"""Conditional28nm whole decode execution using existing finite storage engine."""
from pathlib import Path
import argparse,hashlib,json,sys,time
from collections import Counter
from whole_model import build,load
from whole_pricing import price

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_bytes((json.dumps(v,indent=2,allow_nan=False)+'\n').encode())

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--runtime',type=Path,required=True);p.add_argument('--dependencies',type=Path,required=True)
    p.add_argument('--bindings',type=Path,required=True);p.add_argument('--cores',type=int,required=True)
    p.add_argument('--macros',type=Path,help='default:WHOLE_CONFIG.json next to bindings')
    p.add_argument('--sram-latency-cycles',type=int,choices=(1,2,3))
    p.add_argument('--layers',type=int,default=1);p.add_argument('--head',action='store_true')
    p.add_argument('--head-probe-rows',type=int,help='explicit reducedvocab integrationprobe;not actualmodelhead')
    p.add_argument('--seed',type=int,choices=(17,503,1009),default=17)
    p.add_argument('--backend',choices=('analytic','native'),default='analytic')
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    binding=load(a.bindings);mhz=binding['clock_MHz'];assert mhz in (250,500)
    a.macros=a.macros or a.bindings.parent/'WHOLE_CONFIG.json';macros=load(a.macros)
    assert macros['clock_MHz']==mhz and macros['FMA_feedback_cycles']>=1 and macros['PV_feedback_cycles']>=1
    assert (macros['FMA_lanes'],macros['FMA_contexts'],macros['PV_ADD_per_head'])==(256,4,2)
    assert (macros['SRAM']['capacity_KiB'],macros['SRAM']['bank_count']) in ((960,240),(928,232),(832,208))
    a.sram_latency_cycles=a.sram_latency_cycles or macros['SRAM']['latency_cycles_default']
    assert a.sram_latency_cycles in (1,2,3)
    executed_code={n:sha(Path(__file__).parent/n) for n in ('run_whole.py','whole_model.py','whole_pricing.py','candidate_sram.py','sram_characterization.py')}
    assert a.cores in binding['FFN_candidate_core_counts']
    assert 1<=a.layers<=36
    assert a.head_probe_rows is None or (a.head and 1<=a.head_probe_rows<=151936)
    a.snapshot=a.snapshot.resolve();a.runtime=a.runtime.resolve();a.dependencies=a.dependencies.resolve()
    frozen=load(a.snapshot/'SNAPSHOT_MANIFEST.json')
    for n,x in frozen['sources'].items():assert sha(a.snapshot/n)==x['sha256'],n
    # Construct the backend after the frozen environment imports are available.
    import importlib.util
    s=importlib.util.spec_from_file_location('p28_loader',a.snapshot/'glue/current_mainline.py')
    loader=importlib.util.module_from_spec(s);s.loader.exec_module(loader)
    loader.environment(a.snapshot,a.runtime,a.dependencies,250)
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    if a.backend=='analytic':backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    else:
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        cfg=a.runtime/'base/profiles/derived8533.yaml';profile=next(x for x in load(a.runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        assert sha(cfg)==profile['sha256'];backend=RamulatorBackend(a.runtime/'base/liblpbridge.so',cfg,profile['period_ns'],256)
    a.out.mkdir(parents=True,exist_ok=False);started=time.time()
    try:
        h,m,host,shape,identity=build(a.snapshot,a.runtime,a.dependencies,binding,sha(a.bindings),backend,a.cores,a.sram_latency_cycles,macros,a.seed,a.head,a.layers)
        # Validate actualfull151936-vocabulary tiling structurally,including128row tail.
        head_tiles=m.matrix_tasks(0,'lm_head',151936,2560)
        assert sum(z[1] for z in head_tiles)==151936*2560
        assert sum(sum(n for _,n in z[0]) for z in head_tiles)==151936*2560*2
        assert max(sum(n for _,n in z[0]) for z in head_tiles)<=m.weight[0].size
        del head_tiles
        if a.head_probe_rows is not None:m.model['vocab']=a.head_probe_rows
        head_rows=a.head_probe_rows or 151936
        fixture=[load(a.snapshot/'inputs/SHAPE_FIXTURES.json')['qwen3_4b']]*3
        def progress(stage,l,ns):print(json.dumps(dict(stage=stage,layer=l,simulated_us=ns/1000,wall_seconds=time.time()-started)),flush=True)
        host.full_run(m,fixture,a.layers,a.head,progress)
        mem=h.report();sram=h.mem.report(h.now);L=a.layers
        assert not h.events and not h.mem.queue and not mem['final_pending'] and not mem['final_response_occupied']
        assert not m.p28_staging_busy and not m.common_prefetched
        assert m.kernel_active['GU_frames']==L*6080 and m.kernel_active['Wd_M128_frames']==L*3040
        assert m.actions['samples']==L*2048 and m.actions['PV_ADD']==L*262144
        assert m.actions['SC_equivalent_MAC']==L*74711040
        assert m.p28_counts['front_queries']==m.p28_counts['sampler_queries']==L*32
        assert m.p28_counts['scale64_groups']==L*304 and m.actions['common_state32_vectors']==L*36480
        assert m.p28_counts['codec_g8']==m.p28_counts['codec_u8']==L*9728 and m.p28_counts['codec_bf16']==L*2560
        for kind in ('read','write'):
            expected=sram['counts'][kind+'_words'] if macros['SRAM'][kind+'_pJ_per16B'] is None else 0
            assert sram['counts'].get('unpriced_'+kind+'_words',0)==expected
        assert sram['by_tag']['sampler_score_input']['read_words']==L*32*32
        weights=sum(v.get('issued_bytes',0) for k,v in mem['by_kind'].items() if k in ('QKV_weights','O_weights','lm_head_weights','GU_weights','down_weights'))
        assert weights==L*127139840+(2*2560*head_rows if a.head else 0)
        assert m.actions['digital_BF16_MAC']==L*26214400+(2560*head_rows if a.head else 0)
        assert m.actions['attention_QK_MAC']==L*2621440
        phases=Counter()
        for z in m.phases:phases[z['stage']]+=z['duration_ns']
        result=dict(status='completed',scope='full' if L==36 and a.head and a.head_probe_rows is None else 'layer_or_partial',model='Qwen3-4B',layers=L,
            process='TSMC28HPC+',clock_MHz=mhz,time_ns=h.now,time_ms=h.now/1e6,
            includes_lm_head=a.head,time_without_lm_head_stage_ms=(h.now-phases['lm_head'])/1e6,
            head_probe_rows=a.head_probe_rows,full_vocab_tiling_checked=151936,
            lm_head_stage_ms=phases['lm_head']/1e6,FFN_cores=a.cores,phases=m.phases,
            actions=dict(m.actions),process28_counts=dict(m.p28_counts),kernel_active=dict(m.kernel_active),
            memory=mem,SRAM=sram,common_FFN_stages=m.common_stats,ordinary_matrix_audit=m.ordinary_pool_audit,
            SRAM_layout_contract=m.candidate_sram_contract,
            resource_audit=m.resource_audit,seed=a.seed,backend=a.backend,
            bindings_sha256=sha(a.bindings),snapshot_manifest_sha256=sha(a.snapshot/'SNAPSHOT_MANIFEST.json'),source_identity=identity,
            macro_config=macros,macro_config_sha256=sha(a.macros),
            code_sha256=executed_code,
            assumptions=dict(SRAM_latency_cycles=a.sram_latency_cycles,SRAM_singleRW_16B_banks=sram['physical_banks'],
                SRAM28_characterized=macros['SRAM'].get('macro_characterized',False),
                SRAM_energy_area=macros['SRAM'].get('price_status'),DMA_clock_MHz=mhz,
                shared_FMA='256lanes/4contexts/II1;feedback andtail from macro_config;500timing/price pending',
                PV='2ADD/head;feedback from macro_config;PV28control/price pending',
                sampler_timing='ceil measured28 mean query cycles minus32 sharedloads;not real per-query timing trace',
                sampler_addresses='frozen reference address trace,not new p-bit simulation or PPL',
                vector='retained named cycle counts at selected core clock;28 price pending'),
            numeric_model_or_PPL=False,physical_wholechip_verified=False,wall_seconds=time.time()-started)
        if a.backend=='native':result['native']=backend.finish(h.now)
        budget=price(m,result,binding)
        assert all(sha(Path(__file__).parent/n)==v for n,v in executed_code.items()),'execution source changed:preserve as diagnostic,do not seal'
        validation=dict(status='PASS',queues_drained=True,FFN_frames=True,samples=True,PV_ADDs=True,
            conversions=True,S12_singlepass_reads=True,unpriced_SRAM_actions_preserved=True,weight_bytes=weights,
            no_total_time_scaling=True,no55nm_price_reuse=True,not_complete_system_PPA=True)
        save(a.out/'RESULT.json',result);save(a.out/'BUDGET.json',budget);save(a.out/'VALIDATION.json',validation)
        save(a.out/'SEAL.json',dict(status='completed',files_sha256={n:sha(a.out/n) for n in ('RESULT.json','BUDGET.json','VALIDATION.json')}))
        print(json.dumps(dict(status='completed',scope=result['scope'],MHz=mhz,cores=a.cores,time_ms=result['time_ms'],wall_seconds=time.time()-started)),flush=True)
    finally:
        if hasattr(backend,'close'):backend.close()

if __name__=='__main__':main()
