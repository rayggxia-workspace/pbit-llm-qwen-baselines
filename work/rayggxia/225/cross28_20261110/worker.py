from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
root=Path(__file__).resolve().parent;phase=sys.argv[1];index=int(sys.argv[2]);assert phase in ('pilot','full')
mf=json.loads((root/'FROZEN_MANIFEST.json').read_bytes());e=mf['environment']
for n,v in mf['files_sha256'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==v,n
for name,k in [('runtime','EXECUTION_MANIFEST.json'),('dependencies','MANIFEST.json'),('snapshot','SNAPSHOT_MANIFEST.json')]:
    assert hashlib.sha256((Path(e[name])/k).read_bytes()).hexdigest()==e[name+'_manifest_sha256']
case=mf['gates' if phase=='pilot' else 'full'][index];name=phase+'_'+case['model']+'_'+case['scheme']+'_s'+str(case['seed'])
out=root/'outputs'/name;work=root/'work'/name;work.mkdir(parents=True,exist_ok=False);assert not out.exists()
cmd=[sys.executable,'-B',str(root/'cross_models_20261110/run.py'),'--snapshot',e['snapshot'],'--runtime',e['runtime'],
    '--dependencies',e['dependencies'],'--bindings',str(root/'250MHz/BINDINGS.json'),'--macros',str(root/'250MHz/WHOLE_CONFIG.json'),
    '--model',case['model'],'--scheme',case['scheme'],'--seed',str(case['seed']),'--head','--backend','native','--out',str(out)]
if phase=='pilot':cmd+=['--layers','1','--head-probe-rows','384']
rec=dict(status='running',phase=phase,case=case,command=cmd,working_directory=str(work),python=sys.version,
    job_id=os.environ.get('SLURM_JOB_ID'),started_UTC=datetime.datetime.utcnow().isoformat(),
    frozen_manifest_sha256=hashlib.sha256((root/'FROZEN_MANIFEST.json').read_bytes()).hexdigest())
(work/'INVOCATION.json').write_text(json.dumps(rec,indent=2)+'\n');started=time.time()
with (work/'run.log').open('wb') as log:rc=subprocess.run(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT).returncode
rec.update(status='completed' if rc==0 else 'failed',exit_code=rc,elapsed_seconds=time.time()-started,
    finished_UTC=datetime.datetime.utcnow().isoformat(),log_sha256=hashlib.sha256((work/'run.log').read_bytes()).hexdigest())
if rc==0:
    seal=json.loads((out/'SEAL.json').read_bytes());assert seal['status']=='completed'
    for n,v in seal['files_sha256'].items():assert hashlib.sha256((out/n).read_bytes()).hexdigest()==v
    r=json.loads((out/'RESULT.json').read_bytes());assert r['backend']=='native'
    if phase=='full':assert r['scope']=='full' and r['layers'] in (28,30) and r['head_probe_rows'] is None
    rec['seal_sha256']=hashlib.sha256((out/'SEAL.json').read_bytes()).hexdigest()
(work/'EXIT.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec),flush=True)
raise SystemExit(rc)
