"""Register this actual functional run; preserve each registry's existing union."""
from pathlib import Path
import hashlib,importlib.util,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parents[2]
PROJECT=Path('C:/Users/86134/Documents/a_P_BIT')
RUN_ID='prefill-controller-225-20261127'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def module(path):
    s=importlib.util.spec_from_file_location('registry',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    r=json.loads((ROOT/'results/RESULTS.json').read_text())
    manifest=json.loads((ROOT/'results/RUN_MANIFEST.json').read_text())
    artifacts=[]
    for name in ['README_ZH.md','REPORT_ZH.md','results/RESULTS.json','results/RUN_MANIFEST.json','results/SOURCE_BINDINGS.json','results/BUDGET_UPDATE.json']:
        p=ROOT/name;artifacts.append({'role':name,'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size,'present_at_registration':True})
    record={'schema_version':1,'id':RUN_ID,'name':'Prefill多行权重复用、六核调度与交错状态SRAM：功能/周期回放',
     'family':'P-LPU/prefill_controller','registered_on':'2026-11-27','owner':'rayggxia','issue':225,
     'evidence_level':'RTL_FUNCTIONAL','status':'FUNCTIONAL_CYCLE_PASS_NOT_FULL_PREFILL',
     'stages':{'functional':'passed','synthesis':'not_run','sta':'not_run','power':'not_run','postlayout':'not_run'},
     'boundary':'Separate prompt sequencer and matrix-phase controller; real upstream stochastic arithmetic, finite DMA and synchronous 1RW state banks. Not a full decoder prefill run.',
     'conditions':{'cores':6,'active_core_scan':[1,4,5,6],'rows_per_weight':[1,3,8,32],
      'sampling':[8,16,32,64,128],'weight_bits':8,'local_count_bits':21,'state_bits':64,
      'state_physical_KiB':256,'DMA_return_KiB':16,'command_queue':16,'seeds':[17,29,43],
      'process':'process-independent RTL; intended28nm/250MHz, no new PPA/STA',
      'clock_MHz_reference':250,'model_and_corpus':'N/A: synthetic fixed-point inputs, no PPL'},
     'source':{'repository':'rayggxia-workspace/pbit-llm-qwen-baselines',
      'execution_base_commit':'23a1fd51ce7ed4aa53913895897a1aee4cbdda03',
      'execution_patch':'new files bound by exact source SHA in SOURCE_BINDINGS; publication follows execution',
      'source_bindings_sha256':sha(ROOT/'results/SOURCE_BINDINGS.json'),
      'run_manifest_sha256':sha(ROOT/'results/RUN_MANIFEST.json')},
     'artifacts':artifacts,
     'cases':[{'kind':x['kind'],'arguments':x['arguments'],'returncode':x['returncode'],
       'log':x['log'],'log_sha256':x['log_sha256']} for x in manifest['runs']],
     'limitations':['Prompt and matrix controllers validated separately; full layer lowering/digital attention/activation mapping not integrated.',
      'GU and Wd tested as separate phases with synthetic input codes; no full model quality result.',
      'Cycle correctness is not STA or power/area validation; inherited SRAM macro timing/binding remains separate.',
      'Upstream arithmetic dependencies are read-only local package files, exact paths and hashes retained; this task does not republish their source package.'],
     'next_action':'Connect layer task lowering/digital services; optimize per-core DMA issue bubbles and row handover; then replay complete prefill.'}
    path=ROOT/'results/REGISTRY_RECORD.json';path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    receipts={}
    for name,here in [('task',REPO/'digital_circuit_simulation_registry'),('project_mirror',PROJECT/'digital_circuit_simulation_registry')]:
        mod=module(here/'registry.py');dest=here/'records'/(RUN_ID+'.json')
        if dest.exists():
            if json.loads(dest.read_text(encoding='utf-8'))!=record:raise RuntimeError('Existing run differs: '+str(dest))
            mod.render()
        else:mod.add(path)
        receipts[name]=mod.check()
        # Check our own artifacts exactly; old external entries may be unavailable.
        for a in artifacts:
            p=Path(a['path']);assert sha(p)==a['sha256'] and p.stat().st_size==a['bytes']
        receipts[name]['new_run_artifacts_exact']=True
    (ROOT/'results/REGISTRY_CHECK.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipts,ensure_ascii=False))
if __name__=='__main__':main()
