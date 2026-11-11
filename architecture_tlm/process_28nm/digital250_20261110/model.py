"""28nm digital controls, reusing the accepted55nm actors and finite host.

Only this opt-in process is patched. SC jobs and their frozen sources are never
modified. Old ``area55`` field names are adapter API names; all values here are
28nm raw areas (multiplier1). No old55nm price enters the resulting ledger.
"""
from pathlib import Path
from collections import Counter
from types import MethodType
import copy,inspect,math,sys

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent
sys.path.insert(0,str(PARENT))
from whole_model import module,load,unknown_sram_prices,retime

def memory_layout(m,cfg):
    """Same832KiB and same178macro inventory; digital48KiB KV slots.

    Unused SC crossK96KiB is released. Activation shrinks128->96KiB as in
    probability832. Front448KiB uses82ports;8Attention slots use96ports.
    """
    h=m.h;mem=h.mem
    assert h.now==0 and not h.events and not mem.queue
    m.vector.size=96*1024
    del mem.regions[m.common_state.name]
    m.common_state.size=0;m.common_state.banks=()
    assert all(r.size==48*1024 for r in m.att)
    front=[r for r in mem.regions.values() if r not in m.att]
    assert sum(r.size for r in front)==448*1024
    offsets={};cursor=0
    for r in front:offsets[id(r)]=cursor;cursor+=r.size//16;r.banks=tuple(range(82))
    for g,r in enumerate(m.att):r.banks=tuple(range(82+12*g,82+12*(g+1)))
    def location(r,word):
        if id(r) in offsets:
            linear=offsets[id(r)]+word
            if linear<82*256:row,bank=divmod(linear,82)
            else:row,bank=divmod(linear-82*256,30);row+=256
            return bank,row
        return r.banks[word%12],word//12
    depths=(8192,)*30+(4096,)*148;seen=set();allocated=[0]*178;cursor=0
    for r in mem.regions.values():
        r.base=cursor;cursor+=r.size
        for word in range(r.size//16):
            b,row=location(r,word);assert row<depths[b]//16 and (b,row) not in seen
            seen.add((b,row));allocated[b]+=16
    assert allocated==list(depths) and cursor==832*1024
    mem.capacity=mem.top=cursor;mem.nbank=178;mem.bank_depths=depths;mem.bank_allocated=allocated
    mem.physical_bank_resolver=lambda r,w:location(r,w)[0];mem.physical_location=location
    mem.bank_model_ids=('S2',)*30+('S0',)*148;mem.bank_activity=[Counter() for _ in depths]
    m.sram_bank_row_bases={};h.return_banks=82
    m.compact_memory=dict(capacity_KiB=832,front_banks=82,attention_banks=96,
        physical_macro_count=178,physical_macro_counts={'S2_8KiB':30,'S0_4KiB':148},
        attention_group_KiB=48,bank_clock_MHz=250,profile='digital832_front448_attention384')
    m.candidate_sram_contract=dict(m.compact_memory,no_extra_ports=True,
        unused_SC_crossK_state_removed_KiB=96,FFN_projection_reuse_KiB=256,
        ordinary_weight_slots_KiB=64,activation_KiB=96,norm_KiB=32)

def make_profiles(base_make,base_att,b,scheme):
    """Bind existing GU, BF16 NL, dual-mode FMA and scalar28nm cards."""
    path='BF16' if scheme=='BF16_dense' else 'W8';cards=b['attention_cards']
    raw=load(HERE/'FFN_SOURCE_PROFILE.json');reused=raw['accepted_reused_components']
    fma=b['shared_FMA'] if path=='BF16' else b['digital_reference_cards']['fma16_dual_28_250']
    area=fma['area_mm2'];p=base_make(250,path)
    p.update(PVT='TT0.9V25C',process='28nm',area_multiplier=1,SRAM_KiB=832,SRAM_banks=178,
        host_format_area55_mm2=0,reduction_units=32)
    p['pool']['area55_mm2_per_slice']=area
    p['prices']['nonlinear']=dict(area55_mm2=reused['nl_bf16_250']['area_mm2'],evidence='measured28nmNL5/II1')
    p['prices']['integer_GU']=dict(area55_mm2=reused['integer_gu_250']['area_mm2'],evidence='measured28nmK64PoT_INT64_II1')
    red=b['digital_reference_cards']['fpadd_28_250']
    p['prices']['reduction']=dict(area55_mm2=red['area_mm2'],evidence='measured28nmFP32ADD3/II1')
    def fp(clock,path_,pool_slices=16,gu_units=16,nonlinear_units=4):
        assert clock==250 and path_==path
        q=copy.deepcopy(p);q.update(pool_slices=pool_slices,lanes=pool_slices*16,
            GU_units=gu_units if path=='W8' else 0,NL_units=nonlinear_units)
        q['matrix_mapping'].update(output_tile=pool_slices*16,K_parallel=4,contexts=4)
        width=2 if path=='BF16' else 1
        q['matrix_mapping']['K_tile']=next(k for k in (64,32,16,8,4) if pool_slices*16*math.ceil(k*width/16)*16<=32768)
        q['fixed_components']=[dict(resource_id='FFN_BF16_SwiGLU',area55_mm2=nonlinear_units*reused['nl_bf16_250']['area_mm2'])]
        if path=='W8':
            q['fixed_components'].append(dict(resource_id='FFN_A9W8_GU',area55_mm2=gu_units*reused['integer_gu_250']['area_mm2']))
            aux=b['FFN_shared_aux']
            q['fixed_components'] += [dict(resource_id='FFN_input_scale_codec',area55_mm2=aux['scale']['area_mm2']+32*aux['codec']['area_mm2'])]
        q['shared_components']=[dict(resource_id='shared_FP32_reduction',area55_mm2=32*red['area_mm2'])]
        q['fixed_area55_mm2']=sum(x['area55_mm2'] for x in q['fixed_components'])
        return q
    mode='screen_full' if scheme=='W8_screen' else 'dense';ap=base_att(250,mode,8)
    scalar_counts=dict(bf_fpadd=8,bf_fpmul=1,bf_explut=4,bf_recseed=1)
    scalar=8*sum(cards[k+'_250']['area28_mm2']*n for k,n in scalar_counts.items())
    converter=8*b['FFN_shared_aux']['codec']['area_mm2']
    byte_area=8*b['platform_macro']['register_bit_area_mm2'];holding=8*2176*byte_area
    control=.1*scalar+.01*8 # keep explicit logical-control allowance,not process-scaled measurement
    fixed=[dict(resource_id='digital_attention_scalar_pool',area55_mm2=scalar+converter),
        dict(resource_id='digital_attention_QK_staging',area55_mm2=holding),
        dict(resource_id='digital_attention_control_reserve',area55_mm2=control)]
    if mode=='screen_full':fixed.append(dict(resource_id='digital_attention_SparQ_shared_selector',
        area55_mm2=cards['screen_norm16_250']['area28_mm2']+cards['screen_top16_250']['area28_mm2']))
    ap.update(process='28nm',area_multiplier=1,fixed_components=fixed,
        fixed_area55_mm2=sum(x['area55_mm2'] for x in fixed),SRAM_KiB=832)
    return fp,lambda clock,mode_,groups:copy.deepcopy(ap)

def build(snapshot,runtime,deps,b,macros,backend,scheme,layers,head,seed=17):
    main=module('digital28_current_host',snapshot/'glue/current_mainline.py')
    factory,identity=main.environment(snapshot,runtime,deps,250);unknown_sram_prices()
    h,m=factory(backend,cores=3,layers=36,include_lm=head,seed=seed,
        samples=load(snapshot/'inputs/SAMPLES.json'),attention_input=load(snapshot/'inputs/representative.json'),mode='ising',ffn='sc')
    shape=load(snapshot/'glue/CURRENT_WORKLOAD_PLAN.json')['models']['qwen3_4b']['shape']
    m.cross_clock=250
    from architecture_tlm.module_refresh_20261107 import bindings
    bindings.core_contract=lambda clock:dict(clock_MHz=250,modes=b['FFN_core']['modes'],implementation='28nm')
    main.rebuild(m,shape,layers if head else 36,scheme)
    from architecture_tlm.attention_supply_front_20261107 import finite_supply
    original_consume=finite_supply.consume_tile
    memory_layout(m,macros['SRAM']);retime(m,250,macros['SRAM']['latency_cycles_default'],macros)
    assert macros['FMA_feedback_cycles']==4
    finite_supply.consume_tile=original_consume # same4cycles;retain inspectable frozen source
    # The legacy constructor bootstraps once more and narrows __path__.
    # Restore only the manifest-pinned delivered module directory afterward.
    import architecture_tlm
    architecture_tlm.__path__=[str(snapshot/'modules/architecture_tlm')]+list(architecture_tlm.__path__)
    from architecture_tlm.ffn_digital_contract_20261107 import adapter as F
    from architecture_tlm.attention_digital_small_20261107 import profile as AP
    F.make_profile,AP.profile=make_profiles(F.make_profile,AP.profile,b,scheme)
    sram_area=sum(macros['SRAM']['macro_models'][k]['area_mm2'] for k in h.mem.bank_model_ids)
    p=b['platform_macro'];byte_area=8*p['register_bit_area_mm2']
    target=dict(target_area55_mm2=6.480302546479157,digital_host_fixed_components=[
        dict(resource_id='SRAM28',area55_mm2=sram_area),
        dict(resource_id='host_projection_FIFO',area55_mm2=16384*byte_area),
        dict(resource_id='platform_excluding_operand_FIFO',area55_mm2=20*1024*byte_area+p['vector_output_area_mm2']+p['CIM_programming_distribution_area_mm2'])])
    source=inspect.getsource(main.digital_install)
    old="target=load(snapshot/'architecture_tlm/equal_area_100_250_20261107/TARGETS.json')['versions'][str(clock)]"
    assert source.count(old)==1;source=source.replace(old,'target=TARGET')
    source=source.replace('.0000483721875','BYTE_AREA')
    # Four stage NL is a different integer module. This baseline uses measured
    # BF16 NL, five stages, and the existing finite five-entry result queue.
    env=dict(main.__dict__,TARGET=target,BYTE_AREA=byte_area)
    exec(compile(source,'<28nm digital actor bindings>','exec'),env)
    env['digital_install'](m,snapshot,shape,250,scheme)
    # BF16 probability weights are explicitly RNE-cast before BF16 PV input.
    from architecture_tlm.attention_digital_small_20261107 import adapter as A
    old_front=A.Attention.front
    def front(self,*args,**kwargs):
        yield from old_front(self,*args,**kwargs)
        self.actions['weight_BF16']+=128
    A.Attention.front=front
    # A feature-top transaction is oneQ head in the measured28nm card.
    # FourQ heads share each KV group; neither its service nor price is free.
    coarse_source=inspect.getsource(A.Attention.coarse)
    coarse_source=coarse_source.replace('yield from self.delay(164)','yield from self.delay(4*164)')
    coarse_source=coarse_source.replace("self.actions['feature_select_groups']+=1","self.actions['feature_select_groups']+=4")
    import textwrap
    ce=dict(A.__dict__);exec(compile(textwrap.dedent(coarse_source),'<28nm fourQ feature service>','exec'),ce)
    A.Attention.coarse=ce['coarse']
    m.digital28_contract=dict(scheme=scheme,FFN='BF16 dense' if scheme=='BF16_dense' else 'A9/W8 GU with PoT+INT64;BF16NL;BF16z/W8PoT Wd',
        new_scaled_P8_CIM_not_primary=True,area_multiplier=1,prices='28nm only',
        SRAM=m.candidate_sram_contract,allocation=m.cross_allocation,
        scalar_timing='existing finite onlineSoftmax macros;4cycleADD/MUL/LUT assumed,not integrated RTL',
        conversion='FP32-toBF16 output/coarse/exp-weight conversions explicitly priced;codec primitive proxy',
        controlled_trace='same representative SparQ candidates;synthetic online max-rescale changes,not real model inference')
    return h,m,main,shape,identity
