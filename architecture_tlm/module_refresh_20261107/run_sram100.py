"""Complete cold-layer SRAM comparison; finite current100 Attention and FFN."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,subprocess,time

def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def setup(project,checkout):
    p=checkout/'architecture_tlm/ffn6_100mhz_20261107/replay.py'
    spec=importlib.util.spec_from_file_location('sram100_environment',p)
    env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
    return env.setup(project,checkout)

SOURCES=('sram1216_20261106/model.py','sampling_latency_20261106/model.py',
    'ffn6_100mhz_20261107/model.py','ffn6_100mhz_20261107/ingress16.py',
    'qk_supply_100mhz_20261107/model.py','module_refresh_20261107/host100.py',
    'module_refresh_20261107/run_sram100.py','module_refresh_20261107/test_sram100.py')

def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--configuration',choices=('compact1216','compact1184','compact1056','compact1088bw'),default='compact1088bw')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();checkout=Path(__file__).resolve().parents[2]
    _,owner,identity=setup(a.project,checkout)
    from architecture_tlm.module_refresh_20261107.host100 import make_model
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    inp=a.project/'tmp/attention-compare-issue198-20261027/work/rayggxia/198/attention_tlm_20261105/runtime'
    identity['execution_files_sha256']={f:sha(checkout/'architecture_tlm'/f) for f in SOURCES}
    identity['local_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
    a.out.mkdir(parents=True,exist_ok=False);start=time.time()
    h,m=make_model(AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606),
        owner_install=owner.install,sram_configuration=a.configuration,
        samples=load(inp/'SAMPLES.json'),layers=36,include_lm=False,seed=17,
        attention_input=load(inp/'representative.json'))
    m.model['layers']=1;old=m.phase
    def progress(stage,jobs,layer):
        value=old(stage,jobs,layer)
        print(json.dumps(dict(stage=stage,time_us=h.now/1000,wall_seconds=time.time()-start)),flush=True)
        return value
    m.phase=progress;r=m.run();memory=h.report()
    assert not h.events and not h.mem.queue and not memory['final_pending']
    assert not memory['final_response_occupied'] and len(h.free_slots)==256
    assert not m.common_prefetched
    assert r['kernel_active']==dict(GU_frames=6080,Wd_M128_frames=3040)
    assert r['actions']['GU_logical_R8_ports']==6080*64*16
    assert r['actions']['NL_logical_R8_ports']==3040*64*3*32
    r.update(status='completed',configuration=a.configuration,time_ns=h.now,
        simulated_ms=h.now/1e6,chip_cycles=h.now/10,scope='cold complete layer0+embedding,no head;36-layer address allocation',
        memory=memory,SRAM=h.mem.report(h.now),compact_memory=m.compact_memory,
        source_identity=identity,backend='analytic136.4606GB/s30ns',new_PPA=False,
        new_PPL=False,whole_native_token=False,wall_seconds=time.time()-start)
    reference=load(Path(__file__).with_name('RESULTS_100.json'))
    areas=reference['areas55_proxy_mm2'].copy();areas['shared_SRAM']=r['SRAM']['area55eq_mm2']
    budget=dict(areas55_proxy_mm2=areas,covered_area55_proxy_mm2=sum(areas.values()),
        SRAM_dynamic_mJ=r['SRAM']['dynamic_mJ'],SRAM_leakage_mJ=r['SRAM']['leakage_mJ'],
        FFN_core_budget=r['FFN_core_budget'],whole_chip_energy_mJ=None,
        boundary='same reference module costs; only actual SRAM macro count replaced; no new PPA',
        area_factor_already_applied=.81)
    save(a.out/'RESULT.json',r);save(a.out/'BUDGET.json',budget)
    save(a.out/'SEAL.json',dict(status='completed',result_sha256=sha(a.out/'RESULT.json'),
        budget_sha256=sha(a.out/'BUDGET.json'),source_identity=identity))
    print(json.dumps(dict(status='completed',configuration=a.configuration,ms=h.now/1e6,
        area55_mm2=budget['covered_area55_proxy_mm2'],wall_seconds=time.time()-start)),flush=True)

if __name__=='__main__':main()
