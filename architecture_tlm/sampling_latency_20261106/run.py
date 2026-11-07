from pathlib import Path
import argparse,hashlib,json,time
from .model import make_model
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())

def main(argv,runtime,identity):
    p=argparse.ArgumentParser();p.add_argument('--gu',type=int,default=8);p.add_argument('--wd',type=int,default=32)
    p.add_argument('--prefix-layers',type=int,choices=(0,2),default=2)
    p.add_argument('--seed',type=int,default=17);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
    profile=next(x for x in load(runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
    cfg=runtime/'base/profiles/derived8533.yaml';binary=runtime/'base/liblpbridge.so'
    assert sha(cfg)==profile['sha256'];backend=RamulatorBackend(binary,cfg,profile['period_ns'],256)
    identity.update(memory_config_sha256=sha(cfg),bridge_sha256=sha(binary))
    a.out.mkdir(parents=True,exist_ok=False);start=time.time()
    try:
        attention=load(runtime/'inputs/representative.json');samples=load(runtime/'inputs/SAMPLES.json')
        identity['input_sha256']={n:sha(runtime/'inputs'/n) for n in ('representative.json','SAMPLES.json')}
        h,m=make_model(backend,gu_samples=a.gu,wd_samples=a.wd,mode='ising',ffn='sc',samples=samples,
            layers=36,include_lm=not a.prefix_layers,seed=a.seed,attention_input=attention)
        if a.prefix_layers:m.model['layers']=a.prefix_layers
        original=m.phase
        def progress(stage,generators,layer):
            r=original(stage,generators,layer)
            if stage in ('QKV','attention','GU','NL_Wd','lm_head'):
                print(json.dumps(dict(event='phase_completed',stage=stage,layer=layer,simulated_ms=h.now*1e-6,wall_seconds=time.time()-start)),flush=True)
            return r
        m.phase=progress;result=m.run()
        result.update(status='completed',scope='prefix2_preserve36allocation' if a.prefix_layers else 'whole36+lm_head',
            simulated_ms=h.now*1e-6,simulated_chip_cycles=h.now/10,memory=h.report(),source_identity=identity,
            backend='native',wall_seconds=time.time()-start,PPL_measured=False,PPA_measured=False,
            energy_priced=False,energy_note='existing C20 T64 power price must not be transplanted toT8/T32')
        assert not result['memory']['final_pending'] and not result['memory']['final_response_occupied'] and not h.mem.queue
        result['native']=backend.finish(h.now)
        c=result['memory']['counts'];assert result['native']['counts']['logical64_completed']*64==c['dram_read_bytes']+c['dram_write_bytes']
        save(a.out/'RESULT.json',result)
        save(a.out/'SEAL.json',dict(result_sha256=sha(a.out/'RESULT.json'),source_identity=identity,
            source_files_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')}))
        print(json.dumps(dict(status='completed',gu=a.gu,wd=a.wd,scope=result['scope'],timing=result['decode_timing_ms'],wall_seconds=result['wall_seconds'])),flush=True)
    finally:backend.close()
