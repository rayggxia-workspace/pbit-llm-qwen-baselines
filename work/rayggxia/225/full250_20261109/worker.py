from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
root=Path(__file__).resolve().parent;phase=sys.argv[1];index=int(sys.argv[2])
manifest=json.loads((root/'FROZEN_MANIFEST.json').read_bytes())
for n,v in manifest['files_sha256'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==v,n
env=manifest['environment']
for name,k in [('runtime','EXECUTION_MANIFEST.json'),('dependencies','MANIFEST.json'),('snapshot','SNAPSHOT_MANIFEST.json')]:
    assert hashlib.sha256((Path(env[name])/k).read_bytes()).hexdigest()==env[name+'_manifest_sha256']
assert sys.version_info>=(3,9)
seed=17 if phase=='pilot' else [17,503,1009][index]
assert phase in ('pilot','full')
name='pilot' if phase=='pilot' else 'seed'+str(seed)
out=root/'outputs'/name;work=root/'work'/name;work.mkdir(parents=True,exist_ok=False)
assert not out.exists(),'preserve prior outputs'
cmd=[sys.executable,'-B',str(root/'run_whole.py'),'--snapshot',env['snapshot'],'--runtime',env['runtime'],
     '--dependencies',env['dependencies'],'--bindings',str(root/'250MHz/BINDINGS.json'),'--cores','3',
     '--layers','1' if phase=='pilot' else '36','--head','--seed',str(seed),'--backend','native','--out',str(out)]
if phase=='pilot':cmd+=['--head-probe-rows','384']
record=dict(status='running',phase=phase,seed=seed,command=cmd,working_directory=str(work),
    python=sys.version,job_id=os.environ.get('SLURM_JOB_ID'),array_task=os.environ.get('SLURM_ARRAY_TASK_ID'),
    started_UTC=datetime.datetime.utcnow().isoformat(),frozen_manifest_sha256=hashlib.sha256((root/'FROZEN_MANIFEST.json').read_bytes()).hexdigest())
(work/'INVOCATION.json').write_text(json.dumps(record,indent=2)+'\n')
start=time.time()
with (work/'run.log').open('wb') as log:code=subprocess.run(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT).returncode
record.update(exit_code=code,elapsed_seconds=time.time()-start,finished_UTC=datetime.datetime.utcnow().isoformat(),
    status='completed' if code==0 else 'failed',log_sha256=hashlib.sha256((work/'run.log').read_bytes()).hexdigest())
if code==0:
    seal=json.loads((out/'SEAL.json').read_bytes());assert seal['status']=='completed'
    for n,v in seal['files_sha256'].items():assert hashlib.sha256((out/n).read_bytes()).hexdigest()==v
    result=json.loads((out/'RESULT.json').read_bytes())
    assert result['backend']=='native' and result['clock_MHz']==250
    if phase=='full':assert result['scope']=='full' and result['layers']==36 and result['head_probe_rows'] is None
    record['seal_sha256']=hashlib.sha256((out/'SEAL.json').read_bytes()).hexdigest()
(work/'EXIT.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
raise SystemExit(code)
