"""Read/verify sealed energy and independent Nsight evidence; no new GPU work."""
import base64,csv,hashlib,json,sqlite3,subprocess
from pathlib import Path
root=Path('/home/Hongjie_Zeng/projects/pbit-qwen3-gpu-decode-energy-20261029-issue212')
folder=root/'results/paired_60ad3488bfe9d034'
prefix=root/'results/paired_nsys_60ad3488bfe9d034'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
log=root/'logs/i212_pair_60ad34-3443.log'
state=dict(energy_completed=(folder/'COMPLETED.json').exists(),
           trace_completed=(Path(str(prefix)+'_meta')/'TRACE_COMPLETED.json').exists())
csvfile=Path(str(prefix)+'_module_nvtx_kern_sum.csv')
database=Path(str(prefix)+'.sqlite')
state.update(csv_exists=csvfile.exists(),database_exists=database.exists())
if not all(state.values()):
    print(json.dumps(dict(status='not_completed',phase=state,log_tail=log.read_text()[-2800:] if log.exists() else '',
        queue=subprocess.check_output(['/opt/slurm/21.08.8/bin/squeue','-u','Hongjie_Zeng','-h','-o','%.12i %.10T %.10M %R'],text=True))))
else:
    end=json.loads((folder/'COMPLETED.json').read_text());assert end['status']=='completed'
    manifest=folder/'ARTIFACT_MANIFEST.json';assert sha(manifest)==end['manifest_sha256']
    artifacts=[]
    def add(path,name):
        raw=path.read_bytes();artifacts.append(dict(path=name,bytes=len(raw),sha256=sha(path),base64=base64.b64encode(raw).decode()))
    for name,item in json.loads(manifest.read_text()).items():
        p=(folder/name).resolve();assert folder.resolve() in p.parents
        assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes']
        add(p,'paired/raw/'+name)
    for name in ['COMPLETED.json','ARTIFACT_MANIFEST.json']:add(folder/name,'paired/raw/'+name)
    for name in ['ENVIRONMENT.json','TRACE_COMPLETED.json']:
        add(Path(str(prefix)+'_meta')/name,'nsys/'+name)
    add(csvfile,'nsys/NVTX_KERNELS.csv')
    conn=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True)
    columns={r[1] for r in conn.execute('pragma table_info(NVTX_EVENTS)')}
    query='select coalesce(n.text,s.value),count(*) from NVTX_EVENTS n left join StringIds s on n.textId=s.id group by coalesce(n.text,s.value)' if 'textId' in columns else 'select text,count(*) from NVTX_EVENTS group by text'
    counts={s:n for s,n in conn.execute(query) if s and s.startswith('qwen3/')}
    expected={'Embedding':1,'RoPE':37,'QKV_projection':108,'QK_RMSNorm':72,'KV_append':36,'Attention_core':36,
        'Wo_projection':36,'Layer_RMSNorm':72,'FFN_gate_up':72,'FFN_SwiGLU':72,'FFN_down':36,
        'Residual_add':72,'Final_RMSNorm':1,'lm_head':1}
    for context in [2048,8192]:
        for tag,n in expected.items():assert counts.get('qwen3/'+str(context)+'/'+tag)==n*4,(context,tag,counts.get(tag))
    index={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in
           [prefix.with_suffix('.nsys-rep'),database,csvfile]}
    details=dict(status='completed',NVTX_counts=counts,all_36_layers_verified=True,
        kernel_count=conn.execute('select count(*) from CUPTI_ACTIVITY_KIND_KERNEL').fetchone()[0],
        source_sha256=sha(Path('/home/Hongjie_Zeng/projects/pbit-qwen3-gpu-decode-energy-20261029-issue212/snapshots/paired_60ad3488bfe9d034/paired_thermal.py')),
        artifacts=index,trace_prefix=str(prefix),energy_result=str(folder),validator_source_sha256=sha(Path(__file__)) if '__file__' in globals() and Path(__file__).is_file() else None)
    raw=json.dumps(details,indent=2).encode()+b'\n'
    artifacts.append(dict(path='nsys/VALIDATION.json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode()))
    print(json.dumps(dict(status='completed',artifacts=artifacts,validation=details)))
