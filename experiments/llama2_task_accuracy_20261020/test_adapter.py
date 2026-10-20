"""CPU integration contracts, with all 32 layers of a tiny random Llama fixture."""
import copy
import unittest

import torch
from transformers import LlamaConfig, LlamaForCausalLM

from .adapter import JointAttentionController, ModelGuard, _case, pack_weight_codes
from .cached_score import evaluate_tasks
from .run import configurations

torch.set_num_threads(1)


def model():
    torch.manual_seed(23)
    config=LlamaConfig(vocab_size=64,hidden_size=64,intermediate_size=128,
        num_hidden_layers=32,num_attention_heads=2,num_key_value_heads=2,
        max_position_embeddings=2048,attention_dropout=0.,pretraining_tp=1)
    config._attn_implementation='sdpa'
    return LlamaForCausalLM(config).eval()


DOCS=[dict(id='fixture:0',task='fixture',context_ids=[1,2,3,4],choices_ids=[[5,6,7],[8]]),
      dict(id='fixture:1',task='fixture',context_ids=[2,3,4,5],choices_ids=[[6],[7,8]])]


def choice_scores(value):
    return [[c['logprob'] for c in d['choices']] for d in value['documents']]


class Contracts(unittest.TestCase):
    def test_suite(self):
        rows=configurations()
        self.assertEqual(len(rows),13)
        self.assertEqual(len({c['name'] for c in rows}),13)
        self.assertEqual([r['seed'] for r in rows if r['name'].startswith('joint_S128')],[0,1,2])
        self.assertEqual(_case(rows[4])['mode'],'ising_only')
        with self.assertRaises(ValueError):_case(dict(mode='screen_ising'))

    def test_digital_wrapper_identical_and_all_layers(self):
        m=model()
        a=evaluate_tasks(m,DOCS,dict(ffn='none',mode='sdpa',batch=2),None)
        b=evaluate_tasks(m,DOCS,dict(ffn='none',mode='digital_sdpa',batch=2),None)
        self.assertEqual(a['documents'],b['documents'])
        audit=b['execution_audit']
        self.assertTrue(audit['every_scored_target_used_32_decode_layers'])
        self.assertEqual(len(audit['attention_decode_calls_per_layer']),32)
        self.assertTrue(all(n==audit['actual_decode_calls'] for n in audit['attention_decode_calls_per_layer']))
        self.assertFalse(hasattr(m.model.layers[0].self_attn,'_joint_attention_owner'))

    def test_original_independent_choice_reference(self):
        m=model()
        scores=evaluate_tasks(m,[DOCS[0]],dict(ffn='none',mode='sdpa',batch=1),None)
        with torch.inference_mode():
            for choice,expected in zip(DOCS[0]['choices_ids'],scores['documents'][0]['choices']):
                cache=m.model(input_ids=torch.tensor([DOCS[0]['context_ids'][:-1]]),use_cache=True).past_key_values
                total=0.
                for i,target in enumerate(choice):
                    token=DOCS[0]['context_ids'][-1] if i==0 else choice[i-1]
                    out=m.model(input_ids=torch.tensor([[token]]),past_key_values=cache,use_cache=True)
                    cache=out.past_key_values
                    total+=m.lm_head(out.last_hidden_state[:,-1]).float().log_softmax(-1)[0,target].item()
                self.assertEqual(total,expected['logprob'])

    def test_joint_stream_rollback_repeatable_and_choice_permutation(self):
        config=dict(ffn='b4_t32',mode='ising_only',samples=8,burn=1.,spacing=1.,batch=2,seed=7)
        first=evaluate_tasks(model(),DOCS,config,None)
        second=evaluate_tasks(model(),DOCS,config,None)
        self.assertEqual(first['documents'],second['documents'])
        swapped=copy.deepcopy(DOCS)
        for row in swapped:row['choices_ids'].reverse()
        third=evaluate_tasks(model(),swapped,config,None)
        self.assertEqual(choice_scores(first),[list(reversed(x)) for x in choice_scores(third)])
        self.assertEqual(len(first['ffn_stats']),32)
        self.assertEqual(first['sampling_stats']['installed_layers'],32)

    def test_guard_detects_weight_write(self):
        m=model();guard=ModelGuard(m,'none')
        with torch.no_grad():next(m.parameters()).add_(1.)
        with self.assertRaises(RuntimeError):guard.verify()

    def test_weight_code_packing_is_lossless_and_forward_identical(self):
        from experiments.qwen_multiscale_stratified_20261019.stratified_core import StratifiedFFN
        original=model().model.layers[0].mlp
        reference=StratifiedFFN(original,policy='pot4',mode='sampled',cycles=32,strata=32,seed=3)
        packed=pack_weight_codes(StratifiedFFN(original,policy='pot4',mode='sampled',cycles=32,strata=32,seed=3))
        for name in ('gu_codes','down_codes'):
            self.assertEqual(getattr(packed,name).dtype,torch.int8)
            self.assertTrue(torch.equal(getattr(reference,name),getattr(packed,name).to(torch.int16)))
        for name in ('gu_decoded','down_decoded','gu_tile_lsb','down_tile_lsb'):
            self.assertTrue(torch.equal(getattr(reference,name),getattr(packed,name)))
        with torch.inference_mode():
            for length in (7,1,1):
                x=torch.randn(2,length,64)
                self.assertTrue(torch.equal(reference(x),packed(x)))
        packed.gu_codes[0,0]=0
        packed.gu_codes[0,1]=127
        # Out-of-range INT16 must be rejected instead of wrapping silently.
        reference.gu_codes[0,0]=128
        with self.assertRaises(RuntimeError):pack_weight_codes(reference)

    def test_reject_wrong_architecture_or_shared_owner(self):
        m=model();m.config.model_type='qwen2'
        with self.assertRaises(ValueError):JointAttentionController(mode='ising_only').install(m)
        m=model();m.model.layers[0].self_attn._joint_attention_owner=object()
        with self.assertRaises(ValueError):JointAttentionController(mode='ising_only').install(m)


if __name__=='__main__':unittest.main()
