"""28nm overlay on the frozen finite-bank/DMA/credit execution model.

Run in a fresh Python process: runtime patches are confined to that process.
Uncharacterized SRAM energy stays unknown, while requests and waits still run.
"""
from pathlib import Path
from types import MethodType
from collections import Counter,deque
import importlib.util,inspect,json,math,sys,textwrap

def load(p):return json.loads(Path(p).read_bytes())

def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);x=importlib.util.module_from_spec(spec)
    sys.modules[name]=x;spec.loader.exec_module(x);return x

class Clock:
    name='conditional28';synchronous=True
    def __init__(self,mhz,cycles):
        self.period_ns=1000/mhz;self.chip_hz=self.mac_hz=mhz*1000000;self.mac_period_ns=self.period_ns;self.cycles=cycles
    def service_ns(self,name,legacy_ns):
        fast={'GU_crossK_align_add_macro':5,'down_crossK_align_add_macro':2,'GU_fixed8_quant_macro':4,
              'final_BF16_macro':3,'streaming_argmax_macro':7}
        return self.cycles.get(name,fast.get(name,math.ceil(legacy_ns/10-1e-8)))*self.period_ns
    def report(self):return dict(profile='conditional28',period_ns=self.period_ns,chip_hz=self.chip_hz,
        vector_cycles='retained named macro cycles;28nm PPA pending',DRAM='independent unchanged')

def unknown_sram_prices():
    from architecture_tlm.unified_v6.shared_memory import BeatSRAM
    original=BeatSRAM._tick;s=inspect.getsource(original)
    old='self.energy_pJ+=self.prices[kind]';assert s.count(old)==1
    s=s.replace(old,"if self.prices[kind] is None:self.count['unpriced_'+kind+'_words']+=1\n            else:self.energy_pJ+=self.prices[kind]")
    env=dict(original.__globals__);exec(compile(textwrap.dedent(s),'<28nm optional SRAM event price>','exec'),env);BeatSRAM._tick=env['_tick']
    def report(self,end):
        unknown=any(v is None for v in self.prices.values())
        return dict(capacity_bytes=self.capacity,allocated_bytes=self.top,physical_banks=self.nbank,
            word_bytes=self.word,clock_hz=1e9/self.period,access_ns=self.access_ns,
            fabric_GBs=self.fabric_words*self.word/self.period,counts=dict(self.count),
            by_tag={k:dict(v) for k,v in self.by_tag.items()},dynamic_mJ=None if unknown else self.energy_pJ/1e9,
            leakage_mJ=None if self.leak_W is None else self.nbank*self.leak_W*end/1e6,
            area_mm2=None if getattr(self,'area28_per_macro',None) is None else self.nbank*self.area28_per_macro,
            area_multiplier=1,energy_status='UNPRICED_ACTIONS_RETAINED' if unknown else 'EXPLICIT_MACRO_PRICE',
            regions=[dict(name=r.name,base=r.base,size=r.size,banks=list(r.banks)) for r in self.regions.values()])
    BeatSRAM.report=report

def retime(m,mhz,sram_cycles,macros):
    from architecture_tlm.unified_v6.ingress_sweep import FiniteIngress
    from architecture_tlm.attention_supply_front_20261107 import ordinary_pool
    h=m.h;p=1000/mhz;assert h.now==0 and not h.events
    m.clock=Clock(mhz,macros.get('vector_cycle_overrides',{}));m.mac_hz=mhz*1000000;m.compute_period_ns=p
    h.common_period_ns=h.issue_period=h.ingress_period_ns=p;h.ingress_last_tick=-p
    h.mem.period=p;h.mem.access_ns=sram_cycles*p
    prices=macros['SRAM']
    h.mem.prices={k:prices.get(k+'_pJ_per16B') for k in ('read','write')}
    h.mem.leak_W=prices.get('leak_W_per4KiB');h.mem.area28_per_macro=prices.get('area_mm2_per4KiB')
    a=h.ingress_clock_audit;a.update(ticks=0,off_edge_ticks=0,last_cycle=None,last_tick_ns=None,min_spacing_cycles=None,min_spacing_ns=None,
        ledger='integer'+str(p)+'ns cycles;parent dispatcher tolerance retained')
    def wake(self):
        if not self.ingress_scheduled and any(self.ingress):
            cycle=math.floor((self.now+1e-6)/p)+1
            if a['last_cycle'] is not None:cycle=max(cycle,a['last_cycle']+1)
            self.ingress_scheduled=True;self.later(cycle*p,self._ingress_tick)
    def tick(self):
        cycle=round(self.now/p);error=abs(self.now-cycle*p);assert error<=1.001e-6
        if a['last_cycle'] is not None:
            gap=cycle-a['last_cycle'];assert gap>=1
            a['min_spacing_cycles']=gap if a['min_spacing_cycles'] is None else min(a['min_spacing_cycles'],gap)
            a['min_spacing_ns']=a['min_spacing_cycles']*p
        a['ticks']+=1;a['last_cycle']=cycle;a['last_tick_ns']=cycle*p
        a['max_dispatch_offset_ns']=max(a['max_dispatch_offset_ns'],error)
        return FiniteIngress._ingress_tick(self)
    h._ingress_wake=MethodType(wake,h);h._ingress_tick=MethodType(tick,h)
    previous=h.report
    def report(self):
        r=previous();r['ingress'].update(clock_MHz=mhz,period_ns=p,
            theoretical_forward_GBps=self.per_channel*8*64/p,clock_audit=dict(a));return r
    h.report=MethodType(report,h)
    # Recreate captured ordinary-pool closures with the new explicit period.
    s=inspect.getsource(ordinary_pool).replace('period_ns in (4,10)','period_ns in (2,4,10)')
    env=dict(ordinary_pool.__dict__);exec(compile(s,'<28nm finite ordinary pool>','exec'),env)
    env['install'](m,256,4,True,p,8,True)
    from architecture_tlm.attention_supply_front_20261107 import finite_supply,pv_stream,qk_layout
    for owner,name,old,new in [(finite_supply,'consume_tile','4*period',str(macros['FMA_feedback_cycles'])+'*period'),
        (qk_layout,'stream_words','4*period',str(macros['FMA_feedback_cycles'])+'*period'),
        (pv_stream,'pv_consumer','7*period',str(macros['PV_feedback_cycles'])+'*period')]:
        s=inspect.getsource(getattr(owner,name));assert old in s
        env=dict(owner.__dict__);exec(compile(s.replace(old,new),'<28nm configurable pipeline macro>','exec'),env)
        setattr(owner,name,env[name])
    m.resource_contract.update(compute_MHz=mhz,SRAM_MHz=mhz,new_PPA='mixed measured and explicit macros')
    m.ordinary_pool_contract['SRAM_period_ns']=p
    m.compact_memory['bank_clock_MHz']=mhz
    parent=inspect.getclosurevars(m.phase.__func__).nonlocals['parent']
    def phase(self,name,generators,layer):
        pools=(self.qk_pool,self.norm_pool,self.top_pool,self.sampler_pool)
        assert self.pool_phase is None and all(not q.active and not q.waiters for q in pools)
        self.pool_phase=name
        try:
            if name in ('attention','O'):parent('pool_mode_switch',[h.delay(2*p)],layer);self.resource_audit['pool_switches']+=1
            return parent(name,generators,layer)
        finally:
            assert all(not q.active and not q.waiters for q in pools);self.pool_phase=None
    m.phase=MethodType(phase,m)

def finish_output(m,mode):
    p=m.compute_period_ns;c=m.p28_counts
    if mode=='GU':
        yield from m.h.delay(6*p) # two64 groups, groupII2, latency4
        c['scale64_groups']+=2;c['codec_g8']+=64;c['codec_u8']+=64
    else:c['codec_bf16']+=128
    yield from m.h.delay(9*p) # 128values/16lanes,II1,latency2
    c['staging_groups']+=1

def install_ffn(m,binding,cores):
    from architecture_tlm.module_refresh_20261107 import bindings
    core=binding['FFN_core'];p=m.compute_period_ns
    def contract(clock):
        assert clock==binding['clock_MHz']
        return dict(clock_MHz=clock,modes=core['modes'],profile_sha256=m.p28_binding_sha,implementation=core['price_origin'])
    bindings.core_contract=contract
    base=sys.modules['whole250.ffn_actor'];s=inspect.getsource(base)
    for old,new in [('core_contract(250)','core_contract(CLOCK)'),('65536+20000','65536+self.cross_gu_scale'),
                    ('align_time(h.now,4)','align_time(h.now,PERIOD)'),('ports[port]=begin+16','ports[port]=begin+4*PERIOD')]:
        assert old in s;s=s.replace(old,new)
    old="if k:\n                yield from h.transfer(self.common_state,offset,1024,False,'common_'+mode+'_state_read')"
    new="""if k+1==blocks:
                yield lambda:not self.p28_staging_busy
                self.p28_staging_busy=True
            if k:
                yield from h.transfer(self.common_state,offset,1024,False,'common_'+mode+'_state_read')"""
    assert s.count(old)==1;s=s.replace(old,new)
    old="yield from self.delay(10,'GU_fixed8_quant_macro' if mode=='GU' else 'final_BF16_macro')"
    assert s.count(old)==1;s=s.replace(old,'yield from finish_output(self,mode)')
    old="previous_commit[out]=k;expected[out]=k+1;occupied.remove(out)"
    assert s.count(old)==1;s=s.replace(old,'if k+1==blocks:self.p28_staging_busy=False\n            '+old)
    env=dict(CLOCK=binding['clock_MHz'],PERIOD=p,finish_output=finish_output)
    exec(compile(s,'<28nm shared FFN finite staging>','exec'),env)
    m.common_cores=cores;m.p28_staging_busy=False;m._common_stage=MethodType(env['common_stage'],m)

def front_A(m,r,offset):
    from architecture_tlm.unified_v6.shared_memory import Signal,align_time
    h=m.h;p=m.compute_period_ns;start=h.now;ready={};state=dict(next=0,live=0,peak=0)
    def fill():
        while state['live']<2 and state['next']<32:
            i=state['next'];state['next']+=1;state['live']+=1;state['peak']=max(state['peak'],state['live'])
            ready[i]=Signal();h.mem.submit(r,offset+i*16,16,False,'sampler_score_input',ready[i].set)
    fill()
    for i in range(32):
        yield ready[i];edge=align_time(h.now,p)
        if edge>h.now:yield from h.delay(edge-h.now)
        del ready[i];state['live']-=1;fill();yield from h.delay(p)
    # Measured67-cycle frontend =32inputs +3internal-tail +32gap/load handshakes.
    # Last32 are the backend input transfer, charged only once in time.
    yield from h.delay(35*p)
    m.p28_counts['front_queries']+=1
    return dict(start_ns=start,end_ns=h.now,passes=1,input_bytes=512,peak_input_words=state['peak'],
        frontend='S12F4 first;integer maxgap',shared_backend_load_cycles=32)

def screen(m,layer,g):
    from architecture_tlm.attention_supply_front_20261107 import qk_layout as qk
    h=m.h;r=m.att[g];p=m.compute_period_ns;c=m.p28_counts
    yield from m._append(layer,g,True)
    yield from h.transfer(m.vector,196608+g*6144+5120,1024,False,'query_feature_scan')
    lease=yield from m.top_pool.acquire(g,'feature')
    yield from qk.local_delay(m,4*164*p,'feature_topk_macro');c['top_feature']+=4;m.top_pool.release(g,lease)
    row=m.extra_input['rows'][(layer%3)*8+g]
    yield from qk.coarse(m,layer,g,row['dimensions']);yield from h.transfer(r,32768,16384,True,'coarse_scores')
    lease=yield from m.norm_pool.acquire(g,'normalize')
    for k in range(3):yield from h.transfer(r,32768,16384,False,'coarse_score_pass'+str(k+1))
    yield from qk.local_delay(m,1730*p,'SparQ_normalize_macro');c['norm_groups']+=1;m.norm_pool.release(g,lease)
    lease=yield from m.top_pool.acquire(g,'tokens')
    yield from qk.local_delay(m,815*p,'token_topk_macro');c['top_token']+=1;m.top_pool.release(g,lease)
    yield from qk.selected(m,layer,g,row['candidates']);yield from h.transfer(r,16384,2048,True,'selected_scores')

def sampled(m,layer,g):
    from architecture_tlm.digital_fair_20261105.joint_handoff.attention import adapter as old
    from architecture_tlm.attention_supply_front_20261107.pv_stream import pv_consumer
    h=m.h;r=m.att[g];p=m.compute_period_ns;base=m.kv_bases[layer,g]
    yield from m.compact_screen(layer,g)
    candidates=m.extra_input['rows'][(layer%3)*8+g]['candidates'];top=old.SAMPLED[m.attention_path]
    queries=[m.sample_input['samples']['%s/%d/%d/%d'%(top,m.seed,g,layer%3*4+head)] for head in range(4)]
    assert all(len(q['indices'])==64 for q in queries)
    m.actions['sampler_queries']+=4;m.actions['samples']+=256;m.actions['sample_output_BF16']+=512
    lease=yield from m.sampler_pool.acquire(g,'A_front_gap_sampler')
    queues=[deque() for _ in range(4)];busy=[False]*4;cache={};consumed=[0]*4;producer={'held':False}
    feedback=[[0.]*(128//m.pv_lanes) for _ in range(4)];head_issue=[h.now]*4;last=[h.now]
    audit=dict(layer=layer,group=g,lanes_per_head=m.pv_lanes,max_words_per_head=0,scalar_adds=0,backpressure_shift_ns=0.,front=[])
    m.resource_audit['PV'].append(audit);start=h.now
    def fetched(i):
        cache[i]='valid'
        for head in range(4):consume(head)
    consume=pv_consumer(m,r,queues,busy,cache,consumed,producer,lambda:None,feedback,head_issue,last,m.pv_lanes,audit)
    remaining=m.p28_sampler_remaining_cycles;first=remaining-65
    assert first>=0
    def stream():
        for head,q in enumerate(queries):
            audit['front'].append((yield from front_A(m,r,16384+head*512)))
            t=h.now;shift=0.
            for j,index in enumerate(q['indices']):
                due=t+(first+j)*p+shift
                if h.now<due:yield from h.delay(due-h.now)
                wait=h.now;yield lambda:sum(map(len,queues))<128
                shift+=h.now-wait;audit['backpressure_shift_ns']+=h.now-wait;queues[head].append(index)
                if index not in cache:
                    cache[index]='pending';m.actions['unique_V']+=1
                    h.dma('Attention'+str(g),base+2*m.N*256+candidates[index]*256,256,r,65536+index*256,'sample_V',lambda i=index:fetched(i))
                else:m.actions['V_fetch_reuse']+=1
                consume(head)
            end=t+remaining*p+shift
            if h.now<end:yield from h.delay(end-h.now)
            m.p28_counts['sampler_queries']+=1
        m.sampler_pool.release(g,lease)
    def drain():
        yield lambda:sum(consumed)==256
        if h.now<last[0]:yield from h.delay(last[0]-h.now)
    yield from m._parallel([stream(),drain()]);assert not any(queues) and not any(busy)
    assert audit['scalar_adds']==32768;audit.update(sample_count=256,duration_ns=h.now-start)
    m.actions['sample_queue_peak_capacity']=128
    yield from h.delay(m.p28_macros['PV_output_cycles']*p) # explicit pending28nm format macro
    yield from h.transfer(r,122880,1024,True,'attention_output')

def build(snapshot,runtime,deps,binding,binding_sha,backend,cores,sram_cycles,macros,seed=17,include_head=False,execution_layers=36):
    main=module('p28_current_host',snapshot/'glue/current_mainline.py')
    factory,identity=main.environment(snapshot,runtime,deps,250)
    unknown_sram_prices()
    h,m=factory(backend,cores=cores if cores in (2,3) else 2,layers=36,include_lm=include_head,seed=seed,
        samples=load(snapshot/'inputs/SAMPLES.json'),attention_input=load(snapshot/'inputs/representative.json'),mode='ising',ffn='sc')
    m.cross_clock=binding['clock_MHz'];m.p28_binding_sha=binding_sha;m.p28_counts=Counter()
    # Supply timing authority before the shape adapter executes its actor rewrite.
    from architecture_tlm.module_refresh_20261107 import bindings
    bindings.core_contract=lambda clock:dict(clock_MHz=clock,modes=binding['FFN_core']['modes'],profile_sha256=binding_sha,implementation='28nm')
    shape=load(snapshot/'glue/CURRENT_WORKLOAD_PLAN.json')['models']['qwen3_4b']['shape']
    # Truncated-prefix+head probes require a matching finalnorm tag;otherwise
    # an unused next-layer prefetch can occupy the finalnorm's physical slot.
    main.rebuild(m,shape,execution_layers if include_head else shape['layers'],'SC_ising');m.p28_macros=macros
    retime(m,binding['clock_MHz'],sram_cycles,macros)
    install_ffn(m,binding,cores)
    m.compact_screen=MethodType(screen,m);m.attention_group=MethodType(sampled,m)
    card=binding['attention_cards']['gap_sampler_'+str(binding['clock_MHz'])]
    m.p28_sampler_remaining_cycles=max(65,math.ceil(card['mean_query_cycles_excluding_interquery_gap'])-32)
    return h,m,main,shape,identity
