"""Controller/resource invariants, including two memory granularities."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from dataclasses import replace

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('session_entry',HERE/'run_session.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
from plpu_session.session_control import Session, Simulator
from plpu_session.session_program import Model, compile_plan, layer_program
from plpu_session.session_services import SRAM

CORE=entry.load_core(HERE/'session_memory_reference.py')
BASE=json.loads((HERE/'session_profile.json').read_bytes())
SMALL=Model(name='synthetic128',revision='fixture',layers=2,hidden=128,ffn=256,
            q_heads=2,kv_heads=1,head_dim=64,vocab=137)


def run(model=SMALL,prompt=3,generated=2,rows=4,**overrides):
    hw=dict(BASE,**overrides)
    s=Session(CORE,model,hw,prompt,generated,rows)
    s.sim.run(s.execute())
    return s,s.report()


class SessionChecks(unittest.TestCase):
    def test_first_token_is_prefill_output(self):
        s,r=run(prompt=1,generated=1)
        self.assertEqual(len(r['output_times_ms']),1)
        self.assertFalse(any(x['phase']=='decode' for x in r['layers']))
        self.assertEqual(r['kv_lengths'],[1,1])

    def test_causal_KV_handoff_and_tail(self):
        s,r=run(prompt=5,generated=3,rows=2)
        self.assertEqual(r['kv_lengths'],[7,7])
        for layer in range(2):
            actual=[(x['phase'],x['begin'],x['end']) for x in r['kv_audit'] if x['layer']==layer]
            self.assertEqual(actual,[('prefill',0,2),('prefill',2,4),('prefill',4,5),('decode',5,6),('decode',6,7)])
        self.assertEqual(r['actions']['causal_queries'],2*2*7)
        self.assertEqual(r['actions']['V_samples'],2*2*7*BASE['pv_samples'])

    def test_independent_matrix_and_weight_counts(self):
        s,r=run()
        m=SMALL;tokens=3+2-1
        self.assertEqual(r['engines']['digital']['actions']['QKV'],m.layers*tokens*(m.q_heads+2*m.kv_heads)*m.head_dim*m.hidden)
        self.assertEqual(r['engines']['digital']['actions']['O'],m.layers*tokens*m.q_heads*m.head_dim*m.hidden)
        self.assertEqual(r['engines']['digital']['actions']['LM_HEAD'],2*m.vocab*m.hidden)
        gu=(m.ffn//64)*(m.hidden//64)*8192*m.layers
        self.assertEqual(r['DMA']['by_tag']['prefill/GU_weights']['read_logical_bytes'],gu)
        self.assertEqual(r['DMA']['by_tag']['decode/GU_weights']['read_logical_bytes'],gu)

    def test_no_full_vocab_logit_spill(self):
        _,r=run()
        self.assertEqual(r['actions']['head_streamed_logits'],274)
        self.assertNotIn('first_token/LM_HEAD_output',r['DMA']['by_tag'])
        self.assertNotIn('decode/LM_HEAD_output',r['DMA']['by_tag'])

    def test_finite_state_and_sample_fifo(self):
        _,r=run(prompt=4,generated=2,rows=4)
        self.assertLessEqual(r['state_peak_slots'],BASE['state_slots'])
        self.assertEqual(r['actions']['peak_sample_fifo'],8)
        self.assertLessEqual(r['DMA']['peak_8KiB_credits'],2)

    def test_limited_state_stalls_without_losing_work(self):
        _,a=run(prompt=4,generated=1,rows=4)
        _,b=run(prompt=4,generated=1,rows=4,state_slots=4)
        self.assertEqual(a['frames'],b['frames'])
        self.assertGreaterEqual(b['elapsed_ms'],a['elapsed_ms'])

    def test_llama_template_removes_only_qk_norm(self):
        m=replace(SMALL,qk_norm=False,name='synthetic_llama_template')
        _,r=run(model=m)
        self.assertNotIn('QK_NORM',r['plan']['program'])
        self.assertEqual(r['kv_lengths'],[4,4])
        self.assertFalse(any(k.startswith('QK_NORM') for k in r['engines']['vector']['actions']))

    def test_larger_sampling_budget_counts_accepted_events(self):
        _,a=run(prompt=1,generated=1,pv_samples=16)
        _,b=run(prompt=1,generated=1,pv_samples=64)
        self.assertEqual(b['actions']['V_samples'],4*a['actions']['V_samples'])
        self.assertGreater(b['elapsed_ms'],a['elapsed_ms'])

    def test_memory_backends_keep_work_and_payload(self):
        _,a=run(prompt=2,generated=2)
        _,b=run(prompt=2,generated=2,sram_backend='beat',dma_backend='beat_analytic')
        self.assertEqual(a['frames'],b['frames'])
        for kind in ['read_logical_bytes','write_logical_bytes','read_physical_bytes','write_physical_bytes']:
            self.assertEqual(a['DMA']['counts'][kind],b['DMA']['counts'][kind])
        self.assertEqual(b['request_backend_counts']['dram_read_bytes'],b['DMA']['counts']['read_physical_bytes'])
        self.assertEqual(b['request_backend_counts']['dram_write_bytes'],b['DMA']['counts']['write_physical_bytes'])

    def test_isolated_cim_write_has_32_grants(self):
        times=[]
        for mode in ['burst','beat']:
            sim=Simulator(CORE,250,dict(BASE,sram_backend=mode))
            ram=SRAM(sim,dict(BASE,sram_backend=mode))
            sim.run(ram.transfer('cim:0',0,8192,True,'program'))
            times.append(sim.now)
            self.assertEqual(ram.count['write_words'],512)
        self.assertEqual(times,[128.,128.])

    def test_unsupported_structure_fails_at_compile(self):
        with self.assertRaises(AssertionError):
            compile_plan(replace(SMALL,ffn_type='GEGLU'),BASE,3,2)
        with self.assertRaises(AssertionError):
            compile_plan(SMALL,BASE,0,2)

    def test_qwen_real_shape_capacity_plan(self):
        p=compile_plan(Model(),BASE,2048,128,32)
        self.assertLessEqual(p['max_live_front_bytes'],BASE['front_bytes'])
        self.assertEqual(p['prefill_rows'],4)
        self.assertEqual(p['prefill_pcim_parallel_groups'],3)


if __name__=='__main__':
    unittest.main(verbosity=2)
