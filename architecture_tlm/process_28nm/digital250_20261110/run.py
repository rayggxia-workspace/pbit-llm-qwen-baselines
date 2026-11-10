"""Opt-in full digital Qwen controls:BF16dense,W8dense,W8screen."""
from pathlib import Path
from collections import Counter
import argparse,copy,hashlib,json,sys,time
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from model import build,load
from pricing import price
from pricing250 import split_head
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2,allow_nan=False)+'\n').encode())

def main():
    ap=argparse.ArgumentParser()
    for k in ('snapshot','runtime','dependencies','bindings','macros','out'):ap.add_argument('--'+k,type=Path,required=True)
    ap.add_argument('--scheme',choices=('BF16_dense','W8_dense','W8_screen'),required=True)
    ap.add_argument('--layers',type=int,default=1);ap.add_argument('--head',action='store_true')
    ap.add_argument('--head-probe-rows',type=int);ap.add_argument('--backend',choices=('analytic','native'),default='analytic')
    ap.add_argument('--construct-only',action='store_true');a=ap.parse_args()
    assert 1<=a.layers<=36
    b=load(a.bindings);cfg=load(a.macros);assert b['clock_MHz']==cfg['clock_MHz']==250
    frozen=load(a.snapshot/'SNAPSHOT_MANIFEST.json')
    for n,x in frozen['sources'].items():assert sha(a.snapshot/n)==x['sha256'],n
    import importlib.util
    spec=importlib.util.spec_from_file_location('p28_digital_boot',a.snapshot/'glue/current_mainline.py')
    boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
    boot.environment(a.snapshot,a.runtime,a.dependencies,250)
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    if a.backend=='analytic':backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    else:
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        profile=next(x for x in load(a.runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        yaml=a.runtime/'base/profiles/derived8533.yaml';assert sha(yaml)==profile['sha256']
        backend=RamulatorBackend(a.runtime/'base/liblpbridge.so',yaml,profile['period_ns'],256)
    a.out.mkdir(parents=True,exist_ok=False);start=time.time();source_hashes={p.name:sha(p) for p in HERE.glob('*.py')}
    try:
        h,m,main,shape,identity=build(a.snapshot,a.runtime,a.dependencies,b,cfg,backend,a.scheme,a.layers,a.head)
        save(a.out/'CONSTRUCTION.json',dict(status='PASS',contract=m.digital28_contract,
            bindings_sha256=sha(a.bindings),macro_sha256=sha(a.macros),code_sha256=source_hashes))
        print(json.dumps(dict(stage='constructed',allocation=m.cross_allocation,scheme=a.scheme)),flush=True)
        if a.construct_only:return
        if a.head_probe_rows is not None:
            assert a.head and 1<=a.head_probe_rows<=151936;m.model['vocab']=a.head_probe_rows
        fixture=[load(a.snapshot/'inputs/SHAPE_FIXTURES.json')['qwen3_4b']]*3
        prefix={};prefix_budget={}
        def snapshot():
            return dict(status='completed',scheme=a.scheme,clock_MHz=250,time_ns=h.now,time_ms=h.now/1e6,layers=a.layers,
                actions=dict(m.actions),memory=h.report(),SRAM=h.mem.report(h.now),kernel_active={},macro_config=cfg,
                phases=copy.deepcopy(m.phases),contract=m.digital28_contract,source_identity=identity,
                FFN=[x['actions'] for x in m.cross_digital_results],Attention=[x['actions'] for x in m.cross_attention_results])
        def progress(stage,l,ns):
            print(json.dumps(dict(stage=stage,layer=l,simulated_us=ns/1000,wall_seconds=time.time()-start)),flush=True)
            if stage=='final_norm':
                prefix.update(snapshot());prefix_budget.update(price(m,prefix,b))
        main.full_run(m,fixture,a.layers,a.head,progress)
        r=snapshot();L=a.layers;assert not h.events and not h.mem.queue
        assert not h.report()['final_pending'] and not h.report()['final_response_occupied']
        assert not m.cross_pool.live and not m.cross_pool.queue and not m.cross_pool.used
        assert len(m.cross_digital_results)==L and len(m.cross_attention_results)==L*8
        fa=Counter();aa=Counter()
        for x in m.cross_digital_results:fa.update(x['actions'])
        for x in m.cross_attention_results:aa.update(x['actions'])
        assert fa['MAC']==L*74711040
        assert fa['DRAM_weight_bytes']==L*74711040*(2 if a.scheme=='BF16_dense' else 1)
        assert fa['SwiGLU']==L*9728
        candidates=128 if a.scheme=='W8_screen' else 2048
        assert aa['exact_QK_MAC']==aa['PV_MAC']==L*32*candidates*128
        assert aa['completed_groups']==8*L
        assert not m.actions['samples'] and not m.kernel_active['GU_frames'] and not m.kernel_active['Wd_M128_frames']
        r.update(scope='full' if L==36 and a.head and a.head_probe_rows is None else 'layer_or_partial',
            includes_lm_head=a.head,head_probe_rows=a.head_probe_rows,full_vocab=151936,backend=a.backend,
            without_head_prefix=prefix or None,numeric_model_or_PPL=False,physical_wholechip_verified=False,
            code_sha256=source_hashes,bindings_sha256=sha(a.bindings),macro_sha256=sha(a.macros),
            snapshot_manifest_sha256=sha(a.snapshot/'SNAPSHOT_MANIFEST.json'),wall_seconds=time.time()-start)
        if a.backend=='native':r['native']=backend.finish(h.now)
        budget=price(m,r,b)
        if prefix:budget['lm_head_split']=split_head(budget,prefix_budget,h.now,prefix['time_ns'])
        assert source_hashes=={p.name:sha(p) for p in HERE.glob('*.py')}
        validation=dict(status='PASS',queues_drained=True,shared_pool=True,SC_hardware_inactive=True,
            FFN_work=fa['MAC'],FFN_weight_bytes=fa['DRAM_weight_bytes'],QK_PV_work=True,SRAM832=True,
            actual_bank_ports=True,area_not_exceeding_target=budget['conditional_subsystem_area_mm2']<=6.480302546479157,
            scope='hardwaretransactions;not numericalPPL or physicalchip')
        for n,x in [('RESULT.json',r),('BUDGET.json',budget),('VALIDATION.json',validation)]:save(a.out/n,x)
        save(a.out/'SEAL.json',dict(status='completed',files_sha256={n:sha(a.out/n) for n in ('RESULT.json','BUDGET.json','VALIDATION.json','CONSTRUCTION.json')}))
        print(json.dumps(dict(status='completed',scheme=a.scheme,scope=r['scope'],time_ms=r['time_ms'],wall_seconds=r['wall_seconds'])),flush=True)
    finally:
        if hasattr(backend,'close'):backend.close()

if __name__=='__main__':main()
