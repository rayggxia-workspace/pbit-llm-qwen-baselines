from pathlib import Path
import hashlib,importlib.util,json,sys,unittest
ROOT=Path('C:/Users/86134/Documents/a_P_BIT')
WD=Path(__file__).resolve().parents[4]
FOLDER=WD/'architecture_tlm/attention_candidate_20261107'
def module(name,path,package=False):
    spec=importlib.util.spec_from_file_location(name,path,
        submodule_search_locations=[str(path.parent)] if package else None)
    obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj);return obj
boot=module('attention_review_boot225',WD/'architecture_tlm/sampling_latency_20261106/bootstrap.py')
boot.use_runtime(ROOT/'project_archives/ffn_sram_batch204_20261106/runtime',
    ROOT/'project_archives/sampling_latency225_20261106/dependencies')
from architecture_tlm.sampling_latency_20261106.model import make_model
from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
owner=ROOT/'architecture_tlm/attention_resource_compaction_20261107'
module('reviewed_attention_owner225',owner/'__init__.py',True)
code=module('reviewed_attention_owner225.model',owner/'model.py')
owner_tests=module('reviewed_attention_owner225.test_model',owner/'test_model.py')
integration=module('candidate_attention_integrate225',FOLDER/'integrate.py')
estimator=module('candidate_attention_estimate225',FOLDER/'estimate.py')
inputs=json.loads((FOLDER/'INPUTS.json').read_bytes())

def host():
    return make_model(AnalyticDRAM(),gu_samples=8,wd_samples=32,mode='ising',ffn='sc',samples={},layers=36,include_lm=True)

class Integration(unittest.TestCase):
    def test_real_selected_host_accepts_owner_interface(self):
        h,m=host();integration.install(m,code.install)
        self.assertEqual(h.mem.capacity,1216*1024)
        self.assertEqual(m.ordinary_pool_contract['FP32_reduction_adders'],32)
        self.assertEqual(m.resource_contract['PV_ADD_lanes'],128)
        self.assertEqual(m.resource_contract['independent_QK_lanes'],0)
        self.assertEqual(m.sampling_latency_contract['GU_samples'],8)
        self.assertEqual(m.sampling_latency_contract['NL_Wd_samples'],32)
    def test_physical_ledger_does_not_retain_old_units(self):
        h,m=host()
        # Exercise real owner install/run wrapping but avoid rerunning a full
        # token just to test the inherited old-resource metadata mismatch.
        m.run=lambda:dict(executed_resources=dict(QK_MAC_lanes=512,PV_sample_ADD_lanes=512,FP32_reduction_adders=128))
        integration.install(m,code.install);r=m.run()
        self.assertEqual(r['executed_resources']['QK_MAC_lanes'],0)
        self.assertEqual(r['executed_resources']['logical_QK_service_lanes'],512)
        self.assertEqual(r['executed_resources']['PV_sample_ADD_lanes'],128)
        self.assertEqual(r['executed_resources']['FP32_reduction_adders'],32)
        self.assertFalse(r['attention_candidate_integration']['new_PV4_DC_area_used'])
    def test_other_host_not_globally_changed(self):
        _,a=host();integration.install(a,code.install)
        _,b=host()
        self.assertEqual(b.ordinary_pool_contract['FP32_reduction_adders'],128)
        self.assertEqual(b.attention_adapter_contract['sample_ADD_lanes'],512)
    def test_whole_area_boundary_and_no_duplicate_shared_pool(self):
        x=estimator.evaluate(inputs['base_budget'],inputs['owner_summary'])
        self.assertAlmostEqual(x['candidate_area55_mm2'],41.46302144709482)
        self.assertAlmostEqual(sum(x['groups'].values()),x['candidate_area55_mm2'])
        self.assertEqual(x['areas55_mm2']['shared_SRAM'],8.181624917592)
        self.assertGreater(x['candidate_area55_mm2'],inputs['owner_summary']['areas']['combined32']['attention_plus_pool_plus672KiB_mm2'])
    def test_failed_PV4_DC_not_used_as_official_price(self):
        x=estimator.evaluate(inputs['base_budget'],inputs['owner_summary'])
        self.assertFalse(x['new_PV4_failed_DC_area_used'])
        self.assertAlmostEqual(x['areas55_mm2']['Attention_V_accumulate_control'],3.152141568)
    def test_more_aggressive_reduce8_not_silently_selected(self):
        _,m=host()
        with self.assertRaises(ValueError):integration.install(m,code.install,'combined')

suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(owner_tests),
    unittest.defaultTestLoader.loadTestsFromTestCase(Integration)])
result=unittest.TextTestRunner(verbosity=2).run(suite)
artifacts=json.loads((ROOT/'architecture_tlm/module_handoff/attention_resource_compaction_20261107/RESULTS.json').read_bytes())['artifacts']
checked=[]
for row in artifacts:
    p=Path(row['path']);raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==row['sha256'],p
    checked.append(dict(path=str(p),sha256=row['sha256'],bytes=len(raw)))
validation=dict(status='PASS_conditional_integration' if result.wasSuccessful() else 'FAILED',
    local_tests=result.testsRun,owner_artifact_hashes_checked=len(checked),artifacts=checked,
    no_new_native_jobs=True,new_RTL_PPA=False,new_PPL=False,PV4_gate_sim_passed=False,
    QK_real_input_mapping_passed=False,host_default_changed=False,
    own_source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FOLDER.glob('*.py')},
    pinned_owner_source_sha256=hashlib.sha256((owner/'model.py').read_bytes()).hexdigest())
(Path(__file__).parent/'VALIDATION.json').write_bytes((json.dumps(validation,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps({k:validation[k] for k in ('status','local_tests','owner_artifact_hashes_checked')}))
raise SystemExit(0 if result.wasSuccessful() else 1)
