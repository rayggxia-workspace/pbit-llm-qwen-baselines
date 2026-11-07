"""Paired full-shape FFN actors on current bank map; analytic external service."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys,time
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec)
    sys.modules[name]=obj;spec.loader.exec_module(obj);return obj
def setup(project,checkout):
    run=module('ffn6_qk_environment',checkout/'architecture_tlm/qk_supply_100mhz_20261107/run.py')
    runtime,owner,_,_,identity=run.environment(project,checkout)
    import architecture_tlm
    architecture_tlm.__path__=[str(checkout/'architecture_tlm'),*list(architecture_tlm.__path__)]
    from architecture_tlm.ffn6_100mhz_20261107.model import make_model
    return make_model,owner,identity
def main():
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True)
    p.add_argument('--cores',type=int,choices=(5,6,8,12),required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();checkout=Path(__file__).resolve().parents[2]
    make,owner,identity=setup(a.project,checkout)
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    h,m=make(backend,owner_install=owner.install,cores=a.cores,samples={},layers=36,include_lm=False,seed=17)
    a.out.mkdir(parents=True,exist_ok=False);start=time.time()
    # Same cold FFN boundary for all cores. Preserve36-layer allocation and
    # original shapes; no invented preloaded weights or warm norm state.
    for stage,jobs in [('metadata',[h.fetch('FFN_metadata',m.weight_bases[0,'metadata'],32768,m.vector,65536,'FFN_scale_metadata')]),
        ('GU',[m.sc_gu(0)]),('NL_Wd',[m.sc_down(0)])]:
        m.phase(stage,jobs,0)
        print(json.dumps(dict(stage=stage,cores=a.cores,time_us=h.now/1000,wall_s=time.time()-start)),flush=True)
    for row in m.common_stats:
        T=16 if row['mode']=='GU' else 32
        row['sample_core_ns']=row['frames']*(T+2)*10
        row['core_sampling_utilization']=row['sample_core_ns']/(a.cores*row['elapsed_ns'])
    assert not h.mem.queue and not m.common_prefetched
    memory=h.report();assert not memory['final_pending'] and not memory['final_response_occupied']
    counts=dict(m.actions);frames=m.kernel_active
    counts.update(GU_logical_R8_ports=frames['GU_frames']*64*16,
        NL_logical_R8_ports=frames['Wd_M128_frames']*192*32,
        common_R8_words=frames['GU_frames']*16+frames['Wd_M128_frames']*3*32)
    result=dict(status='completed',cores=a.cores,time_us=h.now/1000,phases=m.phases,stages=m.common_stats,
        actions=counts,memory=memory,SRAM=h.mem.report(h.now),contract=m.ffn6_contract,
        physical_map={r.name:dict(size=r.size,banks=list(r.banks)) for r in h.mem.regions.values()},
        external_backend='analytic136.4606GB/s30ns',scope='cold full-shape one-FFN actor pair; not complete token/nativeLPDDR',
        source_identity=identity,wall_seconds=time.time()-start,source_sha256={f.name:sha(f) for f in Path(__file__).parent.glob('*.py')},
        new_PPA=False,new_PPL=False)
    save(a.out/'RESULT.json',result);save(a.out/'SEAL.json',dict(result_sha256=sha(a.out/'RESULT.json'),source_sha256=result['source_sha256']))
    print(json.dumps(dict(status='completed',cores=a.cores,FFN_us=result['time_us'],wall_s=result['wall_seconds'])),flush=True)
if __name__=='__main__':main()
