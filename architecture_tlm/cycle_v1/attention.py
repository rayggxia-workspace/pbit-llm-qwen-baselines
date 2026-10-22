"""One address-correct Attention query with dynamic sampler feedback.

The entry boundary is an already projected/RoPE-adjusted Q and KV cache plus
an explicit candidate list. Projection, RoPE, candidate screening and multihead
GQA union are deliberately outside this query prototype. No whole-model/PPL or
physical timing claim is implied. All tensor storage here is explicitly FP32.
"""
from collections import Counter, deque
from dataclasses import dataclass
import math
import random
import struct

from .contracts import Buffer, Clock, Operation, Resource
from .kernel import Kernel
from .memory import MemoryPort, MemoryRequest
from .ffn import fp32, sigmoid
from . import rng_protocol


@dataclass(frozen=True)
class AttentionConfig:
    mode: str = 'exact'
    samples: int = 32
    seed: int = 0
    capacity: int = 512
    source_lanes: int = 64
    output_capacity: int = 1
    kv_capacity_bytes: int = 4096
    score_capacity_bytes: int = 32768
    mac_lanes: int = 64
    source_latency: int = 2
    source_ii: int = 1
    histogram_delay_cycles: int = 0
    max_proposals_per_sample: int = 64
    rank_retry_cap: int = 1024
    max_shift: int = 24
    burn_updates: int = 0
    winner_shift: float = 0.0
    response: str = 'q256'
    drive_step: float = 0.125
    cdc_cycles: int = 3
    random_backend: str = 'native'
    seed_word_interval: int = 100
    seed_startup: int = 10
    reseed_cycles: int = 100000000
    native_hold_cycles: int = 0
    vector_lanes: int = 64
    exp_lanes: int = 16
    exp_latency: int = 8
    reciprocal_latency: int = 12
    drive_latency: int = 3
    lut_latency: int = 2

    def validate(self):
        if self.mode not in ('exact','pv','winner','rejection'):
            raise ValueError('unknown Attention mode')
        if self.response not in ('q256','ideal_sigmoid'):
            raise ValueError('unknown source response')
        if self.random_backend not in ('native','behavioral','replay'):
            raise ValueError('unknown random backend')
        if self.random_backend=='native' and self.response!='q256' and self.mode in ('winner','rejection'):
            raise ValueError('native comparator response is q256, not ideal sigmoid')
        for name in ('samples','capacity','source_lanes','output_capacity','kv_capacity_bytes',
                     'score_capacity_bytes','mac_lanes','source_latency','source_ii',
                     'max_proposals_per_sample','rank_retry_cap','cdc_cycles','vector_lanes',
                     'exp_lanes','exp_latency','reciprocal_latency','drive_latency','lut_latency'):
            if type(getattr(self,name)) is not int or getattr(self,name)<1:
                raise ValueError(name+' must be positive integer')
        if type(self.seed_word_interval) is not int or self.seed_word_interval<1:
            raise ValueError('positive seed-word interval required')
        if any(type(v) is not int or v<0 for v in (self.seed_startup,self.reseed_cycles,self.native_hold_cycles)):
            raise ValueError('nonnegative native source timing required')
        for name in ('histogram_delay_cycles','max_shift','burn_updates'):
            if type(getattr(self,name)) is not int or getattr(self,name)<0:
                raise ValueError(name+' must be nonnegative integer')
        if self.samples >= 2**32:
            raise ValueError('sample count exceeds uint32 histogram')
        if not math.isfinite(self.winner_shift) or self.winner_shift<0 or not math.isfinite(self.drive_step) or self.drive_step<=0:
            raise ValueError('invalid drive configuration')
        if self.mode=='rejection' and (self.burn_updates or self.winner_shift):
            raise ValueError('rejection has adaptive shift, not chain burn/winner shift')


class SamplerCapError(RuntimeError):
    """No numerical fallback or valid partial output on a bounded FSM failure."""


def default_resources(config=None):
    c=config or AttentionConfig()
    clock=Clock('core',10000)
    return [Resource('control',clock,1,capacity=16),
            Resource('qk',clock,3,capacity=4),
            Resource('vector',clock,3,capacity=4),
            Resource('attention_exp',clock,c.exp_latency,capacity=2),
            Resource('sampler',clock,1,capacity=1),
            Resource('rng',clock,c.source_latency,ii_cycles=c.source_ii,capacity=2),
            Resource('v_accumulate',clock,3,capacity=1)]+rng_protocol.resources()


def default_buffers(config=None,prefix='attention'):
    c=config or AttentionConfig()
    return [Buffer(prefix+'.kv',c.kv_capacity_bytes,initial=c.kv_capacity_bytes,unit='byte credit'),
            Buffer(prefix+'.scores',c.score_capacity_bytes,initial=c.score_capacity_bytes,unit='byte credit'),
            Buffer(prefix+'.samples',c.output_capacity,unit='index')]+rng_protocol.buffers(prefix)


def make_kernel(config=None,memory_latency=4):
    c=config or AttentionConfig()
    return Kernel(default_resources(c),default_buffers(c),memory_ports=[
        MemoryPort('dram',Clock('dram',12500),latency_cycles=memory_latency,window=4,strict_reads=True),
        MemoryPort('sram',Clock('sram',12500),latency_cycles=2,window=4,strict_reads=True)])


def validate_fixture(fixture,config):
    q=[fp32(x) for x in fixture['q']]
    keys=[[fp32(x) for x in row] for row in fixture['k']]
    values=[[fp32(x) for x in row] for row in fixture['v']]
    ids=list(fixture.get('candidate_ids',range(len(keys))))
    if not q or not keys or not values or len(keys)!=len(values):
        raise ValueError('nonempty matching KV cache required')
    if any(len(row)!=len(q) for row in keys) or not values[0] or any(len(row)!=len(values[0]) for row in values):
        raise ValueError('Q/K/V shape mismatch')
    if any(not math.isfinite(x) for x in q) or any(not math.isfinite(x) for row in keys+values for x in row):
        raise ValueError('finite QKV required')
    if not ids or any(type(i) is not int or not 0<=i<len(keys) for i in ids) or len(set(ids))!=len(ids):
        raise ValueError('candidate IDs must be unique valid physical token indices')
    if len(ids)>config.capacity:
        raise ValueError('candidate capacity exceeded; no silent truncation or unsupported batching')
    if max(len(q),len(values[0]))*4>config.kv_capacity_bytes or sum(local_state_bytes(len(ids),len(q),len(values[0]),config).values())>config.score_capacity_bytes:
        raise ValueError('query exceeds finite KV/score storage')
    return q,keys,values,ids


def local_state_bytes(n,d,dv,c):
    """Conservative simultaneous local storage, including functional doubles.

    No undocumented overlap of score/probability/histogram/drive storage is
    assumed. Source internal PRNG state belongs to its uncharacterized backend;
    the request/response staging and all query-visible state are charged here.
    """
    sampled=c.mode!='exact'
    network=c.mode in ('winner','rejection')
    return dict(q=d*4,output_accumulator=dv*4,logits=n*4,candidate_map=n*4,
        softmax_probabilities=n*8 if c.mode in ('exact','pv') else 0,
        cdf_prefix=n*8 if c.mode=='pv' else 0,
        pv_index_buffer=c.samples*4 if c.mode=='pv' else 0,
        histogram=n*4 if sampled else 0,drive_values=n*8 if network else 0,
        q256_thresholds=n*2 if network and c.response=='q256' else 0,
        proposal_mask_and_valid=2*math.ceil(n/8) if network else 0,
        output_fifo=c.output_capacity*4 if sampled else 0,
        fsm_scalar_state=64)


def softmax(logits):
    m=max(logits)
    weights=[math.exp(x-m) for x in logits]
    total=math.fsum(weights)
    inverse=1/total
    return [x*inverse for x in weights]


class _Source:
    def __init__(self,fixture,c):
        self.c=c
        self.rng=random.Random(c.seed)
        self.replay=fixture.get('random_replay',{})
        self.frame_index=self.fair_index=self.uniform_index=0

    def probabilities(self,drives):
        if self.c.response=='ideal_sigmoid':
            return [sigmoid(d) for d in drives]
        codes=[max(-255,min(255,math.floor(d/self.c.drive_step+.5))) for d in drives]
        return [math.floor(256*sigmoid(code*self.c.drive_step)+.5)/256 for code in codes]

    def frame(self,drives):
        probabilities=self.probabilities(drives)
        frames=self.replay.get('frames')
        if frames is not None:
            if self.frame_index>=len(frames):
                raise ValueError('frozen biased-frame replay exhausted')
            item=frames[self.frame_index]
            bits=item.get('bits') if isinstance(item,dict) else item
            if isinstance(item,dict) and 'drives' in item:
                if len(item['drives'])!=len(drives) or any(abs(a-b)>1e-9 for a,b in zip(item['drives'],drives)):
                    raise ValueError('frozen frame drive does not match live feedback state')
            bits=list(bits)
            if len(bits)!=len(drives) or any(type(b) is not bool for b in bits):
                raise ValueError('replay frame has wrong lane count or nonboolean bits')
        elif self.c.response=='q256':
            bits=[self.rng.getrandbits(8)<round(p*256) for p in probabilities]
        else:
            bits=[self.rng.random()<p for p in probabilities]
        self.frame_index+=1
        return bits

    def fair(self,width):
        if not width: return 0
        values=self.replay.get('fair')
        if values is not None:
            if self.fair_index>=len(values): raise ValueError('frozen fair replay exhausted')
            value=values[self.fair_index]
        else: value=self.rng.getrandbits(width)
        self.fair_index+=1
        if type(value) is not int or not 0<=value<1<<width:
            raise ValueError('fair response outside requested width')
        return value

    def uniform(self):
        values=self.replay.get('uniforms')
        if values is not None:
            if self.uniform_index>=len(values): raise ValueError('frozen uniform replay exhausted')
            value=values[self.uniform_index]
        else: value=self.rng.getrandbits(32)/2**32
        self.uniform_index+=1
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<1:
            raise ValueError('uniform response must be in [0,1)')
        return value


def build_attention(kernel,fixture,config=None,prefix='attention',*,
                    address_layout=None,shared_k=None,value_sink=None):
    """Build one query; optional group hooks retain its sampler/state semantics.

    The GQA owner supplies disjoint query addresses and real shared K reads,
    records every QK consumer, and may coordinate the V union after sampling.
    Default execution remains the original standalone query contract.
    """
    c=config or AttentionConfig()
    c.validate()
    q,keys,values,candidates=validate_fixture(fixture,c)
    if fixture.get('random_replay') and c.random_backend!='replay':
        raise ValueError('frozen source requires explicit random_backend=replay')
    if c.random_backend=='replay' and not fixture.get('random_replay'):
        raise ValueError('replay backend requires frozen source fixture')
    n,d,dv=len(candidates),len(q),len(values[0])
    storage=local_state_bytes(n,d,dv,c)
    score_bytes=sum(storage.values())
    source=_Source(fixture,c)
    pack=lambda row:struct.pack('<'+'f'*len(row),*row)
    unpack=lambda data:list(struct.unpack('<'+'f'*(len(data)//4),data))
    qbase,kbase,vbase,hbase=0x70000000,0x71000000,0x72000000,0x73000000
    output_base=0x74000000
    if address_layout is not None:
        qbase,kbase,vbase,hbase,output_base=(address_layout[name]
            for name in ('q','k','v','histogram','output'))
    kernel.load_memory('sram',qbase,pack(q))
    if shared_k is None:
        for index,row in enumerate(keys): kernel.load_memory('dram',kbase+index*d*4,pack(row))
        for index,row in enumerate(values): kernel.load_memory('dram',vbase+index*dv*4,pack(row))
    kernel.load_memory('sram',hbase,bytes(n*4))
    state=dict(output=None,logits=[None]*n,probabilities=None,local_indices=[],physical_indices=[],
               histogram={},frames=[],proposals=0,rejected_empty=0,rejected_multi=0,
               source_requests=0,source_frames=0,source_waves=0,fair_draws=0,rank_retries=0,
               winner_holds=0,winner_switches=0,algorithm_updates=0,
               operation_ids=[],K_addresses=[],V_addresses=[],local_state_bytes=storage,
               native_biased_generated_lanes=0,native_biased_used_lanes=0,native_biased_padding_lanes=0,
               native_fair_generated_bits=0,native_fair_used_bits=0,native_fair_unused_bits=0,
               provenance=dict(scope='one query from preprojected RoPE Q/K and explicit candidate IDs',
                  tensor_format='FP32 Q/K/V storage; not BF16 traffic',
                  arithmetic='QK double-precision products/fsum rounded to FP32; functional double-precision Softmax; per-term FP32 V accumulation; not a bit-true hardware datapath',
                  random_source='Issue95 native Bivium protocol' if c.random_backend=='native' and c.mode!='exact' else 'unused exact digital path' if c.mode=='exact' else 'frozen replay' if c.random_backend=='replay' else 'Python Random behavioral local PRNG',
                  response=c.response,drive_step=c.drive_step,
                  independent_samples=(True if c.mode=='rejection' and c.response=='ideal_sigmoid' and c.random_backend=='behavioral' else False),
                  independence_boundary='ideal rejection independence assumes independent ideal response; q256 adaptive-state samples and frozen replays have no IID guarantee',
                  pv_sampling='one-offset systematic sampling; outputs are not independent' if c.mode=='pv' else None,
                  timing='configured, uncharacterized',candidate_overflow='error',
                  V_prefetch='bounded ordered lookahead: at most floor(KV_credit_bytes/V_row_bytes) rows ahead of consumption; replies may reorder within this window',
                  omitted='QKV projections, RoPE, screening, GQA union, Wo, full decoder',
                  storage_boundary='finite query-local state and KV response credits; backing DRAM/SRAM address space has no total-capacity allocator',
                  trace_storage='frames and retained index histories are simulator evidence, not additional hardware queues',
                  source_state='native or behavioral source state is backend-owned and separately reported; source staging/masks are in local_state_bytes',
                  cdc=f'producer completion to destination acceptance: {c.cdc_cycles} destination edges; 3 models two synchronizers plus old-state consumer',
                  fixture=fixture.get('provenance',{})))
    if c.mode=='pv': state['provenance']['independent_samples']=False
    if c.mode=='rejection' and c.response!='ideal_sigmoid':
        state['provenance']['target']='quantized response; no inherited exact-softmax or model-PPL claim'
    else: state['provenance']['target']='conditional numeric query, not model quality validation'
    free_kv,free_scores,queue=prefix+'.kv',prefix+'.scores',prefix+'.samples'
    pending=deque()
    consumer_busy=[False]
    consumed=[0]
    sampler_done=[False]
    final_started=[False]
    serial=[0]
    biased_names=[f'biased_{i}' for i in range(math.ceil(min(c.source_lanes,n if c.mode=='winner' else max(0,n-1))/20))]
    kinds={name:'bivium' for name in biased_names} if c.mode in ('winner','rejection') else {}
    kinds['fair']='bivium'
    native=(rng_protocol.NativeRandomService(kernel,prefix,kinds,c.seed,c.seed_word_interval,c.seed_startup,
        c.reseed_cycles,c.native_hold_cycles,state['operation_ids']) if c.random_backend=='native' and c.mode!='exact' else None)
    state['native_biased_lanes']=len(biased_names)*20 if native else 0

    def add(suffix,resource,**kwargs):
        ident=prefix+'.'+suffix
        kwargs.setdefault('cdc_cycles',c.cdc_cycles)
        kernel.add(Operation(ident,resource,**kwargs))
        state['operation_ids'].append(ident)
        return ident

    def unique(tag):
        value=f'{tag}.{serial[0]}'
        serial[0]+=1
        return value

    def finish_values(dependency,weights):
        if final_started[0]: return
        final_started[0]=True
        def finish_accumulation(last,acc):
            def finished(k,op):
                state['output']=list(acc)
                state['retained_samples']=len(state['local_indices'])
                state['unique_V']=len(weights)
                state['output_address']=output_base
                state['output_bytes']=dv*4
                def stored(k2,op2):
                    state['complete_ps']=k2.now_ps
                    state['native_random']=native.report() if native else None
                add('output.write','sram',deps=(op.id,),
                    memory=MemoryRequest(output_base,dv*4,write=True,data=pack(acc)),
                    outputs={free_scores:score_bytes},on_complete=stored,actions={'output_write_bytes':dv*4})
            add('complete','control',deps=(last,),on_complete=finished)
        if value_sink is not None:
            physical_weights={candidates[i]:weights[i] for i in weights}
            state['V_addresses']=[vbase+i*dv*4 for i in sorted(physical_weights)]
            value_sink(state,dependency,physical_weights,finish_accumulation)
            return
        acc=[0.0]*dv
        last=dependency
        prefetch_window=c.kv_capacity_bytes//(dv*4)
        retired=[]
        for order,local in enumerate(sorted(weights,key=lambda i:candidates[i])):
            physical=candidates[local]
            address=vbase+physical*dv*4
            state['V_addresses'].append(address)
            # A later response must never occupy the last credit needed by an
            # earlier ordered accumulator. Restrict eligibility, not just the
            # total bytes, so sparse numeric IDs cannot deadlock under the
            # kernel's stable lexicographic arbitration.
            read_deps=(dependency,) if order<prefetch_window else (retired[order-prefetch_window],)
            read=add(f'V.{physical}.read','dram',deps=read_deps,
                memory=MemoryRequest(address,dv*4),inputs={free_kv:dv*4},
                actions={'V_read_bytes':dv*4},metadata={'physical_token':physical,'multiplicity':state['histogram'].get(physical)})
            def accumulate(k,op,read=read,weight=weights[local],physical=physical):
                row=unpack(k.memory_reads[read])
                if row!=values[physical]: raise AssertionError('V address/payload mismatch')
                for j,value in enumerate(row): acc[j]=fp32(acc[j]+fp32(weight*value))
            last=add(f'V.{physical}.accumulate','v_accumulate',deps=(read,last),
                latency_cycles=3+math.ceil(dv/c.mac_lanes)-1,on_complete=accumulate,
                outputs={free_kv:dv*4},actions={'V_weighted_mac':dv})
            retired.append(last)
        finish_accumulation(last,acc)

    def maybe_finish(dependency):
        if sampler_done[0] and consumed[0]==c.samples:
            counts=Counter(state['local_indices'])
            if sum(counts.values())!=c.samples or sum(state['histogram'].values())!=c.samples:
                raise AssertionError('histogram lost sample multiplicity')
            finish_values(dependency,{i:count/c.samples for i,count in counts.items()})

    def consume_next(dependency):
        if consumer_busy[0] or not pending: return
        local,emit_id=pending.popleft()
        consumer_busy[0]=True
        label=unique('histogram')
        read=add(label+'.read','sram',deps=tuple(dict.fromkeys((dependency,emit_id))),
            memory=MemoryRequest(hbase+local*4,4),inputs={queue:1},
            earliest_ps=kernel.now_ps+c.histogram_delay_cycles*10000,
            actions={'histogram_read':1})
        def read_cb(k,op):
            old=struct.unpack('<I',k.memory_reads[op.id])[0]
            if old>=2**32-1: raise OverflowError('histogram counter overflow')
            def written(k2,op2):
                state['histogram'][candidates[local]]=old+1
                consumed[0]+=1
                consumer_busy[0]=False
                consume_next(op2.id)
                maybe_finish(op2.id)
            add(label+'.write','sram',deps=(op.id,),
                memory=MemoryRequest(hbase+local*4,4,write=True,data=struct.pack('<I',old+1)),
                on_complete=written,actions={'histogram_write':1})
        # callback is immutable in Operation; replace construction above by
        # registering a dependent decoder, preserving actual SRAM response.
        def decode(k,op):
            class ReadView:
                id=read
            read_cb(k,ReadView())
        add(label+'.decode','control',deps=(read,),on_complete=decode)

    def emit(local,dependency,next_callback):
        index=len(state['local_indices'])
        def emitted(k,op):
            state['local_indices'].append(local)
            state['physical_indices'].append(candidates[local])
            pending.append((local,op.id))
            consume_next(op.id)
            next_callback(op.id)
        add(f'emit.{index}','sampler',deps=(dependency,),outputs={queue:1},on_complete=emitted,
            actions={'sample_output':1},metadata={'local_index':local,'physical_token':candidates[local]})

    def mark_done(dependency):
        sampler_done[0]=True
        maybe_finish(dependency)

    def fair(width,dependency,callback,label):
        if width==0:
            callback(0,dependency)
            return
        if native:
            if width>160: raise ValueError('native fair Bivium word width exceeded')
            def response(data,done):
                state['fair_draws']+=1
                state['native_fair_generated_bits']+=160
                state['native_fair_used_bits']+=width
                state['native_fair_unused_bits']+=160-width
                value=sum(w<<(8*i) for i,w in enumerate(data['words']['fair']))&((1<<width)-1)
                callback(value,done)
            native.frame(unique(label),{'fair':[128]*20},(dependency,),response)
            return
        def got(k,op):
            state['fair_draws']+=1
            callback(source.fair(width),op.id)
        add(unique(label),'rng',deps=(dependency,),latency_cycles=c.source_latency+math.ceil(width/c.source_lanes)-1,
            on_complete=got,actions={'fair_random_bits':width})

    def draw(drives,dependency,callback):
        frame=state['source_requests']
        state['source_requests']+=1
        state['source_frames']+=bool(drives)
        # The source's complete frame is a frozen functional response; each
        # physical wave is still accepted/completed independently below.
        bits=[None]*len(drives)
        source_bits=[None]
        previous=dependency
        for start in range(0,len(drives),c.source_lanes):
            count=min(c.source_lanes,len(drives)-start)
            def returned(k,op,start=start,count=count):
                if source_bits[0] is None: source_bits[0]=source.frame(drives)
                bits[start:start+count]=source_bits[0][start:start+count]
            label=f'frame.{frame}.wave.{start//c.source_lanes}'
            if native:
                q=[round(p*256) for p in source.probabilities(drives[start:start+count])]
                padded=q+[0]*(len(biased_names)*20-len(q))
                requests={name:padded[i*20:(i+1)*20] for i,name in enumerate(biased_names)}
                def received(data,done,start=start,count=count):
                    delivered=[bit for name in biased_names for bit in data['bits'][name]]
                    bits[start:start+count]=delivered[:count]
                    state['native_biased_generated_lanes']+=len(delivered)
                    state['native_biased_used_lanes']+=count
                    state['native_biased_padding_lanes']+=len(delivered)-count
                previous=native.frame(label,requests,(previous,),received)
            else:
                previous=add(label,'rng',deps=(previous,),
                    on_complete=returned,actions={'biased_random_lanes':count,
                       'random_bits':count*(8 if c.response=='q256' else 53)},
                    metadata={'frame':frame,'lane_start':start,'lanes':count,'source_lanes':c.source_lanes})
            state['source_waves']+=1
        def reduced(k,op):
            if any(b is None for b in bits): raise AssertionError('incomplete source response')
            add(f'frame.{frame}.decision','sampler',deps=(op.id,),
                on_complete=lambda k2,op2:callback(bits,op2.id),actions={'sampler_decision':1})
        add(f'frame.{frame}.reduce','sampler',deps=(previous,),
            latency_cycles=max(1,math.ceil(max(0,(len(drives)-1).bit_length())/2)),
            on_complete=reduced,actions={'proposal_frame':1,'active_reduce_nodes':max(0,len(drives)-1)})

    def begin_sampler(dependency):
        logits=state['logits']
        ref=state['max_index']
        if c.mode=='pv':
            def built_cdf(k,op):
                cumulative=0.0
                state['cdf']=[]
                for probability in state['probabilities']:
                    cumulative+=probability
                    state['cdf'].append(cumulative)
            cdf_ready=add('pv.cdf_build','vector',deps=(dependency,),latency_cycles=n,
                actions={'cdf_prefix_serial_add':n},on_complete=built_cdf,
                metadata={'contract':'one FP64 functional prefix item per cycle; physical circuit uncharacterized'})
            def offset_value(uniform,dependency):
                def scan(k,op):
                    out=[]
                    local=0
                    for sample in range(c.samples):
                        target=(uniform+sample)/c.samples
                        while state['cdf'][local]<=target and local+1<n:
                            local+=1
                        out.append(local)
                    def next_index(index,dep):
                        if index==len(out): mark_done(dep)
                        else: emit(out[index],dep,lambda done:next_index(index+1,done))
                    next_index(0,op.id)
                add('pv.cdf_scan','vector',deps=(dependency,cdf_ready),latency_cycles=n+c.samples,
                    actions={'cdf_serial_scan_slots':n+c.samples,'cdf_sample_indices':c.samples},
                    on_complete=scan,metadata={'contract':'ordered CDF/sample merge, one slot per cycle including tail padding'})
            if native: fair(32,dependency,lambda value,done:offset_value(value/2**32,done),'pv.offset')
            else:
                add('pv.offset','rng',deps=(dependency,),on_complete=lambda k,op:offset_value(source.uniform(),op.id),
                    actions={'uniform_random_bits':32})
            return
        if c.mode=='winner':
            winner=[ref]
            drives=[z-c.winner_shift for z in state['base_drives']]
            def step(index,dep):
                if index==c.samples+c.burn_updates:
                    mark_done(dep)
                    return
                def responded(bits,ready):
                    active=[i for i,b in enumerate(bits) if b]
                    previous=winner[0]
                    state['proposals']+=1
                    def commit(selected,commit_dep):
                        winner[0]=selected
                        state['algorithm_updates']+=1
                        state['winner_holds' if selected==previous else 'winner_switches']+=1
                        state['frames'].append(dict(frame=index,active_count=len(active),previous=previous,
                                                    winner=selected,retained=index>=c.burn_updates))
                        if index<c.burn_updates:
                            add(f'burn.{index}','sampler',deps=(commit_dep,),on_complete=lambda k,op:step(index+1,op.id),
                                actions={'burn_commit':1})
                        else: emit(selected,commit_dep,lambda done:step(index+1,done))
                    if not active or bits[previous]: commit(previous,ready)
                    else:
                        width=(len(active)-1).bit_length()
                        def rank(attempt,rank_dep):
                            if attempt>=c.rank_retry_cap:
                                state['status']='failed_rank_cap'
                                raise SamplerCapError('uniform rank cap: no biased fallback')
                            def chosen(value,ready2):
                                if value<len(active):
                                    add(unique('winner_rank_select'),'sampler',deps=(ready2,),
                                        latency_cycles=max(1,math.ceil((n-1).bit_length()/2)),
                                        actions={'rank_tree_visits':(n-1).bit_length()},
                                        on_complete=lambda k3,op3:commit(active[value],op3.id))
                                else:
                                    state['rank_retries']+=1
                                    rank(attempt+1,ready2)
                            fair(width,rank_dep,chosen,'winner_rank')
                        rank(0,ready)
                draw(drives,dep,responded)
            step(0,dependency)
            return
        shift=[0]
        nonref=[i for i in range(n) if i!=ref]
        def proposal(dep):
            if len(state['local_indices'])==c.samples:
                mark_done(dep)
                return
            if state['proposals']>=c.samples*c.max_proposals_per_sample:
                state['status']='failed_proposal_cap'
                raise SamplerCapError('proposal cap: no IID fallback or valid partial result')
            old_shift=shift[0]
            drives=[state['base_drives'][i]-old_shift*math.log(2.0) for i in nonref]
            def responded(bits,ready):
                active=[i for i,b in zip(nonref,bits) if b]
                state['proposals']+=1
                def decision(address,new_shift,decision_dep):
                    shift[0]=new_shift
                    state['frames'].append(dict(proposal=state['proposals']-1,active_count=len(active),
                        shift=old_shift,next_shift=new_shift,accepted=address is not None,local_index=address))
                    def after_feedback(final_dep):
                        if address is not None: emit(address,final_dep,proposal)
                        else: proposal(final_dep)
                    if new_shift!=old_shift:
                        add(unique('offset_reprogram'),'vector',deps=(decision_dep,),
                            latency_cycles=c.drive_latency+c.lut_latency+math.ceil(max(1,len(nonref))/c.vector_lanes)-1,
                            ii_cycles=max(1,math.ceil(len(nonref)/c.vector_lanes)),
                            actions={'drive_reprogram_values':len(nonref),'drive_subtract':len(nonref),
                                     'q256_lut_lookup':len(nonref) if c.response=='q256' else 0,'offset_changes':1},
                            on_complete=lambda k,op:after_feedback(op.id))
                    else: after_feedback(decision_dep)
                if len(active)==1: decision(active[0],old_shift,ready)
                elif len(active)>1:
                    state['rejected_multi']+=1
                    decision(None,min(c.max_shift,old_shift+1),ready)
                else:
                    def corrected(value,ready2):
                        if value==0: decision(ref,old_shift,ready2)
                        else:
                            state['rejected_empty']+=1
                            decision(None,max(0,old_shift-1),ready2)
                    fair(old_shift,ready,corrected,'empty_correction')
            draw(drives,dep,responded)
        proposal(dependency)

    qread=add('Q.read','sram',memory=MemoryRequest(qbase,d*4),inputs={free_scores:score_bytes},actions={'Q_read_bytes':d*4})
    qk_done=[]
    for local,physical in enumerate(candidates):
        address=kbase+physical*d*4
        state['K_addresses'].append(address)
        if shared_k is not None:
            read,cache_ready=shared_k.read(physical)
            read_dependencies=(qread,read,cache_ready)
        else:
            read=add(f'K.{physical}.read','dram',memory=MemoryRequest(address,d*4),
                inputs={free_kv:d*4},actions={'K_read_bytes':d*4},metadata={'physical_token':physical})
            read_dependencies=(qread,read)
        def dot(k,op,read=read,local=local,physical=physical):
            actual_q=unpack(k.memory_reads[qread])
            row=unpack(k.memory_reads[read])
            if actual_q!=q or row!=keys[physical]: raise AssertionError('Q/K address payload mismatch')
            state['logits'][local]=fp32(math.fsum(a*b for a,b in zip(actual_q,row))/math.sqrt(d))
        qk_done.append(add(f'QK.{local}','qk',deps=read_dependencies,
            latency_cycles=3+math.ceil(d/c.mac_lanes)-1,on_complete=dot,
            outputs={} if shared_k is not None else {free_kv:d*4},actions={'QK_mac':d}))
        if shared_k is not None: shared_k.consume(physical,qk_done[-1])
    def prepared(k,op):
        if c.mode=='exact':
            finish_values(op.id,{i:p for i,p in enumerate(state['probabilities'])})
        else: begin_sampler(op.id)
    batches=max(1,math.ceil(n/c.vector_lanes))
    reduction_latency=max(1,(min(n,c.vector_lanes)-1).bit_length()+batches-1+(batches-1).bit_length())
    def found_max(k,op):
        state['max_index']=max(range(n),key=state['logits'].__getitem__)
        state['score_max']=state['logits'][state['max_index']]
    maximum=add('score.max_reduce','vector',deps=tuple(qk_done),
        latency_cycles=reduction_latency,ii_cycles=batches,on_complete=found_max,
        actions={'score_max_compare':n-1},
        metadata={'lanes':c.vector_lanes,'contract':'pipelined lane tree, finite batches, final batch tree; uncharacterized'})
    if c.mode in ('exact','pv'):
        def exponentiated(k,op):
            # Reuse the allocated double-precision probability scratch in place.
            state['probabilities']=[math.exp(value-state['score_max']) for value in state['logits']]
        exp_batches=math.ceil(n/c.exp_lanes)
        exponent=add('score.subtract_exp','attention_exp',deps=(maximum,),
            latency_cycles=c.exp_latency+exp_batches-1,ii_cycles=exp_batches,
            on_complete=exponentiated,actions={'score_subtract':n,'exp_values':n},
            metadata={'lanes':c.exp_lanes,'latency':c.exp_latency,'II_per_lane':1,
                      'numeric':'functional double precision; no inherited approximate-RTL PPA'})
        def summed(k,op): state['denominator']=math.fsum(state['probabilities'])
        summation=add('score.sum_reduce','vector',deps=(exponent,),latency_cycles=reduction_latency,
            ii_cycles=batches,on_complete=summed,actions={'softmax_sum_add':n-1},metadata={'lanes':c.vector_lanes})
        def inverted(k,op): state['inverse_denominator']=1/state['denominator']
        inverse=add('score.reciprocal','vector',deps=(summation,),latency_cycles=c.reciprocal_latency,
            on_complete=inverted,actions={'softmax_reciprocal':1},metadata={'functional_results':1})
        def normalized(k,op):
            state['probabilities']=[value*state['inverse_denominator'] for value in state['probabilities']]
        ready=add('score.normalize','vector',deps=(inverse,),latency_cycles=3+batches-1,ii_cycles=batches,
            on_complete=normalized,actions={'softmax_normalize_multiply':n,'softmax_values':n},metadata={'lanes':c.vector_lanes})
    else:
        def centered(k,op): state['base_drives']=[value-state['score_max'] for value in state['logits']]
        centered_id=add('score.center_drives','vector',deps=(maximum,),
            latency_cycles=c.drive_latency+batches-1,ii_cycles=batches,on_complete=centered,
            actions={'drive_subtract':n},metadata={'lanes':c.vector_lanes})
        drive_count=n if c.mode=='winner' else n-1
        ready=add('score.program_drives','vector',deps=(centered_id,),
            latency_cycles=c.lut_latency+max(1,math.ceil(drive_count/c.vector_lanes))-1,
            ii_cycles=max(1,math.ceil(drive_count/c.vector_lanes)),
            actions={'drive_program_values':drive_count,'q256_lut_lookup':drive_count if c.response=='q256' else 0},
            metadata={'lanes':c.vector_lanes,'contract':'drive quantization/LUT cache populated before first source request'})
    add('score_prepare','control',deps=(ready,),on_complete=prepared)
    return state


def reference_attention(fixture,local_indices=None,config=None):
    """Independent arithmetic oracle; sampler sequence is an explicit input."""
    c=config or AttentionConfig()
    c.validate()
    q,keys,values,candidates=validate_fixture(fixture,c)
    logits=[fp32(math.fsum(a*b for a,b in zip(q,keys[i]))/math.sqrt(len(q))) for i in candidates]
    probs=softmax(logits)
    if local_indices is None:
        weights=dict(enumerate(probs))
    else:
        if not local_indices or any(type(i) is not int or not 0<=i<len(candidates) for i in local_indices):
            raise ValueError('valid nonempty sampled trajectory required')
        weights={i:n/len(local_indices) for i,n in Counter(local_indices).items()}
    output=[fp32(math.fsum(weights[i]*values[candidates[i]][j] for i in weights)) for j in range(len(values[0]))]
    return dict(logits=logits,probabilities=probs,output=output)
