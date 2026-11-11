"""Freeze two shapes, eight native gates and twelve full CPU cases."""
from pathlib import Path
import ast,hashlib,json,zipfile
H=Path(__file__).resolve().parent;ROOT=H.parents[3];P=ROOT/'architecture_tlm/process_28nm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
save=lambda p,x:p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
assert not (H/'SUBMISSION.json').exists(),'check existing receipt;do not duplicate'
names=['whole_model.py','whole_pricing.py','pricing250.py','candidate_sram.py','mixed_sram.py','sram_characterization.py',
    '250MHz/BINDINGS.json','250MHz/WHOLE_CONFIG.json']
names += ['digital250_20261110/'+n for n in ('model.py','pricing.py','FFN_SOURCE_PROFILE.json')]
names += ['cross_models_20261110/'+n for n in ('model.py','run.py','MODELS.json')]
hashes={n:sha(P/n) for n in names};digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:12]
package=H/('package_'+digest);package.mkdir(exist_ok=True)
for n in names:
    d=package/n;d.parent.mkdir(parents=True,exist_ok=True)
    if d.exists():assert sha(d)==hashes[n]
    else:d.write_bytes((P/n).read_bytes())
    if d.suffix=='.py':ast.parse(d.read_text(),feature_version=(3,9))
gates=[];full=[]
for model in ('llama32_3b','deepseek_7b'):
    for scheme in ('SC_ising','BF16_dense','W8_dense','W8_screen'):
        gate=len(gates);gates.append(dict(model=model,scheme=scheme,seed=17,index=gate))
        for seed in ((17,503,1009) if scheme=='SC_ising' else (17,)):
            full.append(dict(model=model,scheme=scheme,seed=seed,gate_index=gate,index=len(full)))
worker=r'''from pathlib import Path
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
'''
(package/'worker.py').write_bytes(worker.encode());hashes['worker.py']=sha(package/'worker.py')
env=json.loads((H.parent/'full250_20261109/package_3c811d6efe58/FROZEN_MANIFEST.json').read_bytes())['environment']
manifest=dict(status='IMMUTABLE28_CROSS_MODEL250_PLAN',files_sha256=hashes,environment=env,
    gates=gates,full=full,models=json.loads((P/'cross_models_20261110/MODELS.json').read_bytes())['models'],
    clock_MHz=250,SRAM_KiB=832,physical_SRAM_macros=178,batch=1,context=2048,
    GU_samples=16,Wd_samples=32,K=128,S=64,SC_cores=3,CPU_only=True,GPUs=0,
    scope='same28nmchip;actualshapeandKVwaves;notaccuracy/newweights',
    Q_head_padding='physical4Q issue slots;activeFMA16 slices gated;area/idleretained')
save(package/'FROZEN_MANIFEST.json',manifest)
archive=H/('tlm28cross250_225_'+digest+'.zip')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in package.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(package))
base='/public3/home/t6s011227/pbit_chimera_pipeline_20260920'
plan=dict(local=str(archive),remote=base+'/'+archive.name,root=base+'/tlm28cross250_225_'+digest,
    package=str(package),sha256=sha(archive),bytes=archive.stat().st_size,manifest_sha256=sha(package/'FROZEN_MANIFEST.json'),
    resources=dict(partition='v6_384',cpus_per_task=1,pilot_GiB=12,full_GiB=24,pilot_hours=4,full_hours=24,
        native_gate_array=8,full_jobs=12,full_artificial_concurrency_cap=None,GPUs=0))
save(H/'UPLOAD_PLAN.json',plan);print(json.dumps(plan))
