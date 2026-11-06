"""Replay the existing complete probability actors with finite norm streaming."""
from pathlib import Path
import argparse
import hashlib
import json
import time
from .bootstrap import use_runtime


def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_bytes((json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--profile',choices=('resident_2p5','stream_2p5','stream_2m'),required=True)
    p.add_argument('--backend',choices=('native','analytic'),default='native')
    p.add_argument('--seed',type=int,choices=(17,503,1009),default=17)
    p.add_argument('--prefix-layers',type=int,default=0)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.prefix_layers not in (0,2):p.error('only complete or two-layer preflight')
    ident=use_runtime(args.runtime)
    from .model import make_model
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    from architecture_tlm.digital_fair_20261105.joint_handoff.accounting import price
    if args.backend=='analytic':
        backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    else:
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        profile=next(x for x in load(args.runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        cfg=args.runtime/'base/profiles/derived8533.yaml'
        if sha(cfg)!=profile['sha256']:raise ValueError('memory profile changed')
        binary=args.runtime/'base/liblpbridge.so'
        ident.update(memory_config_sha256=sha(cfg),bridge_sha256=sha(binary))
        backend=RamulatorBackend(binary,cfg,profile['period_ns'],256)
    args.out.mkdir(parents=True,exist_ok=False)
    started=time.time()
    try:
        attention=load(args.runtime/'inputs/representative.json')
        samples=load(args.runtime/'inputs/SAMPLES.json')
        ident['input_sha256']={n:sha(args.runtime/'inputs'/n) for n in ('representative.json','SAMPLES.json')}
        h,m=make_model(backend,profile=args.profile,mode='ising',ffn='sc',samples=samples,
            layers=36,include_lm=not args.prefix_layers,seed=args.seed,attention_input=attention)
        if args.prefix_layers:m.model['layers']=args.prefix_layers
        phase=m.phase
        def progress(stage,generators,layer):
            r=phase(stage,generators,layer)
            if stage in ('QKV','attention','NL_Wd','lm_head'):
                print(json.dumps(dict(event='phase_completed',stage=stage,layer=layer,
                    simulated_ms=h.now*1e-6,wall_seconds=time.time()-started)),flush=True)
            return r
        m.phase=progress
        result=m.run()
        result.update(status='completed',scope='prefix2_preserve36allocation' if args.prefix_layers else 'whole36+lm_head',
            simulated_ms=h.now*1e-6,simulated_chip_cycles=h.now/10,memory=h.report(),
            source_identity=ident,backend=args.backend,wall_seconds=time.time()-started,
            PPL_measured=False,PPA_measured=False,numeric_parameter_bytes_changed=False,
            timing_workload='same three captured Attention layers modulo3 as Issue236')
        if result['memory']['final_pending'] or result['memory']['final_response_occupied'] or h.mem.queue:
            raise RuntimeError('undrained memory activity')
        if args.backend=='native':
            result['native']=backend.finish(h.now)
            n=result['memory']['counts']
            assert result['native']['counts']['logical64_completed']*64==n['dram_read_bytes']+n['dram_write_bytes']
        assert all(a<=b for a,b in zip(h.mem.bank_allocated,h.mem.bank_depths))
        if not args.prefix_layers and args.profile!='resident_2p5':
            assert result['norm_storage_contract']['streamed_bytes']==392192
            assert result['norm_storage_contract']['load_counts']=={i:1 for i in range(37)}
        budget=price(result,load(args.runtime/'PRICES.json'),load(args.runtime/'architecture_tlm/digital_fair_20261105/LATEST_SC_PRICES.json'))
        # Same logic instances; only measured-macro SRAM replication changes.
        budget['original_2p5_target_area55_mm2']=budget['covered_area_target55_mm2']
        budget['norm_memory_policy']=args.profile
        budget['covered_area_target55_mm2']=67.54144608182283-(2621440-h.mem.capacity)/4096*.03322622205*.81
        budget['covered_area_gap_percent']=(budget['covered_area55_mm2']/budget['covered_area_target55_mm2']-1)*100
        assert abs(sum(budget['covered_areas55_mm2'].values())-budget['covered_area55_mm2'])<1e-8
        assert abs(sum(budget['onchip_components_mJ'].values())-budget['covered_onchip_mJ'])<1e-8
        save(args.out/'RESULT.json',result);save(args.out/'BUDGET.json',budget)
        save(args.out/'SEAL.json',dict(result_sha256=sha(args.out/'RESULT.json'),budget_sha256=sha(args.out/'BUDGET.json'),
            source_files_sha256={f.name:sha(f) for f in sorted(Path(__file__).parent.glob('*.py'))},source_identity=ident))
        print(json.dumps(dict(status='completed',profile=args.profile,scope=result['scope'],
            simulated_ms=result['simulated_ms'],area55_mm2=budget['covered_area55_mm2'],wall_seconds=result['wall_seconds'])),flush=True)
    finally:
        if hasattr(backend,'close'):backend.close()


if __name__=='__main__':main()
