"""Action/traffic budget adapter, NOT a new native whole-model simulator.

Fixed physical hardware. Shape-exact static matrix work; explicitly conditional
V reuse, scheduling efficiency and inherited circuit-price boundaries.
"""
from pathlib import Path
import hashlib,json,math

HERE=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_bytes())
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())
def up(n,m):return math.ceil(n/m)*m


def model_from_config(key,config):
    q=config['num_attention_heads'];d=config['hidden_size']
    return dict(key=key,hidden=d,ffn=config['intermediate_size'],layers=config['num_hidden_layers'],
        q_heads=q,kv_heads=config['num_key_value_heads'],head_dim=config.get('head_dim',d//q),
        vocab=config['vocab_size'],qk_norm=key=='qwen3_4b',tie_word_embeddings=config['tie_word_embeddings'])


def quantities(m,c,unique=None):
    hw=c['hardware'];L,d,f,q,kv,h,V=(m[k] for k in ('layers','hidden','ffn','q_heads','kv_heads','head_dim','vocab'))
    N,r,K,S=hw['context'],hw['r'],hw['K'],hw['S'];heads=q//kv
    assert q%kv==0 and heads<=4 and h==128 and d%128==f%128==0
    groups=L*kv;queries=L*q
    unique=unique if unique is not None else K*(-math.expm1(heads*S*math.log1p(-1/K)))
    assert 1<=unique<=min(K,heads*S)
    qkv=L*d*(q+2*kv)*h;o=L*d*q*h;lm=V*d;ffn=3*L*d*f
    gu=L*(f//64)*(d//64);wd=L*(d//128)*(f//64)
    gu_state=L*(f//64)*(d//64-1)*64;wd_state=L*(d//128)*(f//64-1)*64
    meta_per_layer=max(32768,up(3*d*f//4096,64))
    normal_bytes=up((2*L*d+(L*2*h if m['qk_norm'] else 0)+d)*2,64)
    # Keep eight physical KV buffers, not kv logical replicas. Check resident
    # norm layout first, then use ordinary double-buffered layer norm weights.
    memory=placement(m,c,normal_bytes)
    norm_stream=normal_bytes if memory['normalization_policy']=='layer_stream_double_buffer' else 0
    dram=dict(embedding=up(d*2,64),QKV_weights=2*qkv,O_weights=2*o,
        GU_weights=2*L*d*f,down_weights=L*d*f,lm_head_weights=2*lm,
        FFN_scale_metadata=L*meta_per_layer,K_append=groups*h*2,V_append=groups*h*2,
        K_block_for_transpose=groups*32*h*2,K_feature_append=groups*32*h*2,
        coarse_K=groups*r*N*2,selected_K=groups*K*h*2,sample_V=groups*unique*h*2)
    if norm_stream:dram['normalization_weight_stream']=norm_stream
    output_words=queries*h*2/16;kv_words=groups*h*2/16;norm_words=(2*L+1)*d*2/16
    tags={}
    def put(name,reads=0,writes=0):
        tags[name]={}
        if reads:tags[name]['read_words']=reads
        if writes:tags[name]['write_words']=writes
    put('embedding_fill',writes=up(d*2,64)/16)
    for k in ('save_residual_read','residual_branch','residual_skip'):put(k,reads=L*d/4)
    for k in ('save_residual_write','residual_output'):put(k,writes=L*d/4)
    for k in ('norm_activation','norm_gamma'):put(k,reads=norm_words)
    put('norm_output',writes=norm_words)
    put('QKV_activation_to_local',reads=L*d/8)
    for name,amount in [('QKV',qkv),('O',o),('lm_head',lm)]:
        put(name+'_weights_fill',writes=amount*2/16);put(name+'_operand',reads=amount*2/16)
    put('QKV_output',writes=L*(q+2*kv)*h/8)
    put('QK_norm_rope_input',reads=L*(q+kv)*h/8)
    put('QK_norm_rope_output',writes=L*(q+kv)*h/8)
    for name in ('K','V'):
        put(name+'_append_input',reads=kv_words);put(name+'_append_source',writes=kv_words)
        put(name+'_append_DMA_source',reads=kv_words)
    for name in ('Q_to_attention','query_feature_scan','attention_gather_read','O_activation_to_local'):
        put(name,reads=output_words)
    for name in ('Q_local_fill','attention_output','attention_gather_write'):put(name,writes=output_words)
    trans=groups*32*h*2/16
    for name in ('K_block_for_transpose_fill','K_transpose_write'):put(name,writes=trans)
    for name in ('K_transpose_read','K_feature_append_DMA_source'):put(name,reads=trans)
    put('coarse_K_fill',writes=dram['coarse_K']/16);put('coarse_K_operand',reads=dram['coarse_K']/16)
    coarse_words=queries*N*2/16
    put('coarse_scores',writes=coarse_words)
    for i in range(1,4):put('coarse_score_pass'+str(i),reads=coarse_words)
    put('selected_K_fill',writes=dram['selected_K']/16);put('selected_K_operand',reads=dram['selected_K']/16)
    put('selected_scores',writes=queries*K*4/16);put('sampler_score_input',reads=queries*K*4/16)
    put('sample_V_fill',writes=dram['sample_V']/16)
    put('sample_V_operand',reads=queries*S*h*2/16)
    put('O_output',writes=L*d/8)
    put('GU_weights_fill',writes=2*L*d*f/16);put('down_weights_fill',writes=L*d*f/16)
    put('FFN_scale_metadata_fill',writes=L*meta_per_layer/16)
    put('x_encode_input',reads=L*d/8);put('x_codes_store',writes=L*up(d//64*80,64)/16)
    put('GU_weight_scale_metadata',reads=gu);put('Wd_weight_scale_metadata',reads=2*wd)
    put('GU_x_codes',reads=L*hw['FFN_cores']*(d//64)*5)
    put('common_GU_state_write',writes=gu_state);put('common_GU_state_read',reads=gu_state)
    put('GU_quantized_output',writes=L*f/8);put('GU_scale_output',writes=L*f/64)
    ref=c['reference'];rm=ref['model']
    reload_factor=ref['sram_by_tag']['NL_gu_scale']['read_words']/(rm['layers']*hw['FFN_cores']*(rm['ffn']//64))
    nl_loads=L*hw['FFN_cores']*(f//64)*reload_factor
    put('NL_gu_codes',reads=nl_loads*8);put('NL_gu_scale',reads=nl_loads)
    put('common_Wd_state_write',writes=wd_state);put('common_Wd_state_read',reads=wd_state)
    put('FFN_BF16_output',writes=L*d/8);put('lm_head_activation_to_local',reads=d/8)
    if norm_stream:put('normalization_weight_stream_fill',writes=norm_stream/16)
    physical_weights=3*L*d*f+2*(qkv+o+lm)+(0 if m['tie_word_embeddings'] else 2*lm)
    return dict(model=m,queries=queries,logical_KVgroups=groups,query_heads_per_KV=heads,
        physical_KVgroup_waves_per_layer=math.ceil(kv/hw['attention_physical_groups']),
        unique_V_per_KVgroup=unique,unique_V_bounds=[1,min(K,heads*S)],
        ordinary_MAC=qkv+o+lm,ordinary_by_matrix=dict(QKV=qkv,O=o,lm_head=lm),
        FFN_MAC=ffn,GU_frames=gu,Wd_frames=wd,state32_vectors=(gu+wd)*4,
        reduction_ADD=(L*((q+2*kv)*h+d)+V)*63,
        QK_MAC=queries*(N*r+K*h),PV_ADD=queries*S*h,samples=queries*S,
        dram_bytes_by_kind=dram,external_bytes=math.fsum(dram.values()),sram_by_tag=tags,
        SRAM_read_words=math.fsum(x.get('read_words',0) for x in tags.values()),
        SRAM_write_words=math.fsum(x.get('write_words',0) for x in tags.values()),
        logical_full_BF16_KV_bytes=2*groups*N*h*2,
        full_KV_plus_transposed_K_view_bytes=3*groups*N*h*2,
        physical_mixed_weight_storage_bytes=physical_weights,
        weight_plus_KV_storage_bytes=physical_weights+3*groups*N*h*2+L*meta_per_layer+normal_bytes,
        metadata_per_layer_bytes=meta_per_layer,
        memory_placement=memory)


def placement(m,c,norm_bytes):
    ref=c['reference'];hw=c['hardware']
    regions=[]
    for old in ref['sram_regions']:
        x=dict(old)
        if x['name']=='resident_norm_weights':x['size']=norm_bytes
        if x['name']=='common_FFN_wide_state':x['size']=m['ffn']*16
        regions.append(x)
    def check(rows):
        allocated=[0]*512
        for x in rows:
            words=math.ceil(x['size']/16);banks=x['banks']
            for j,b in enumerate(banks):allocated[b]+=(words//len(banks)+(j<words%len(banks)))*16
        failures=[i for i,(a,b) in enumerate(zip(allocated,ref['bank_depths'])) if a>b]
        return allocated,failures
    allocated,fail=check(regions)
    original_fail=list(fail)
    policy='resident_all_norm_weights'
    if fail:
        # Two complete per-layer RMSNorm vectors per slot, two slots. Same
        # shared SRAM and DMA, ordinary cross-layer prefetch; not a new macro.
        policy='layer_stream_double_buffer'
        for row in regions:
            if row['name']=='resident_norm_weights':row['size']=up(8*m['hidden'],64)
        allocated,fail=check(regions)
    assert not fail and sum(allocated)<=hw['SRAM_bytes'],(m['key'],fail)
    return dict(normalization_policy=policy,norm_resident_bytes=next(x['size'] for x in regions if x['name']=='resident_norm_weights'),
        physical_allocated_bytes=sum(allocated),capacity_bytes=hw['SRAM_bytes'],
        same_physical_banks=True,logical_KVgroups_not_replicated_into_SRAM=True,
        original_resident_layout_failing_banks=original_fail,
        revised_bank_capacity_check='PASS_not_a_port_or_timing_simulation',
        maximum_bank_usage_fraction=max(a/b for a,b in zip(allocated,ref['bank_depths'])),
        metadata_layout_repack_required=m['key']!='qwen3_4b',
        metadata_warning='parameterize fixed32KiB load and dynamic-scale offset20000; DeepSeek requires33024B/layer')


def time_budget(x,c,utilization):
    hw=c['hardware'];hz=hw['chip_hz'];physical=hw['attention_physical_groups']
    m=x['model'];queries=x['queries']
    compute=dict(projection_and_lm=x['ordinary_MAC']/hw['ordinary_FMA_lanes']/hz,
        FFN=(x['GU_frames']+x['Wd_frames'])*hw['FFN_frame_cycles']/hw['FFN_cores']/hz,
        QK=x['QK_MAC']/(physical*hw['attention_QK_lanes_per_group'])/hz,
        sampler=queries*c['prices']['sampler']['work_ns']*1e-9/physical,
        PV=x['PV_ADD']/(physical*16*x['query_heads_per_KV'])/hz,
        reduction=x['reduction_ADD']/128/hz)
    compute_ms=math.fsum(compute.values())*1000
    sram_ms=(x['SRAM_read_words']+x['SRAM_write_words'])*16/(512*1e6)
    memory_ms=x['external_bytes']/(hw['nominal_DRAM_GBs']*utilization*1e6)
    time=max(memory_ms,compute_ms,sram_ms)
    return dict(time_ms=time,cycles=time*hw['chip_hz']/1000,
        external_service_ms=memory_ms,serial_compute_optimistic_floor_ms=compute_ms,
        aggregate_SRAM_service_floor_ms=sram_ms,compute_stage_floor_ms={k:v*1000 for k,v in compute.items()},
        external_utilization=utilization,critical_estimated_resource='external_memory' if time==memory_ms else 'compute_or_SRAM',
        method='calibrated effective-bandwidth roofline with sequential compute-phase and SRAM floors; not native schedule')


def energy_budget(x,c,t):
    p=c['prices'];hw=c['hardware'];ms=t['time_ms'];ns=ms*1e6
    fma=p['digital']['fma16_c4'];inc=p['online'];energy={}
    energy['ordinary_BF16_FMA']=x['ordinary_MAC']*fma['incremental_pJ']*1e-9+64*fma['idle_W']*ms
    energy['ordinary_final_reduction']=x['reduction_ADD']*inc['fpadd']*1e-9+128*17.52e-6*ms
    sc=p['sc'];frames=x['GU_frames']+x['Wd_frames'];busy_ns=frames*660
    assert busy_ns<=hw['FFN_cores']*ns
    energy['FFN_common_core']=(128*(x['GU_frames']*sc['GU_gross_pJ_per_DOT64']+x['Wd_frames']*sc['Wd_gross_pJ_per_DOT64'])*1e-9
        +(hw['FFN_cores']*ns-busy_ns)*sc['idle_W_per_core_proxy']*1e-6)
    st=p['common']['ab_state32'];op=x['state32_vectors']
    energy['FFN_crossK_state32']=op*st['active_pJ']*1e-9+(2*ns-op*10)*st['idle_W']*1e-6
    energy['FFN_random_service_proxy']=0.0
    energy['shared_SRAM']=(x['SRAM_read_words']*p['SRAM_read_pJ_per16B']+x['SRAM_write_words']*p['SRAM_write_pJ_per16B'])*1e-9+640*p['SRAM_idle_W_per4KiB']*ms
    ingress=p['ingress']
    energy['DMA_24KiB_holding']=x['external_bytes']/64*ingress['capture_pJ_per64B']*1e-9+ingress['data_leak_W']*ms
    state_reads=x['sram_by_tag']['common_GU_state_read']['read_words']+x['sram_by_tag']['common_Wd_state_read']['read_words']
    energy['FFN_2KiB_state_response_proxy']=state_reads/4*ingress['capture_pJ_per64B']*1e-9+ingress['data_leak_W']*ms/12
    remain=p['remaining'];hold=remain['digital_local_holding_bytes']
    energy['digital_holding_proxy']=hold/24576*ingress['data_leak_W']*ms
    m=x['model'];r=c['reference']['model']
    codec=(m['layers']*(m['hidden']+2*m['ffn']))/(r['layers']*(r['hidden']+2*r['ffn']))
    vector=((2*m['layers']+1)*m['hidden'])/((2*r['layers']+1)*r['hidden'])
    energy['format_and_vector_proxy']=remain['format_activity_mJ']*codec+remain['other_vector_activity_mJ']*vector+remain['format_leak_W']*ms
    energy['Attention_QK_FMA']=x['QK_MAC']*fma['incremental_pJ']*1e-9+32*fma['idle_W']*ms
    s=p['screen']
    # Keep full measured four-head selector activity for each logical group.
    # This explicit upper proxy avoids giving MHA free selector execution.
    energy['Attention_SparQ']=x['logical_KVgroups']*s['screen_active_nJ_per_group']*1e-6+8*s['screen_leak_W_per_group']*ms
    sm=p['sampler']
    energy['Attention_sampler']=x['queries']*(sm['query_nJ']-sm['idle_W']*sm['work_ns'])*1e-6+8*sm['idle_W']*ms
    v=p['vpath']['vacc16'];ctrl=p['vpath']['vctrl4']
    energy['Attention_V_accumulate']=x['PV_ADD']*v['incremental_nJ']['stream']*1e-6+32*v['idle_W']*ms
    fraction=max(0,min(1,(x['unique_V_per_KVgroup']-8)/120))
    rate=ctrl['incremental_nJ']['reuse']*(1-fraction)+ctrl['incremental_nJ']['cold']*fraction
    energy['Attention_V_control']=x['samples']*rate*1e-6+8*ctrl['idle_W']*ms
    out=p['output_converter'];elements=x['queries']*m['head_dim']
    energy['Attention_normalize_output_proxy']=elements*2*inc['fp32_to_bf16']*1e-9+512*out['idle_W']*ms
    total=math.fsum(energy.values());external={str(z):x['external_bytes']*8*z*1e-9 for z in hw['external_pJ_per_bit']}
    return dict(onchip_components_mJ=energy,onchip_mJ=total,external_mJ_by_pJ_per_bit=external,
        covered_system_mJ_at4pJ=total+external['4'],covered_system_average_W_at4pJ=(total+external['4'])/ms,
        onchip_average_W=total/ms,area_components55_mm2=c['reference']['areas55_mm2'],
        covered_area55_mm2=math.fsum(c['reference']['areas55_mm2'].values()),
        FFN_RNG_already_inside_core=True,new_model_activity_measured=False)


def estimate_model(m,c,reference=False):
    ref=c['reference'];hw=c['hardware']
    unique=ref['actions']['unique_V']/(ref['model']['layers']*ref['model']['kv_heads']) if reference else None
    x=quantities(m,c,unique)
    current_eff=ref['external_bytes']/(ref['time_ms']*1e6)/hw['nominal_DRAM_GBs']
    scenarios={}
    for name,u in [('reference_efficiency',current_eff),('util65',.65),('util90',.90)]:
        t=time_budget(x,c,u);scenarios[name]=dict(**t,**energy_budget(x,c,t))
    vb=[]
    for u in x['unique_V_bounds']:
        z=quantities(m,c,u);t=time_budget(z,c,current_eff)
        vb.append(dict(unique_V=u,external_bytes=z['external_bytes'],time_ms=t['time_ms'],
            system_mJ_at4pJ=energy_budget(z,c,t)['covered_system_mJ_at4pJ']))
    return dict(status='ANALYTICAL_PRELIMINARY_NOT_NATIVE_TLM_OR_PPL',quantities=x,
        scenarios=scenarios,V_reuse_bounds_at_reference_efficiency=vb,
        new_model_V_assumption='uniform-with-replacement occupancy scenario; winner-hold mixing/correlation and real logits unvalidated',
        QK_trace_reused_as_new_model=False)


def main():
    c=load(HERE/'CALIBRATION.json');models=[]
    for key in ('qwen3_4b','llama32_3b','deepseek_7b'):
        models.append(model_from_config(key,load(HERE/'evidence'/(key+'_config.json'))))
    rows={m['key']:estimate_model(m,c,m['key']=='qwen3_4b') for m in models}
    baseline=rows['qwen3_4b'];b=baseline['scenarios']['reference_efficiency'];ref=c['reference']
    assert abs(baseline['quantities']['external_bytes']-ref['external_bytes'])<1e-4
    for name,value in ref['onchip_components_mJ'].items():
        assert abs(b['onchip_components_mJ'][name]-value)<1e-8,(name,b['onchip_components_mJ'][name],value)
    out=dict(format='fixed-chip-cross-model-preliminary-1',reference_reconstruction='PASS',
        models=rows,hardware=c['hardware'],limitations=c['limits']+[
            'new model memory scheduling is calibrated analytical, not full native replay',
            '65/90 percent memory efficiency are scenarios, not measured bounds or confidence intervals',
            'SparQ selector per-logical-group cost retains measured four-head activity as an upper proxy',
            'same physical area assumes reprogrammable routing/control; any added interface delta not yet priced',
            'new model scales, T64/K128/S64 quality and Ising cycle distributions require independent calibration/PPL'],
        inputs_sha256={str(p.relative_to(HERE)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [HERE/'CALIBRATION.json',*sorted((HERE/'evidence').glob('*.json'))]},
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),new_native_jobs_submitted=False)
    save(HERE/'ESTIMATE.json',out)
    print(json.dumps({k:dict(time_ms=v['scenarios']['reference_efficiency']['time_ms'],
        onchip_mJ=v['scenarios']['reference_efficiency']['onchip_mJ'],
        total_mJ=v['scenarios']['reference_efficiency']['covered_system_mJ_at4pJ'],
        average_W=v['scenarios']['reference_efficiency']['covered_system_average_W_at4pJ'],
        external_GB=v['quantities']['external_bytes']/1e9,
        area55_mm2=v['scenarios']['reference_efficiency']['covered_area55_mm2'],
        SRAM_allocated=v['quantities']['memory_placement']['physical_allocated_bytes']) for k,v in rows.items()}))


if __name__=='__main__':main()
