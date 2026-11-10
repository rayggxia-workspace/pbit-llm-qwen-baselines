"""Full finite transaction replay for Llama3.2-3B and DeepSeek7B."""
from pathlib import Path
from collections import Counter
import argparse,copy,hashlib,json,sys,time
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from model import build,price,load,sum_counters
from pricing250 import split_head
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2,allow_nan=False)+'\n').encode())

def main():
    ap=argparse.ArgumentParser()
    for n in ('snapshot','runtime','dependencies','bindings','macros','out'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--model',choices=('qwen3_4b','llama32_3b','deepseek_7b'),required=True)
    ap.add_argument('--scheme',choices=('SC_ising','BF16_dense','W8_dense','W8_screen'),required=True)
    ap.add_argument('--seed',type=int,choices=(17,503,1009),default=17)
    ap.add_argument('--layers',type=int);ap.add_argument('--head',action='store_true');ap.add_argument('--head-probe-rows',type=int)
    ap.add_argument('--backend',choices=('analytic','native'),default='analytic');ap.add_argument('--construct-only',action='store_true')
    a=ap.parse_args();model=load(HERE/'MODELS.json')['models'][a.model];shape=model['shape'];L=a.layers or shape['layers']
    assert 1<=L<=shape['layers']
    b=load(a.bindings);cfg=load(a.macros);assert b['clock_MHz']==cfg['clock_MHz']==250
    frozen=load(a.snapshot/'SNAPSHOT_MANIFEST.json')
    for n,x in frozen['sources'].items():assert sha(a.snapshot/n)==x['sha256'],n
    import importlib.util
    sp=importlib.util.spec_from_file_location('cross28_boot',a.snapshot/'glue/current_mainline.py')
    boot=importlib.util.module_from_spec(sp);sp.loader.exec_module(boot);boot.environment(a.snapshot,a.runtime,a.dependencies,250)
    from architecture_tlm.unified_v6.shared_memory import AnalyticDRAM
    if a.backend=='analytic':backend=AnalyticDRAM(latency_ns=30,bandwidth_GBs=136.4606)
    else:
        from architecture_tlm.digital_baselines_20261104.backend import RamulatorBackend
        profile=next(x for x in load(a.runtime/'base/profiles/PROFILES.json') if x['name']=='derived8533')
        yaml=a.runtime/'base/profiles/derived8533.yaml';assert sha(yaml)==profile['sha256']
        backend=RamulatorBackend(a.runtime/'base/liblpbridge.so',yaml,profile['period_ns'],256)
    a.out.mkdir(parents=True,exist_ok=False);start=time.time()
    source_hashes={str(p.relative_to(HERE.parent)):sha(p) for d in (HERE,HERE.parent/'digital250_20261110') for p in d.glob('*.py')}
    try:
        h,m,host,_,identity,model=build(a.snapshot,a.runtime,a.dependencies,b,sha(a.bindings),cfg,backend,a.model,a.scheme,L,a.head,a.seed)
        H,F,Q,KV,D,V=[shape[k] for k in ('hidden','ffn','q_heads','kv_heads','head_dim','vocab')]
        head_tasks=m.matrix_tasks(0,'lm_head',V,H)
        assert sum(x[1] for x in head_tasks)==V*H
        assert sum(sum(n for _,n in x[0]) for x in head_tasks)==V*H*2
        assert max(sum(n for _,n in x[0]) for x in head_tasks)<=m._pool(0,'lm_head')[0].size
        del head_tasks
        save(a.out/'CONSTRUCTION.json',dict(status='PASS',model=model,contract=m.cross28_contract,
            resource=m.resource_contract,SRAM=m.candidate_sram_contract,
            digital_allocation=getattr(m,'cross_allocation',None),full_vocab_tiling=True,source_hashes=source_hashes))
        print(json.dumps(dict(stage='constructed',model=a.model,scheme=a.scheme)),flush=True)
        if a.construct_only:return
        if a.head_probe_rows:
            assert a.head and a.head_probe_rows<=V;m.model['vocab']=a.head_probe_rows
        fixture=[load(a.snapshot/'inputs/SHAPE_FIXTURES.json')[a.model]]*3
        prefix={};prefix_budget={}
        def snapshot():
            return copy.deepcopy(dict(status='completed',model_key=a.model,model_id=model['model_id'],revision=model['revision'],
                scheme=a.scheme,shape=shape,layers=L,seed=a.seed,clock_MHz=250,time_ns=h.now,time_ms=h.now/1e6,
                actions=dict(m.actions),process28_counts=dict(getattr(m,'p28_counts',{})),kernel_active=dict(m.kernel_active),
                memory=h.report(),SRAM=h.mem.report(h.now),macro_config=cfg,phases=m.phases,
                source_identity=identity,contract=m.cross28_contract,resource_contract=m.resource_contract,
                ordinary_matrix_audit=m.ordinary_pool_audit,resource_audit=m.resource_audit,
                common_FFN_stages=m.common_stats,allocation=getattr(m,'cross_allocation',None),
                FFN=[x['actions'] for x in getattr(m,'cross_digital_results',[])],
                physical_Attention=[x['actions'] for x in getattr(m,'cross_attention_results',[])]))
        def progress(stage,l,ns):
            print(json.dumps(dict(stage=stage,layer=l,simulated_us=ns/1000,wall_seconds=time.time()-start)),flush=True)
            if stage=='final_norm':prefix.update(snapshot());prefix_budget.update(price(m,prefix,b,a.scheme))
        host.full_run(m,fixture,L,a.head,progress);r=snapshot()
        assert not h.events and not h.mem.queue and not r['memory']['final_pending'] and not r['memory']['final_response_occupied']
        assert r['SRAM']['capacity_bytes']==832*1024 and r['SRAM']['physical_banks']==178
        waves=KV//8;physical_Q=KV*4;selected_QK=physical_Q*(2048*32+128*128)
        if a.scheme=='SC_ising':
            assert m.kernel_active['GU_frames']==L*(F//64)*(H//64)
            assert m.kernel_active['Wd_M128_frames']==L*(H//128)*(F//64)
            assert m.actions['SC_equivalent_MAC']==L*3*F*H
            assert m.actions['attention_QK_MAC']==L*selected_QK
            assert m.actions['samples']==L*Q*64 and m.actions['PV_ADD']==L*Q*64*128
            assert m.p28_counts['front_queries']==m.p28_counts['sampler_queries']==L*Q
            assert m.p28_counts['top_feature']==L*Q and m.p28_counts['norm_groups']==L*KV
            assert m.p28_counts['codec_g8']==m.p28_counts['codec_u8']==L*F
            assert m.p28_counts['codec_bf16']==L*H
            assert m.p28_counts['scale64_groups']==L*F//32
            assert m.actions['common_state32_vectors']==4*(m.kernel_active['GU_frames']+m.kernel_active['Wd_M128_frames'])
            assert not m.p28_staging_busy and not m.common_prefetched
        else:
            fa=sum_counters(x['actions'] for x in m.cross_digital_results);aa=sum_counters(x['actions'] for x in m.cross_attention_results)
            assert len(m.cross_digital_results)==L and len(m.cross_attention_results)==L*KV
            assert fa['MAC']==3*L*F*H and fa['SwiGLU']==L*F
            assert fa['DRAM_weight_bytes']==3*L*F*H*(2 if a.scheme=='BF16_dense' else 1)
            n=128 if a.scheme=='W8_screen' else 2048
            assert aa['exact_QK_MAC']==aa['PV_MAC']==L*physical_Q*n*128
            assert aa['completed_groups']==L*KV
            assert not m.cross_pool.used and not m.cross_pool.live and not m.cross_pool.queue
            assert not m.actions['samples'] and not m.kernel_active['GU_frames']
        phases=Counter()
        for p in m.phases:phases[p['stage']]+=p['duration_ns']
        rows=a.head_probe_rows or V;wb=2 if a.scheme=='BF16_dense' else 1
        weight_expected=L*(2*H*((Q+2*KV)*128+Q*128)+3*H*F*wb)+(H*rows*2 if a.head else 0)
        kinds=('QKV_weights','O_weights','lm_head_weights','GU_weights','down_weights','digital_weights')
        actual=sum(x.get('issued_bytes',0) for k,x in r['memory']['by_kind'].items() if k in kinds)
        assert actual==weight_expected,(actual,weight_expected)
        r.update(scope='full' if L==shape['layers'] and a.head and not a.head_probe_rows else 'layer_or_partial',
            includes_lm_head=a.head,head_probe_rows=a.head_probe_rows,full_vocab=V,backend=a.backend,
            without_lm_head_stage_ms=(h.now-phases['lm_head'])/1e6,code_sha256=source_hashes,
            bindings_sha256=sha(a.bindings),macro_config_sha256=sha(a.macros),
            snapshot_manifest_sha256=sha(a.snapshot/'SNAPSHOT_MANIFEST.json'),wall_seconds=time.time()-start,
            physical_QK_issue_heads=physical_Q,useful_QK_heads=Q,KV_waves=waves,
            numeric_model_or_PPL=False,physical_wholechip_verified=False,weights_checked=actual)
        if a.backend=='native':r['native']=backend.finish(h.now)
        budget=price(m,r,b,a.scheme)
        if prefix:budget['lm_head_split']=split_head(budget,prefix_budget,h.now,prefix['time_ns'])
        assert all(sha(HERE.parent/n)==v for n,v in source_hashes.items())
        v=dict(status='PASS',queues_drained=True,all_logical_KV_groups=True,actual_shape_work=True,
            complete_head_tiling=True,weight_bytes=actual,SRAM832_same_macro_count=True,
            no_latency_rescaling=True,physical_padding_recorded=True,scope='conditionalTLMnotqualityorpostlayout')
        for n,x in [('RESULT.json',r),('BUDGET.json',budget),('VALIDATION.json',v)]:save(a.out/n,x)
        save(a.out/'SEAL.json',dict(status='completed',files_sha256={n:sha(a.out/n) for n in ('RESULT.json','BUDGET.json','VALIDATION.json','CONSTRUCTION.json')}))
        print(json.dumps(dict(status='completed',scope=r['scope'],model=a.model,scheme=a.scheme,time_ms=r['time_ms'],wall_seconds=r['wall_seconds'])),flush=True)
    finally:
        if hasattr(backend,'close'):backend.close()

if __name__=='__main__':main()
