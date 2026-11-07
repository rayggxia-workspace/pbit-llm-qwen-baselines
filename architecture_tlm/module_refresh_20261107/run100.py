"""Complete first-layer baseline/refreshed transaction pair, analytic DRAM."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys,time

def load(p): return json.loads(Path(p).read_bytes())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v): Path(p).write_bytes((json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())

def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--project',type=Path,required=True)
    p.add_argument('--attention-source',type=Path)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();checkout=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('refresh100_environment',
        checkout/'architecture_tlm/ffn6_100mhz_20261107/replay.py')
    env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
    _,owner,identity=env.setup(a.project,checkout)
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    from architecture_tlm.ffn6_100mhz_20261107.ingress16 import make_model as baseline
    from architecture_tlm.module_refresh_20261107.host100 import make_model as refreshed
    from architecture_tlm.module_refresh_20261107.bindings import core_budget
    inp=a.project/'tmp/attention-compare-issue198-20261027/work/rayggxia/198/attention_tlm_20261105/runtime'
    a.out.mkdir(parents=True,exist_ok=False);rows={}
    for label,make in [('baseline',baseline),('refreshed',refreshed)]:
        start=time.time()
        extra=dict(attention_source=a.attention_source) if label=='refreshed' else {}
        h,m=make(AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606),
            owner_install=owner.install,samples=load(inp/'SAMPLES.json'),layers=36,
            include_lm=False,seed=17,attention_input=load(inp/'representative.json'),**extra)
        m.model['layers']=1;phase=m.phase
        def progress(stage,jobs,layer):
            r=phase(stage,jobs,layer)
            print(json.dumps(dict(case=label,stage=stage,time_us=h.now/1000,
                                  wall_seconds=time.time()-start)),flush=True)
            return r
        m.phase=progress;r=m.run();memory=h.report()
        assert not h.events and not h.mem.queue and not memory['final_pending']
        assert not memory['final_response_occupied'] and len(h.free_slots)==256
        r.update(status='completed',case=label,time_ns=h.now,scope='cold complete layer+embedding,no lm_head;36-layer address allocation',
            memory=memory,SRAM=h.mem.report(h.now),source_identity=identity,
            FFN_core_budget=core_budget(m.kernel_active,h.now,6,100),
            ordinary_contract=m.ordinary_pool_contract,matrix_audit=m.ordinary_pool_audit,
            source_sha256={f.name:sha(f) for f in Path(__file__).parent.glob('*') if f.is_file()},
            backend='analytic136.4606GB/s30ns',new_PPL=False,new_PPA=False)
        save(a.out/(label+'.json'),r);save(a.out/(label+'_SEAL.json'),dict(sha256=sha(a.out/(label+'.json'))))
        rows[label]=r
    old,new=rows['baseline'],rows['refreshed']
    assert old['kernel_active']==new['kernel_active']
    for k in ('digital_BF16_MAC','attention_QK_MAC','PV_ADD','samples','unique_V','GU_logical_R8_ports','NL_logical_R8_ports'):
        assert old['actions'].get(k,0)==new['actions'].get(k,0),k
    for kind,v in old['memory']['by_kind'].items():
        for key in ('issued_bytes','issued_address_sum','issued_address_xor'):
            assert v.get(key,0)==new['memory']['by_kind'][kind].get(key,0),(kind,key)
    assert not any(x['stage']=='wide_score_front_allowance' for x in new['phases'])
    save(a.out/'SUMMARY.json',dict(status='PASS',baseline_us=old['time_ns']/1000,
        refreshed_us=new['time_ns']/1000,change_percent=(new['time_ns']/old['time_ns']-1)*100,
        FFN_core_budget=new['FFN_core_budget'],arithmetic_samples_external_addresses_equal=True,
        current100_ingress_KiB=16,scope=new['scope'],backend=new['backend'],
        whole_native_LPDDR_token=False,whole_token_time_ms=None,
        raw=[dict(name=k,sha256=sha(a.out/(k+'.json'))) for k in rows]))
    print(json.dumps(dict(status='PASS',old_us=old['time_ns']/1000,new_us=new['time_ns']/1000)),flush=True)

if __name__=='__main__': main()
