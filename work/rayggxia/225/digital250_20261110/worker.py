from pathlib import Path
import datetime,hashlib,json,os,subprocess,sys,time
root=Path(__file__).resolve().parent;phase=sys.argv[1];index=int(sys.argv[2]);assert phase in ('pilot','full')
manifest=json.loads((root/'FROZEN_MANIFEST.json').read_bytes())
for n,v in manifest['files_sha256'].items():assert hashlib.sha256((root/n).read_bytes()).hexdigest()==v,n
env=manifest['environment']
for name,k in [('runtime','EXECUTION_MANIFEST.json'),('dependencies','MANIFEST.json'),('snapshot','SNAPSHOT_MANIFEST.json')]:
    assert hashlib.sha256((Path(env[name])/k).read_bytes()).hexdigest()==env[name+'_manifest_sha256']
scheme=['BF16_dense','W8_dense','W8_screen'][index];case=phase+'_'+scheme
out=root/'outputs'/case;work=root/'work'/case;work.mkdir(parents=True,exist_ok=False)
assert not out.exists()
cmd=[sys.executable,'-B',str(root/'digital250_20261110/run.py'),'--snapshot',env['snapshot'],'--runtime',env['runtime'],
    '--dependencies',env['dependencies'],'--bindings',str(root/'250MHz/BINDINGS.json'),
    '--macros',str(root/'250MHz/WHOLE_CONFIG.json'),'--scheme',scheme,'--layers','1' if phase=='pilot' else '36',
    '--head','--backend','native','--out',str(out)]
if phase=='pilot':cmd+=['--head-probe-rows','384']
rec=dict(status='running',phase=phase,scheme=scheme,command=cmd,working_directory=str(work),python=sys.version,
    job_id=os.environ.get('SLURM_JOB_ID'),array_task=os.environ.get('SLURM_ARRAY_TASK_ID'),
    started_UTC=datetime.datetime.utcnow().isoformat(),frozen_manifest_sha256=hashlib.sha256((root/'FROZEN_MANIFEST.json').read_bytes()).hexdigest())
(work/'INVOCATION.json').write_text(json.dumps(rec,indent=2)+'\n');start=time.time()
with (work/'run.log').open('wb') as log:rc=subprocess.run(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT).returncode
rec.update(exit_code=rc,status='completed' if rc==0 else 'failed',elapsed_seconds=time.time()-start,
    finished_UTC=datetime.datetime.utcnow().isoformat(),log_sha256=hashlib.sha256((work/'run.log').read_bytes()).hexdigest())
if rc==0:
    seal=json.loads((out/'SEAL.json').read_bytes());assert seal['status']=='completed'
    for n,v in seal['files_sha256'].items():assert hashlib.sha256((out/n).read_bytes()).hexdigest()==v
    r=json.loads((out/'RESULT.json').read_bytes());assert r['backend']=='native' and r['scheme']==scheme
    if phase=='full':assert r['scope']=='full' and r['layers']==36 and r['head_probe_rows'] is None
    rec['seal_sha256']=hashlib.sha256((out/'SEAL.json').read_bytes()).hexdigest()
(work/'EXIT.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec),flush=True)
raise SystemExit(rc)
