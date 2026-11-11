"""Integration checks on real sealed counters and completed owner price cards."""
from pathlib import Path
from types import SimpleNamespace as NS
import copy,hashlib,json,os,unittest,tempfile
from whole_pricing import price
from pricing250 import split_head

ROOT=Path(__file__).resolve().parents[2];WS=Path(os.environ.get('PBIT_WORKSPACE',str(ROOT.parents[1])))
D=Path(__file__).resolve().parent
load=lambda p:json.loads(Path(p).read_bytes())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

class Refresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b=load(D/'250MHz/BINDINGS.json');cls.c=load(D/'250MHz/WHOLE_CONFIG.json')
        H=ROOT/'work/rayggxia/225/mixed34_20261109/revision2/p250_mixed'
        seal=load(H/'SEAL.json')
        for n,v in seal['files_sha256'].items():assert sha(H/n)==v
        cls.r=load(H/'RESULT.json');cls.old=load(H/'BUDGET.json')
        slots={x['component']:x['instances'] for x in cls.old['rows']}
        cls.m=NS(common_cores=3,sampler_pool=NS(slots=slots['score_front']),
            norm_pool=NS(slots=slots['SparQ_norm']),top_pool=NS(slots=slots['SparQ_top']))

    def test_selected_archives_and_source_bytes(self):
        for p,v in self.b['source_sha256'].items():
            if (WS/p).exists():self.assertEqual(sha(WS/p),v,p)
        f=load(WS/'architecture_tlm/module_handoff/ffn28_nomargin_20261109/profile.json')
        for card in f['accepted_components'].values():
            p=Path(card['archive']['path']);self.assertTrue(p.exists(),str(p))
            self.assertEqual(sha(p),card['archive']['sha256'])

    def test_real_price_selection_and_other_clock(self):
        self.assertAlmostEqual(self.b['FFN_core']['area_mm2'],.372693132)
        self.assertAlmostEqual(self.b['shared_FMA']['gross_pJ_per_FMA']*64,203.825)
        self.assertAlmostEqual(self.b['attention_cards']['gap_sampler_250']['area28_mm2'],.008918154)
        self.assertAlmostEqual(self.b['attention_cards']['gap_softmax_r8_gf64_250']['area28_mm2'],.02209788)
        self.assertEqual(self.b['score_frontend'],'s12_max_gap')
        self.assertEqual((self.c['FMA_feedback_cycles'],self.c['PV_feedback_cycles']),(4,7))
        self.assertEqual(sha(D/'500MHz/BINDINGS.json'),'634b3a61a3b7bfbfa25e6a3b64c071494562a4dab3de64f49f147e5da7a1b128')
        accepted=load(D/'DEFAULT_SRAM832_20261109.json')
        old500=next(x for x in accepted['rows'] if x['clock_MHz']==500)
        self.assertEqual(sha(D/'500MHz/WHOLE_CONFIG.json'),old500['default_config_sha256'])

    def test_counter_ledger_closed_without_waiving_proxy_limits(self):
        q=price(self.m,self.r,self.b)
        self.assertEqual(q['unpriced_in_chosen_boundary'],[])
        self.assertAlmostEqual(q['conditional_subsystem_area_mm2'],sum(x['area_mm2'] for x in q['rows']))
        self.assertAlmostEqual(q['conditional_subsystem_energy_mJ'],sum(x['energy_mJ'] for x in q['rows']))
        names=[x['component'] for x in q['rows']];self.assertEqual(len(names),len(set(names)))
        self.assertEqual(names.count('shared_FMA256'),1)
        self.assertIsNone(q['full_system_area_mm2'])
        self.assertFalse(q['physical_full_clock_qualified'])
        self.assertGreater(q['conditional_subsystem_area_mm2'],q['covered_component_area_mm2'])
        self.assertLess(q['conditional_subsystem_area_mm2'],6.56634)
        self.assertFalse(self.b['PV_backend']['area_is_new_compact_PPA'])

    def test_gross_idle_identity(self):
        q=price(self.m,self.r,self.b);row=next(x for x in q['rows'] if x['component']=='FFN_shared_GU_Wd')
        core=self.b['FFN_core'];busy=sum(self.r['kernel_active'][k]*core['modes'][mode]['frame_ns']
            for mode,k in [('GU','GU_frames'),('Wd','Wd_M128_frames')])
        gross=sum(self.r['kernel_active'][k]*core['modes'][mode]['gross_pJ_per_frame']
            for mode,k in [('GU','GU_frames'),('Wd','Wd_M128_frames')])
        expected=(gross+core['waiting_power_W']*(3*self.r['time_ns']-busy)*1000)/1e9
        self.assertAlmostEqual(row['energy_mJ'],expected,places=14)

    def test_head_split_preserves_resident_area(self):
        q=price(self.m,self.r,self.b);part=copy.deepcopy(q);part['conditional_subsystem_energy_mJ']*=.9
        part['external_bytes']=int(part['external_bytes']*.9)
        part['conditional_total_energy_mJ_by_external_pJbit']={k:v*.9 for k,v in part['conditional_total_energy_mJ_by_external_pJbit'].items()}
        s=split_head(q,part,self.r['time_ns'],self.r['time_ns']*.9)
        self.assertAlmostEqual(s['lm_head_stage']['core_energy_mJ'],q['conditional_subsystem_energy_mJ']*.1)

    def test_legacy_generator_cannot_downgrade_current250(self):
        from prepare_bindings import write
        with tempfile.TemporaryDirectory(dir=ROOT/'work/rayggxia/225/update250_20261109') as tmp:
            out=Path(tmp);(out/'250MHz').mkdir();p=out/'250MHz/BINDINGS.json'
            p.write_bytes(b'{"refresh250_version":1}\n');before=p.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'newer accepted overlay'):write(WS,out)
            self.assertEqual(before,p.read_bytes());self.assertFalse((out/'500MHz').exists())

if __name__=='__main__':unittest.main(verbosity=2)
