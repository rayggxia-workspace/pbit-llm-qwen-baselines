from pathlib import Path
import argparse,hashlib,json,math,time
from .model import CASES,make_model

def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def main(argv,runtime,identity):
    p=argparse.ArgumentParser()
    p.add_argument('--configuration',choices=CASES,required=True)
    p.add_argument('--backend',choices=('analytic','native'),default='native')
    p.add_argument('--seed',type=int,choices=(17,503,1009),default=17)
    p.add_argument('--prefix-layers',type=int,choices=(0,2),default=2)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(argv)
    if a.backend=='analytic':
        from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
        backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    else:
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        profile=next(x for x in load(runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        config=runtime/'base/profiles/derived8533.yaml';assert sha(config)==profile['sha256']
        binary=runtime/'base/liblpbridge.so'
        identity.update(memory_config_sha256=sha(config),bridge_sha256=sha(binary))
        backend=RamulatorBackend(binary,config,profile['period_ns'],256)
    a.out.mkdir(parents=True,exist_ok=False);started=time.time()
    try:
        attention=load(runtime/'inputs/representative.json');samples=load(runtime/'inputs/SAMPLES.json')
        identity['input_sha256']={n:sha(runtime/'inputs'/n) for n in ('representative.json','SAMPLES.json')}
        h,m=make_model(backend,configuration=a.configuration,mode='ising',ffn='sc',samples=samples,
            layers=36,include_lm=not a.prefix_layers,seed=a.seed,attention_input=attention)
        if a.prefix_layers:m.model['layers']=a.prefix_layers
        phase=m.phase
        def progress(stage,generators,layer):
            r=phase(stage,generators,layer)
            if stage in ('QKV','attention','NL_Wd','lm_head'):
                print(json.dumps(dict(event='phase_completed',stage=stage,layer=layer,
                    simulated_ms=h.now*1e-6,wall_seconds=time.time()-started)),flush=True)
            return r
        m.phase=progress;result=m.run()
        result.update(status='completed',configuration=a.configuration,
            scope='prefix2_preserve36allocation' if a.prefix_layers else 'whole36+lm_head',
            simulated_ms=h.now*1e-6,simulated_chip_cycles=h.now/10,memory=h.report(),
            source_identity=identity,backend=a.backend,wall_seconds=time.time()-started,
            PPL_measured=False,PPA_measured=False,numeric_parameter_bytes_changed=False)
        assert not result['memory']['final_pending'] and not result['memory']['final_response_occupied'] and not h.mem.queue
        if a.backend=='native':
            result['native']=backend.finish(h.now);c=result['memory']['counts']
            assert result['native']['counts']['logical64_completed']*64==c['dram_read_bytes']+c['dram_write_bytes']
        from architecture_tlm.digital_fair_20261105.joint_handoff.accounting import price
        prices=load(runtime/'PRICES.json')
        budget=price(result,prices,load(runtime/'architecture_tlm/digital_fair_20261105/LATEST_SC_PRICES.json'))
        fma=prices['digital']['fma16_c4'];ms=result['simulated_ms']
        budget['covered_areas55_mm2']['ordinary_BF16_FMA']=40*fma['area55_mm2']
        budget['onchip_components_mJ']['ordinary_BF16_FMA']=(result['actions']['digital_BF16_MAC']*fma['incremental_pJ']*1e-9+40*fma['idle_W']*ms)
        budget['covered_area55_mm2']=math.fsum(budget['covered_areas55_mm2'].values())
        budget['covered_onchip_mJ']=math.fsum(budget['onchip_components_mJ'].values())
        budget['covered_system_mJ_at4pJ']=budget['covered_onchip_mJ']+budget['external_mJ_by_pJ_per_bit']['4.0']
        budget['covered_system_W_at4pJ']=budget['covered_system_mJ_at4pJ']/ms
        budget['historical_area_target55_mm2']=budget.pop('covered_area_target55_mm2',None)
        budget.pop('covered_area_gap_percent',None)
        budget['area_matching_experiment']=False
        budget['comparison_limitations']+=['640 pool physical40FMA16; fixed128 final adders retained',
            'new compact address decoder/interconnect PPA not characterized; no quality measurement']
        save(a.out/'RESULT.json',result);save(a.out/'BUDGET.json',budget)
        save(a.out/'SEAL.json',dict(result_sha256=sha(a.out/'RESULT.json'),budget_sha256=sha(a.out/'BUDGET.json'),
            source_files_sha256={f.name:sha(f) for f in Path(__file__).parent.glob('*.py')},source_identity=identity))
        print(json.dumps(dict(status='completed',configuration=a.configuration,scope=result['scope'],
            simulated_ms=result['simulated_ms'],area55_mm2=budget['covered_area55_mm2'],wall_seconds=result['wall_seconds'])),flush=True)
    finally:
        if hasattr(backend,'close'):backend.close()
