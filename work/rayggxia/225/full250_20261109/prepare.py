"""Freeze full Qwen28/250 CPU jobs; no weights, credentials or PDK bundled."""
from pathlib import Path
import ast,hashlib,json,zipfile
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1];D=ROOT/'architecture_tlm/process_28nm'
BASE='/public3/home/t6s011227/pbit_chimera_pipeline_20260920'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.write_bytes((json.dumps(v,indent=2)+'\n').encode())
assert not (H/'SUBMISSION.json').exists(),'check existing receipt;never submit twice'
names=['run_whole.py','whole_model.py','whole_pricing.py','pricing250.py','candidate_sram.py','mixed_sram.py','sram_characterization.py',
       '250MHz/BINDINGS.json','250MHz/WHOLE_CONFIG.json']
hashes={n:sha(D/n) for n in names}
cfg=json.loads((D/'250MHz/WHOLE_CONFIG.json').read_bytes());b=json.loads((D/'250MHz/BINDINGS.json').read_bytes())
assert cfg['clock_MHz']==b['clock_MHz']==250 and cfg['SRAM']['capacity_KiB']==832 and cfg['SRAM']['bank_count']==178
assert b['FFN_selected_core_count']==3 and b['score_frontend']=='s12_max_gap'
digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()[:12]
package=H/('package_'+digest);package.mkdir(exist_ok=True)
for name in names:
    p=package/name;p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():assert sha(p)==hashes[name]
    else:p.write_bytes((D/name).read_bytes())
    if p.suffix=='.py':ast.parse(p.read_text(encoding='utf8'),filename=name,feature_version=(3,9))
worker=r'''from pathlib import Path
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
'''
p=package/'worker.py'
if p.exists():assert p.read_bytes()==worker.encode()
else:p.write_bytes(worker.encode())
hashes['worker.py']=sha(p);ast.parse(worker,feature_version=(3,9))
environment=dict(runtime=BASE+'/tlm236_joint_20261105/retry_time_audit_ed028cc70e06',
    dependencies=BASE+'/attention_resources198_20261107/ee741a72b48e/dependencies',snapshot=BASE+'/tlm245_current_3a7dd5e0679e',
    runtime_manifest_sha256='7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40',
    dependencies_manifest_sha256='4ce8d1065aa7d4b5f2067e9e409d5bc56bad987cb6b3edf945719ac85777e483',
    snapshot_manifest_sha256='982f9303785c364ed7c7ac5384927f0a12f98388433708306878e5f14fbae925')
manifest=dict(status='IMMUTABLE_28NM250_FULL_QWEN_PLAN',files_sha256=hashes,environment=environment,
    CPU_only=True,GPUs=0,model='Qwen/Qwen3-4B',model_revision='1cfa9a7208912126459214e8b04321603b3df60c',
    layers=36,vocab=151936,B=1,context=2048,GU_samples=16,Wd_samples=32,K=128,S=64,
    FFN_cores=3,SRAM_KiB=832,SRAM_macros=178,score_front='S12_first',backend='native_LPDDR5X8533_derived',
    full_seeds=[17,503,1009],scope='hardware transaction model,not numerical inference/PPL')
dump(package/'FROZEN_MANIFEST.json',manifest)
archive=H/('tlm28p250_full225_'+digest+'.zip')
if archive.exists():
    with zipfile.ZipFile(archive) as z:
        for p in package.rglob('*'):
            if p.is_file():assert z.read(str(p.relative_to(package)).replace('\\','/'))==p.read_bytes()
else:
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in package.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(package))
plan=dict(local=str(archive),remote=BASE+'/'+archive.name,root=BASE+'/tlm28p250_full225_'+digest,
    sha256=sha(archive),bytes=archive.stat().st_size,manifest_sha256=sha(package/'FROZEN_MANIFEST.json'),
    package=str(package),pilot='one layer+384head,native',full='36layers+151936head;3seeds',
    resources=dict(partition='v6_384',cpus_per_task=1,GiB_per_task=12,full_concurrency=2,pilot_hours=4,full_hours=12,GPUs=0))
dump(H/'UPLOAD_PLAN.json',plan);print(json.dumps(plan))
