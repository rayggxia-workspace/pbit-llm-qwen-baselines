"""Same28nm chip, different decoder shapes; no old latency rescaling.

Preserve physical four-Q/64MAC issue groups. Unused whole FMA16 head slices
are clock-gated in the action ledger; their area, issue slots and residency
remain. This is an explicit mapping assumption, not a new optimized chip.
"""
from pathlib import Path
from types import MethodType
import copy,inspect,math,sys,textwrap
HERE=Path(__file__).resolve().parent;PARENT=HERE.parent
sys.path.insert(0,str(PARENT))
import whole_model as W
from whole_model import load,module

def vector_decoder(meta):
    target=57344 if meta>32768 else 65536
    def address(offset,size):
        if offset>=196608:
            g,inside=divmod(offset-196608,6144)
            if g<8 and inside>=5120 and inside+size<=6144:return 49152+g*1024+inside-5120
        if 131072<=offset and offset+size<=131072+8192:return 32768+offset-131072
        if 65536<=offset and offset+size<=65536+meta+1024:return target+offset-65536
        if 0<=offset and offset+size<=32768:return offset
        raise ValueError(('cross28 vector bounds',offset,size,meta))
    return address

def select_queries(m):
    """Adapt only active-head producer/consumer cardinality of pinned S64."""
    src=inspect.getsource(W.sampled)
    for old,new in [
        ('range(4)','range(m.cross_qpg)'),
        ("m.actions['sampler_queries']+=4","m.actions['sampler_queries']+=m.cross_qpg"),
        ("m.actions['samples']+=256","m.actions['samples']+=64*m.cross_qpg"),
        ("m.actions['sample_output_BF16']+=512","m.actions['sample_output_BF16']+=128*m.cross_qpg"),
        ('sum(consumed)==256','sum(consumed)==64*m.cross_qpg'),
        ("audit['scalar_adds']==32768","audit['scalar_adds']==8192*m.cross_qpg"),
        ('sample_count=256','sample_count=64*m.cross_qpg'),
        ("r,122880,1024,True,'attention_output'","r,122880,m.cross_qpg*256,True,'attention_output'")]:
        assert old in src,old;src=src.replace(old,new)
    env=dict(W.sampled.__globals__);exec(compile(src,'<cross28 activeS64 heads>','exec'),env)
    m.attention_group=MethodType(env['sampled'],m)
    src=inspect.getsource(W.screen)
    src=src.replace('4*164*p','m.cross_qpg*164*p').replace("c['top_feature']+=4","c['top_feature']+=m.cross_qpg")
    env=dict(W.screen.__globals__);exec(compile(src,'<cross28 actualfeature queries>','exec'),env)
    m.compact_screen=MethodType(env['screen'],m)

def common_finish(m,main,shape,model):
    """Real token embedding location, also for untied DeepSeek embeddings."""
    m.embedding_base=m.lm_base if model['tie_word_embeddings'] else m.a.alloc('untied_token_embedding',shape['vocab']*shape['hidden']*2)
    src=inspect.getsource(main.full_run).replace("m.lm_base+(m.seed%m.model['vocab'])","m.embedding_base+(m.seed%m.model['vocab'])")
    assert 'm.embedding_base+' in src
    env=dict(main.__dict__);exec(compile(src,'<cross28 actualembedding address>','exec'),env)
    main.full_run=env['full_run']
    m.cross28_contract=dict(model_id=model['model_id'],revision=model['revision'],config_sha256=model['config_sha256'],
        shape=shape,Q_per_KV=m.cross_qpg,KV_waves=shape['kv_heads']//8,hardware_Qslots_per_KV=4,
        physical_QK_PV_issue_width=64,unused_heads='wholeFMA16slices gated;area/issue slots/residency retained',
        active_V_sample_heads=m.cross_qpg,local_KV_workers=8,untied_embedding=not model['tie_word_embeddings'],
        metadata_bytes=3*(shape['hidden']//64)*(shape['ffn']//64),
        metadata_physical_base=57344 if m.cross_meta>32768 else 65536,
        reused_sample_addresses='pinnedseed/perphysicalgroup trace;differentKVwave addresses;not new textaccuracy',
        fixture_source='SHAPE_FIXTURES per model;different activehead/SparQ candidates and maxchange metadata',
        area_SRAM_compute_external_unchanged=True,extra_weight_storage=False)
    return m

def build(snapshot,runtime,deps,b,bsha,macros,backend,model_key,scheme,layers,head,seed=17):
    model=load(HERE/'MODELS.json')['models'][model_key];shape=model['shape']
    if scheme=='SC_ising':
        main=module('cross28_host',snapshot/'glue/current_mainline.py');main.vector_decoder=vector_decoder
        factory,identity=main.environment(snapshot,runtime,deps,250);W.unknown_sram_prices()
        h,m=factory(backend,cores=3,layers=36,include_lm=head,seed=seed,
            samples=load(snapshot/'inputs/SAMPLES.json'),attention_input=load(snapshot/'inputs/representative.json'),mode='ising',ffn='sc')
        m.cross_clock=250;m.p28_binding_sha=bsha
        from collections import Counter
        m.p28_counts=Counter()
        from architecture_tlm.module_refresh_20261107 import bindings
        bindings.core_contract=lambda clock:dict(clock_MHz=250,modes=b['FFN_core']['modes'],profile_sha256=bsha,implementation='28nm')
        main.rebuild(m,shape,layers if head else shape['layers'],scheme);m.p28_macros=macros
        from candidate_sram import install
        install(m,macros['SRAM']);W.retime(m,250,macros['SRAM']['latency_cycles_default'],macros)
        W.install_ffn(m,b,3);select_queries(m)
        card=b['attention_cards']['gap_sampler_250']
        m.p28_sampler_remaining_cycles=max(65,math.ceil(card['mean_query_cycles_excluding_interquery_gap'])-32)
    else:
        d=module('cross28_digital_binding',PARENT/'digital250_20261110/model.py')
        # Keep both frozen generic modules untouched. Override only the shape
        # reader and vector address function in this opt-in process.
        original_load=d.load;original_module=d.module
        def reader(p):
            x=original_load(p)
            if Path(p).name=='CURRENT_WORKLOAD_PLAN.json':
                x=copy.deepcopy(x);x['models']['qwen3_4b']['shape']=shape
            return x
        def loader(name,path):
            x=original_module(name,path)
            if name=='digital28_current_host':x.vector_decoder=vector_decoder
            return x
        d.load=reader;d.module=loader
        h,m,main,_,identity=d.build(snapshot,runtime,deps,b,macros,backend,scheme,layers,head,seed)
    common_finish(m,main,shape,model)
    return h,m,main,shape,identity,model

def gated_digital_results(m):
    """Retain physical counts and return activeFMA work for action pricing."""
    saved=[]
    for row in m.cross_attention_results:
        original=row['actions'];active=dict(original)
        for name in ('coarse_QK_MAC','exact_QK_MAC','PV_MAC','coarse_BF16','weight_BF16','output_BF16'):
            n=original.get(name,0);assert n*m.cross_qpg%4==0
            active[name]=n*m.cross_qpg//4
        saved.append(original);row['actions']=active
    return saved

def price(m,result,b,scheme):
    if scheme=='SC_ising':
        from whole_pricing import price as base
        # Physical QK issue slots are padded tofour heads. Measured FMA16
        # actions use active slices; full physical pool idle stays charged.
        r=copy.copy(result);r['actions']=dict(result['actions'])
        raw=r['actions']['attention_QK_MAC'];assert raw*m.cross_qpg%4==0
        r['actions']['attention_QK_MAC']=raw*m.cross_qpg//4
        value=base(m,r,b)
        value['QK_physical_MAC']=raw;value['QK_useful_MAC']=r['actions']['attention_QK_MAC']
    else:
        p=module('cross28_digital_pricing',PARENT/'digital250_20261110/pricing.py')
        source=inspect.getsource(p.price)
        source=source.replace('L*40*',"L*(r['shape']['hidden']//64)*").replace('L*2560*',"L*r['shape']['hidden']*")
        env=dict(p.__dict__);exec(compile(source,'<cross28 dynamic inputcodec counts>','exec'),env)
        original=gated_digital_results(m)
        try:value=env['price'](m,result,b)
        finally:
            for row,old in zip(m.cross_attention_results,original):row['actions']=old
        value['physical_Attention_actions']=dict(sum_counters(original))
    value['cross_model_contract']=m.cross28_contract
    value['physical_issue_padding_not_free_speedup']=True
    value['inactive_head_gating']='FMA16 wholehead slices;linear incremental action proxy,physicalarea/idleretained'
    return value

def sum_counters(rows):
    from collections import Counter
    out=Counter()
    for row in rows:out.update(row)
    return out
