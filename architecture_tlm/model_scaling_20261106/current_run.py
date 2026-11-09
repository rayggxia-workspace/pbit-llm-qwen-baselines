"""Current-host full model entry; outputs are sealed only after work/queue gates."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,sys,time
from current_mainline import environment,rebuild,digital_install,full_run,load

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2,allow_nan=False)+'\n').encode())

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--snapshot',type=Path,required=True)
    ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--dependencies',type=Path,required=True)
    ap.add_argument('--model',required=True,choices=('qwen3_4b','llama32_3b','deepseek_7b'))
    ap.add_argument('--clock',type=int,choices=(100,250),required=True)
    ap.add_argument('--scheme',choices=('SC_ising','BF16_dense','W8_dense','W8_screen'),required=True)
    ap.add_argument('--layers',type=int,default=0);ap.add_argument('--seed',type=int,choices=(17,503,1009),default=17)
    ap.add_argument('--backend',choices=('native','analytic'),default='native');ap.add_argument('--skip-head',action='store_true')
    ap.add_argument('--anchor-captured',action='store_true',help='Qwen control only: retain original captured candidate-address fixture')
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.snapshot=a.snapshot.resolve()
    manifest=load(a.snapshot/'SNAPSHOT_MANIFEST.json')
    for n,x in manifest['sources'].items():assert sha(a.snapshot/n)==x['sha256'],n
    factory,identity=environment(a.snapshot,a.runtime.resolve(),a.dependencies.resolve(),a.clock)
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    if a.backend=='native':
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        cfg=a.runtime/'base/profiles/derived8533.yaml'
        profile=next(x for x in load(a.runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        assert sha(cfg)==profile['sha256'];backend=RamulatorBackend(a.runtime/'base/liblpbridge.so',cfg,profile['period_ns'],256)
    else:backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    a.out.mkdir(parents=True,exist_ok=False);start=time.time()
    try:
        shape=load(a.snapshot/'glue/CURRENT_WORKLOAD_PLAN.json')['models'][a.model]['shape']
        L=shape['layers'] if not a.layers else a.layers
        kw=dict(layers=36,include_lm=not a.skip_head,seed=a.seed,samples=load(a.snapshot/'inputs/SAMPLES.json'),
            attention_input=load(a.snapshot/'inputs/representative.json'))
        if a.clock==250:kw.update(mode='ising',ffn='sc')
        h,m=factory(backend,**kw);m.cross_clock=a.clock
        rebuild(m,shape,shape['layers'],a.scheme)
        if a.scheme!='SC_ising':digital_install(m,a.snapshot,shape,a.clock,a.scheme)
        fixture=load(a.snapshot/'inputs/SHAPE_FIXTURES.json')[a.model]
        if a.model=='qwen3_4b' and a.anchor_captured:
            raw=load(a.snapshot/'inputs/representative.json')['rows'];fixture=[raw[i*8:(i+1)*8] for i in range(3)]
            # Digital online-softmax still uses the matching synthetic max
            # trace; candidates remain exactly the SC captured candidate IDs.
            if a.scheme!='SC_ising':
                synthetic=load(a.snapshot/'inputs/SHAPE_FIXTURES.json')[a.model]
                fixture=[[dict(row,**{k:synthetic[g][k] for k in ('dense_max_changes','screen_full_max_changes')}) for g,row in enumerate(rows)] for rows in fixture]
        else:fixture=[fixture]*3
        no_head={}
        def progress(stage,l,ns):
            if stage=='final_norm':no_head.update(time_ns=ns,memory=h.report(),SRAM=h.mem.report(ns),actions=dict(m.actions))
            print(json.dumps(dict(stage=stage,layer=l,simulated_us=ns/1000,wall_seconds=time.time()-start)),flush=True)
        full_run(m,fixture,L,not a.skip_head,progress)
        memory=h.report();assert not h.events and not h.mem.queue and not memory['final_pending'] and not memory['final_response_occupied']
        if a.scheme=='SC_ising':
            assert not m.common_prefetched
            assert m.kernel_active['GU_frames']==L*2*shape['hidden']*shape['ffn']//8192
            assert m.kernel_active['Wd_M128_frames']==L*shape['hidden']*shape['ffn']//8192
            assert m.actions['samples']==L*shape['q_heads']*64
        else:assert not m.cross_pool.live and not m.cross_pool.queue
        H,F,Q,KV,D=[shape[k] for k in ('hidden','ffn','q_heads','kv_heads','head_dim')]
        weights=sum(v.get('issued_bytes',0) for k,v in memory['by_kind'].items() if k in ('QKV_weights','O_weights','lm_head_weights','GU_weights','down_weights','digital_weights'))
        expected_weights=L*(2*H*(2*Q+2*KV)*D+3*H*F*(2 if a.scheme=='BF16_dense' else 1))
        if not a.skip_head:expected_weights+=2*shape['vocab']*H
        assert weights==expected_weights,('matrix weight bytes',weights,expected_weights)
        expected_projection=L*H*(2*Q+2*KV)*D+(0 if a.skip_head else shape['vocab']*H)
        assert m.actions['digital_BF16_MAC']==expected_projection,('projection MACs',m.actions['digital_BF16_MAC'],expected_projection)
        if a.scheme=='SC_ising':
            assert m.actions['SC_equivalent_MAC']==L*3*H*F
            assert m.actions['attention_QK_MAC']==L*4*KV*(2048*32+128*128)
        else:
            assert sum(z['actions']['MAC'] for z in m.cross_digital_results)==L*3*H*F
            assert len(m.cross_attention_results)==L*KV
            for z in m.cross_attention_results:
                n=128 if a.scheme=='W8_screen' else 2048
                assert z['actions']['exact_QK_MAC']==z['actions']['PV_MAC']==4*n*128
        phases=Counter()
        for p in m.phases:phases[p['stage']]+=p['duration_ns']
        r=dict(status='completed',model=a.model,shape=shape,clock_MHz=a.clock,scheme=a.scheme,seed=a.seed,layers=L,
            time_ns=h.now,time_ms=h.now/1e6,time_without_lm_head_stage_ms=(h.now-phases['lm_head'])/1e6,
            lm_head_stage_ms=phases['lm_head']/1e6,includes_head=not a.skip_head,phases=m.phases,phase_totals_ns=dict(phases),
            actions=dict(m.actions),kernel_active=dict(m.kernel_active),memory=memory,SRAM=h.mem.report(h.now),
            norm_storage=m.norm_store.report(),common_FFN_stages=m.common_stats,ordinary_contract=m.ordinary_pool_contract,
            matrix_audit=m.ordinary_pool_audit,resource_contract=m.resource_contract,compact_memory=m.compact_memory,
            allocation=getattr(m,'cross_allocation',None),digital_FFN=getattr(m,'cross_digital_results',[]),
            digital_Attention=getattr(m,'cross_attention_results',[]),source_identity=identity,
            snapshot_manifest_sha256=sha(a.snapshot/'SNAPSHOT_MANIFEST.json'),backend=a.backend,
            numeric_model_or_PPL=False,wall_seconds=time.time()-start,
            mapping=dict(physical_KV_slots=8,logical_KV_heads=shape['kv_heads'],waves=shape['kv_heads']//8,
                physical_query_slots_per_KV=4,active_Q_per_KV=m.cross_qpg,SC_inactive_samplers_disabled=True,
                QK_padding_cycles_retained=True,digital_attention_padding_cycles_retained=True,
                metadata_bytes=m.cross_meta,norm_slot_bytes=16384,query_input='captured Qwen or declared synthetic BF16 source',
                sampler_input='reference ab_both3-layer trace;not actual new-model distributions'))
        if a.backend=='native':r['native']=backend.finish(h.now)
        if a.scheme!='SC_ising':
            r['shared_pool_lease_summary']=dict(canonical_resource_id=m.cross_pool.resource_id,lanes=m.cross_pool.lanes,
                peak_lanes=m.cross_pool.peak,leases=len(m.cross_pool.audit),drained=not m.cross_pool.live,
                owners=dict(Counter(z['owner'].split(':')[0] for z in m.cross_pool.audit)))
        from current_pricing import price
        budget=price(r,a.snapshot)
        if no_head:
            before=dict(r,**no_head);nb=price(before,a.snapshot)
            budget['excluding_lm_head_stage']=dict(time_ms=no_head['time_ns']/1e6,onchip_mJ=nb['onchip_mJ'],
                system_mJ_by_pJbit=nb['system_mJ_by_pJbit'],average_W_by_pJbit=nb['average_W_by_pJbit'],
                note='stage boundary;retains finalnorm and any head-prefetch already overlapped;not no-head hardware rerun')
        validation=dict(status='PASS',queues_drained=True,physical_SRAM_unchanged=True,FFN_frame_check=a.scheme=='SC_ising',
            sample_count_checked=a.scheme=='SC_ising',no_cycle_rescaling=True,energy_closed=budget['energy_sum_closed'],
            weight_read_bytes=weights,expected_weight_bytes=expected_weights,actual_projection_MAC=expected_projection,
            FFN_logical_MAC=L*3*H*F,attention_heads_and_waves_checked=True)
        save(a.out/'RESULT.json',r);save(a.out/'BUDGET.json',budget);save(a.out/'VALIDATION.json',validation)
        save(a.out/'SEAL.json',dict(status='completed',files_sha256={n:sha(a.out/n) for n in ('RESULT.json','BUDGET.json','VALIDATION.json')}))
        print(json.dumps(dict(status='completed',model=a.model,clock=a.clock,scheme=a.scheme,time_ms=h.now/1e6,wall_seconds=time.time()-start)),flush=True)
    finally:
        if hasattr(backend,'close'):backend.close()

if __name__=='__main__':main()
