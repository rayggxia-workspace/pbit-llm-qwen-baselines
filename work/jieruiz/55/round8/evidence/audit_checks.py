import os,pathlib,subprocess,sys,json,time
out=pathlib.Path(__file__).resolve().parent;root=out.parents[1]/'tmp/pr55-review-round8-20261023'
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONUTF8='1')
ro='architecture_tlm/resource_optimization_v1/results';df='architecture_tlm/ffn_dataflow_optimization/results'
commands={
'registry_tests':['-m','unittest','discover','-s','digital_circuit_simulation_registry','-p','test_registry.py','-v'],
'registry_check':['digital_circuit_simulation_registry/registry.py','check'],
'119_artifacts':['-m','architecture_tlm.resource_optimization_v1.verify','--inputs',ro+'/coarse_20261023',ro+'/confirmation_20261023',ro+'/vector_confirmation_20261023','--expected','208','--output',str(out/'119_artifacts.json')],
'122_artifacts':['work/amlink1219/121/validate_artifacts.py'],
'127_artifacts':['-m','architecture_tlm.ffn_dataflow_optimization.verify_results','--dependencies',str(out/'frozen_dependencies'),'--fixtures',df+'/fixtures','--runs',*[df+'/shard'+str(i) for i in range(4)],'--expected-grid','main48','--output',str(out/'127_artifacts.json')],
'126_rtl':['-m','architecture_tlm.cycle_v1.audit.verify_rtl_evidence','--output',str(out/'126_rtl.json')],
'126_layer':['-m','architecture_tlm.cycle_v1.audit.verify_layer_artifacts','--results','architecture_tlm/cycle_v1/results/reduced_layer_20261023','--output',str(out/'126_layer.json')],
}
for key in sys.argv[1:] or commands:
 start=time.time();cmd=[sys.executable,'-B','-X','utf8',*commands[key]]
 with (out/(key+'.log')).open('w',encoding='utf-8',newline='\n') as f:p=subprocess.run(cmd,cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT)
 result=dict(check=key,command=cmd,exit_code=p.returncode,seconds=round(time.time()-start,3))
 (out/(key+'_command.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(result),flush=True);print((out/(key+'.log')).read_text(encoding='utf-8')[-1500:],flush=True)
