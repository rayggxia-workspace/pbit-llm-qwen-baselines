import os,pathlib,subprocess,sys,json,time
out=pathlib.Path(__file__).resolve().parent
root=out.parents[1]/'tmp/pr55-review-round8-20261023'
env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1',ENCODE_CYCLE_BACKEND=str(root),ENCODE_CYCLE_REVIEW_TMP=str(out/'test_tmp'),FFN_DATAFLOW_DEPS=str(out/'frozen_dependencies'))
(out/'test_tmp').mkdir(exist_ok=True)
suites={
'119':['architecture_tlm.resource_optimization_v1.test_ledger','architecture_tlm.resource_optimization_v1.test_search'],
'120':['architecture_tlm.ffn_storage_contract.test_model','architecture_tlm.ffn_storage_contract.test_counter'],
'122':['architecture_tlm.encoding_restore_contract.test_adapter','architecture_tlm.encoding_restore_contract.test_arithmetic','architecture_tlm.encoding_restore_contract.test_review'],
'126':['architecture_tlm.cycle_v1.test_'+s for s in ['attention','ffn','kernel','memory','rng_protocol','v6_adapter','gqa']],
'126audit':['architecture_tlm.cycle_v1.audit.test_'+s+'_adversarial' for s in ['core','ffn','attention','native','layer','gqa']],
'127':['architecture_tlm.ffn_dataflow_optimization.test_model','architecture_tlm.ffn_dataflow_optimization.test_fixtures'],
'v6':['architecture_tlm.unified_v6.test_model','architecture_tlm.unified_v6.test_rng_integrated','architecture_tlm.unified_v6.test_rng_interface'],
'registry':['digital_circuit_simulation_registry.test_registry'],
'125':['architecture_tlm.cycle_v1.test_ffn_contract','architecture_tlm.ffn_cycle_integration.test_active_memory','architecture_tlm.ffn_cycle_integration.backend_overlay.test_apply_overlay','architecture_tlm.encoding_restore_contract.ppa.test_flow','architecture_tlm.encoding_restore_contract.sim.test_prepare'],
}
for key in sys.argv[1:] or list(suites):
 command=[sys.executable,'-B','-X','utf8','-m','unittest',*suites[key],'-v'];start=time.time()
 with (out/f'tests_{key}.log').open('w',encoding='utf-8',newline='\n') as log:
  p=subprocess.run(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
 result=dict(suite=key,command=command,exit_code=p.returncode,seconds=round(time.time()-start,3),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip())
 (out/f'tests_{key}.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(result),flush=True)
 print('\n'.join((out/f'tests_{key}.log').read_text(encoding='utf-8').splitlines()[-7:]),flush=True)
