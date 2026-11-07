"""Create a small immutable dependency snapshot and synthetic shape fixtures.

Owner source remains in local/EDA shared storage; public delivery is the glue,
profiles, file digests and execution receipts, not copied private module code.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,shutil,sys

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    w=a.workspace.resolve();out=a.out.resolve();here=Path(__file__).resolve().parent
    out.mkdir(parents=True,exist_ok=False);sources={}
    def copy(source,name):
        dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        sources[name]=dict(source=str(source),sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
    for directory in ('attention_digital_small_20261107','ffn_digital_contract_20261107'):
        for source in (w/'architecture_tlm'/directory).iterdir():
            if source.suffix in ('.py','.json'):copy(source,'architecture_tlm/'+directory+'/'+source.name)
    for name in ('execution.py','CURRENT_WORKLOAD_PLAN.json'):
        copy(here/name,'architecture_tlm/model_scaling_20261106/'+name)
    copy(here.parent/'equal_area_100_250_20261107/TARGETS.json','architecture_tlm/equal_area_100_250_20261107/TARGETS.json')
    old=w/'project_archives/ffn_sram_batch204_20261106/runtime'
    for name in ('unified_v6/shared_memory.py','digital_baselines_20261104/backend.py'):
        copy(old/'base/architecture_tlm'/name,'base/architecture_tlm/'+name)
    copy(w/'architecture_tlm/sram1216_20261106/250MHz/ffn_actor.py','architecture_tlm/sc_actor_source.py')
    copy(w/'architecture_tlm/module_refresh_20261107/FFN_PROFILE.json','inputs/FFN_PROFILE.json')
    copy(w/'project_archives/attention_integrated250_198_20261107/inputs/SAMPLES.json','inputs/SAMPLES.json')
    # Numeric synthetic data only; no model weights, tokenizer or corpus needed.
    import numpy as np
    sys.path.insert(0,str(out))
    from architecture_tlm.attention_digital_small_20261107.numeric_ref import select
    from architecture_tlm.attention_digital_small_20261107.numeric_online import bf16
    models=json.loads((here/'CURRENT_WORKLOAD_PLAN.json').read_bytes())['models'];fixtures={}
    for key,entry in models.items():
        m=entry['shape'];qpg=m['q_heads']//m['kv_heads'];rows=[]
        for g in range(m['kv_heads']):
            rng=np.random.default_rng(17+1000*g);q=bf16(rng.normal(size=(qpg,128)));k=bf16(rng.normal(size=(2048,128)))
            dims,ids=select(q.astype(np.float64),k.astype(np.float64));z=(q.astype(np.float64)@k.astype(np.float64).T/np.sqrt(128)).astype(np.float32)
            row=dict(dimensions=dims.tolist(),candidates=ids.tolist(),active_Q_heads=qpg,
                QK_sha256=hashlib.sha256(q.tobytes()+k.tobytes()).hexdigest(),seed=17+1000*g)
            for mode,idx in [('dense',np.arange(2048)),('screen_full',ids)]:
                running=np.full(qpg,-np.inf);changes=[]
                for b in range(len(idx)//32):
                    new=np.maximum(running,z[:,idx[b*32:(b+1)*32]].max(1));changes.append(int((new>running).sum()) if b else 0);running=new
                row[mode+'_max_changes']=changes
            assert len(ids)==128 and len(set(ids))==128 and set(range(2016,2048))<=set(ids)
            rows.append(row)
        fixtures[key]=rows
    f=out/'inputs/SHAPE_FIXTURES.json';f.write_bytes((json.dumps(fixtures,indent=2)+'\n').encode())
    sources['inputs/SHAPE_FIXTURES.json']=dict(generated='synthetic BF16 Q/K,seed17+1000*group,active-head SparQ rule',sha256=hashlib.sha256(f.read_bytes()).hexdigest())
    manifest=dict(status='prepared_not_simulated',sources=sources,model_weights_downloaded=False,
        private_sources_must_not_be_published=True,reference_sampler='old ab_both/P8 trace,not new-model score statistics',
        comparison='fixed4Q-slot initial mapping; inactive-slot cycles/energy conservatively retained')
    (out/'EXECUTION_MANIFEST.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
    print(json.dumps(dict(status='prepared',files=len(sources),root=str(out),fixture_sha256=sources['inputs/SHAPE_FIXTURES.json']['sha256'])))

if __name__=='__main__':main()
