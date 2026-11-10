"""Freeze three standard digital controls, guarded by per-case native gates."""
from pathlib import Path
import ast,hashlib,json,zipfile
H=Path(__file__).resolve().parent;ROOT=H.parents[3];P=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda p,x:p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
assert not (H/'SUBMISSION.json').exists(),'existing submission:status only'
names=['whole_model.py','sram_characterization.py','pricing250.py','250MHz/BINDINGS.json','250MHz/WHOLE_CONFIG.json']
names += ['digital250_20261110/'+n for n in ('run.py','model.py','pricing.py','FFN_SOURCE_PROFILE.json')]
hashes={n:sha(P/n) for n in names};digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:12]
package=H/('package_'+digest);package.mkdir(exist_ok=True)
for name in names:
    dst=package/name;dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():assert sha(dst)==hashes[name]
    else:dst.write_bytes((P/name).read_bytes())
    if dst.suffix=='.py':ast.parse(dst.read_text(),feature_version=(3,9))
worker=r'''from pathlib import Path
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
'''
(package/'worker.py').write_bytes(worker.encode());hashes['worker.py']=sha(package/'worker.py');ast.parse(worker,feature_version=(3,9))
old=json.loads((H.parent/'full250_20261109/package_3c811d6efe58/FROZEN_MANIFEST.json').read_bytes())
manifest=dict(status='IMMUTABLE28_DIGITAL250_PLAN',files_sha256=hashes,environment=old['environment'],
    model='Qwen/Qwen3-4B',model_revision=old['model_revision'],CPU_only=True,GPUs=0,
    schemes=['BF16_dense','W8_dense','W8_screen'],layers=36,vocab=151936,B=1,context=2048,seed=17,
    process='28nmTT0.9V25C',clock_MHz=250,SRAM_KiB=832,SRAM_macros=178,
    area_target_mm2=6.480302546479157,old_scaled_P8_CIM_not_primary=True,
    baseline_scope='same three55nm numerical paths,28nm measured actions;finite native memory;notPPLorphysicalchip')
save(package/'FROZEN_MANIFEST.json',manifest)
archive=H/('tlm28d250_full225_'+digest+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in package.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(package))
base='/public3/home/t6s011227/pbit_chimera_pipeline_20260920'
plan=dict(local=str(archive),remote=base+'/'+archive.name,root=base+'/tlm28d250_full225_'+digest,
    sha256=sha(archive),bytes=archive.stat().st_size,manifest_sha256=sha(package/'FROZEN_MANIFEST.json'),package=str(package),
    resources=dict(partition='v6_384',cpus_per_task=1,GiB_per_task=12,pilot_hours=4,full_hours=24,concurrency=2,GPUs=0))
save(H/'UPLOAD_PLAN.json',plan);print(json.dumps(plan))
