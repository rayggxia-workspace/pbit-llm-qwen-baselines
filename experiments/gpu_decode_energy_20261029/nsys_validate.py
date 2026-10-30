import hashlib,json,sqlite3,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent.parent/'results/nsys_99b9dbd2a97b75a1'
# This source lives in snapshots/nsys_validation_<hash>; resolve via task root.
task=Path(__file__).resolve().parents[2]
root=task/'results/nsys_99b9dbd2a97b75a1'
model=json.loads((root/'MODEL_COMPLETED.json').read_bytes())
assert model['status']=='completed' and model['layers']==36 and model['logits_bitwise_equal']
dest=root/'validation_v1';dest.mkdir(exist_ok=False)
database=dest/'qwen3_decode.sqlite'
command=[str(Path.home()/'.local/bin/nsys'),'export','--type=sqlite','--output='+str(database),str(root/'qwen3_decode.nsys-rep')]
result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(dest/'EXPORT_LOG.txt').write_text(result.stdout);assert result.returncode==0,result.stdout
conn=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True)
tables={r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
assert {'CUPTI_ACTIVITY_KIND_KERNEL','NVTX_EVENTS'}.issubset(tables)
kernels=conn.execute('select count(*) from CUPTI_ACTIVITY_KIND_KERNEL').fetchone()[0];assert kernels>0
columns={r[1] for r in conn.execute('pragma table_info(NVTX_EVENTS)')}
if 'textId' in columns:
    rows=conn.execute('select coalesce(n.text,s.value),count(*) from NVTX_EVENTS n left join StringIds s on n.textId=s.id group by coalesce(n.text,s.value)').fetchall()
else:rows=conn.execute('select text,count(*) from NVTX_EVENTS group by text').fetchall()
counts={name:count for name,count in rows if name and (name.startswith('qwen3/') or name.startswith('decode/'))}
expected={'qwen3/QKV_projection':432,'qwen3/Attention_core':144,'qwen3/KV_append':144,
 'qwen3/FFN_gate_up':288,'qwen3/FFN_down':144,'decode/eager_fixed':4,'decode/annotated_fixed':4,'decode/graph_fixed':8}
for name,count in expected.items():assert counts.get(name)==count,(name,counts.get(name),count)
kcols=[r[1] for r in conn.execute('pragma table_info(CUPTI_ACTIVITY_KIND_KERNEL)')]
graph={col:conn.execute('select count(*) from CUPTI_ACTIVITY_KIND_KERNEL where "'+col+'" is not null and "'+col+'" != 0').fetchone()[0] for col in kcols if 'graph' in col.lower()}
assert any(v>0 for v in graph.values()),'no graph-associated CUDA kernels'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary={'status':'completed','trace_Slurm_job_id':model['Slurm_job_id'],'validation_Slurm_job_id':__import__('os').environ['SLURM_JOB_ID'],
 'nsys_version':subprocess.check_output([str(Path.home()/'.local/bin/nsys'),'--version'],text=True).strip(),
 'CUDA_kernel_count':kernels,'NVTX_counts':counts,'graph_associated_kernel_counts':graph,
 'expected_tags_and_layer_counts_verified':True,'model_logits_bitwise_equal':True,
 'report':{'relative_path':'qwen3_decode.nsys-rep','bytes':(root/'qwen3_decode.nsys-rep').stat().st_size,'sha256':sha(root/'qwen3_decode.nsys-rep')},
 'sqlite':{'relative_path':'validation_v1/qwen3_decode.sqlite','bytes':database.stat().st_size,'sha256':sha(database)},
 'model_completion_sha256':sha(root/'MODEL_COMPLETED.json'),'validator_source_sha256':sha(Path(__file__)),
 'power_plugin':'2024.6.2 profile help has no nvml_metrics plugin; use existing separate NVML measurement',
 'limitations':['no new model PPL or energy claim','trace adds overhead; not a replacement for unprofiled TPOT','CPU sampling/context-switch tracing disabled for unprivileged capture']}
with (dest/'COMPLETED.json').open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
print(json.dumps(summary),flush=True)
