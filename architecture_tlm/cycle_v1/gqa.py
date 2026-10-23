"""A finite, shared-KV head group in one Kernel, with a post-sampling barrier.

One preprojected KV head serves multiple preprojected/RoPE-adjusted query heads.
This is a conditional timing/dataflow contract, not full-decoder or RTL proof.
"""
from dataclasses import dataclass, replace
import math
import struct

from . import attention
from .contracts import Buffer, Clock, Operation, Resource, positive_int, nonnegative_int
from .kernel import Kernel
from .memory import MemoryPort, MemoryRequest


@dataclass(frozen=True)
class GQAConfig:
    k_slots: int = 2
    v_slots: int = 2
    cache_bytes_per_cycle: int = 64
    query_state_capacity_bytes: int = 1048576
    base_address: int = 0x80000000
    operand_slots: int = 2
    metadata_capacity_bytes: int = 65536
    union_scan_lanes: int = 16

    def validate(self):
        for name in ('k_slots','v_slots','cache_bytes_per_cycle','query_state_capacity_bytes',
                     'operand_slots','metadata_capacity_bytes','union_scan_lanes'):
            positive_int(getattr(self,name),name)
        nonnegative_int(self.base_address,'base_address')


def _prepare(fixture,attention_configs,group_config):
    gc=group_config or GQAConfig()
    gc.validate()
    queries=fixture['queries']
    if not isinstance(queries,list) or not queries:
        raise ValueError('a nonempty query-head list and one shared K/V head are required')
    if attention_configs is None: attention_configs=attention.AttentionConfig()
    if isinstance(attention_configs,attention.AttentionConfig):
        # Separate deterministic state is not a claim of independent entropy.
        configs=[replace(attention_configs,seed=attention_configs.seed+i) for i in range(len(queries))]
    else:
        configs=list(attention_configs)
        if len(configs)!=len(queries): raise ValueError('one config per query required')
    data=[]
    for query,c in zip(queries,configs):
        c.validate()
        item=dict(query,k=fixture['k'],v=fixture['v'],provenance=fixture.get('provenance',{}))
        q,k,v,ids=attention.validate_fixture(item,c)
        data.append((item,q,k,v,ids))
    physical=('source_latency','source_ii','exp_latency','cdc_cycles','mac_lanes',
              'vector_lanes','exp_lanes','reciprocal_latency','drive_latency','lut_latency')
    if any(any(getattr(c,n)!=getattr(configs[0],n) for n in physical) for c in configs):
        raise ValueError('query configs must agree on shared physical resource and CDC settings')
    if sum(c.score_capacity_bytes for c in configs)>gc.query_state_capacity_bytes:
        raise ValueError('sum of per-query score/state capacity exceeds the group budget')
    if sum(metadata_bytes(data).values())>gc.metadata_capacity_bytes:
        raise ValueError('group union/consumer metadata exceeds finite capacity')
    return gc,configs,data


def metadata_bytes(data):
    """Two bounded directories: ID, refcount, head mask, compaction scratch.

    Candidate maps, scores and histograms already belong to each query budget.
    The V directory is bounded by the statically known K candidate union.
    """
    union=len(set(i for item in data for i in item[4]))
    entry=12+math.ceil(len(data)/8)
    return dict(K_directory=union*entry,V_directory=union*entry,head_ready_and_cursors=len(data)*16)


def _layout(data,gc):
    _,_,keys,values,_=data[0]
    cursor=(gc.base_address+63)//64*64
    regions=[]
    def allocate(name,port,size):
        nonlocal cursor
        start=cursor
        cursor=(cursor+size+63)//64*64
        regions.append(dict(name=name,port=port,address=start,size_bytes=size))
        return start
    kbase=allocate('K','dram',len(keys)*len(keys[0])*4)
    vbase=allocate('V','dram',len(values)*len(values[0])*4)
    layouts=[]
    for h,(_,q,_,_,ids) in enumerate(data):
        layouts.append(dict(k=kbase,v=vbase,q=allocate(f'q{h}.Q','sram',len(q)*4),
            histogram=allocate(f'q{h}.histogram','sram',len(ids)*4),
            output=allocate(f'q{h}.output','sram',len(values[0])*4)))
    return layouts,regions


def address_layout(fixture,attention_configs=None,group_config=None):
    """Public exact layout for bank/latency adversarial tests and integration."""
    gc,_,data=_prepare(fixture,attention_configs,group_config)
    return _layout(data,gc)


def default_buffers(fixture,attention_configs=None,group_config=None,prefix='gqa'):
    gc,configs,data=_prepare(fixture,attention_configs,group_config)
    d,dv=len(data[0][1]),len(data[0][3][0])
    buffers=[Buffer(prefix+'.K.free',gc.k_slots*d*4,gc.k_slots*d*4,'byte credit'),
             Buffer(prefix+'.V.free',gc.v_slots*dv*4,gc.v_slots*dv*4,'byte credit'),
             Buffer(prefix+'.operand.free',gc.operand_slots*max(d,dv)*4,gc.operand_slots*max(d,dv)*4,'byte credit'),
             Buffer(prefix+'.metadata.free',gc.metadata_capacity_bytes,gc.metadata_capacity_bytes,'byte credit')]
    for h,c in enumerate(configs):
        p=f'{prefix}.q{h}'
        buffers.extend(b for b in attention.default_buffers(c,p) if b.name!=p+'.kv')
    return buffers


def default_resources(config=None,prefix='gqa'):
    return attention.default_resources(config)+[Resource(prefix+'.cache',Clock('core',10000),1,capacity=2,
        provenance='one shared cache row read port, explicitly batched bytes; not SRAM macro calibration'),
        Resource(prefix+'.union',Clock('core',10000),1,capacity=1,
                 provenance='bounded metadata scanner; configured entries per cycle, not combinational free union')]


def make_gqa(fixture,attention_configs=None,group_config=None,*,prefix='gqa',
             memory_latency=4,memory_window=4,memory_banks=4,memory_latency_by_address=None):
    gc,configs,_=_prepare(fixture,attention_configs,group_config)
    kernel=Kernel(default_resources(configs[0],prefix),default_buffers(fixture,configs,gc,prefix),[
        MemoryPort('dram',Clock('dram',12500),latency_cycles=memory_latency,window=memory_window,
                   banks=memory_banks,strict_reads=True,latency_by_address=memory_latency_by_address),
        MemoryPort('sram',Clock('sram',12500),latency_cycles=2,window=memory_window,
                   banks=memory_banks,strict_reads=True)])
    return kernel,build_gqa(kernel,fixture,configs,gc,prefix=prefix)


def build_gqa(kernel,fixture,attention_configs=None,group_config=None,*,prefix='gqa'):
    """Add the entire initial group to a caller-owned Kernel with group resources.

    Dynamic KV append and overlapping address owners are explicitly unsupported.
    DRAM reads fill finite response-cache rows; an explicit cache port serves
    each QK/V consumer. Cache data are the actual returned memory bytes.
    """
    gc,configs,data=_prepare(fixture,attention_configs,group_config)
    layouts,regions=_layout(data,gc)
    for region in regions:
        lo,hi=region['address'],region['address']+region['size_bytes']
        if any(lo<=address<hi for address in kernel._memory[region['port']].data):
            raise ValueError('GQA address region overlaps existing initialized memory: '+region['name'])
        if any(op.resource==region['port'] and op.memory is not None and
               lo<op.memory.address+op.memory.size_bytes and op.memory.address<hi
               for op in kernel.operations.values()):
            raise ValueError('GQA address region overlaps an existing memory operation: '+region['name'])
    _,_,keys,values,_=data[0]
    d,dv=len(keys[0]),len(values[0])
    operand_bytes=max(d,dv)*4
    meta=metadata_bytes(data)
    pack=lambda row:struct.pack('<'+'f'*len(row),*row)
    unpack=lambda blob:list(struct.unpack('<'+'f'*(len(blob)//4),blob))
    for token,row in enumerate(keys): kernel.load_memory('dram',layouts[0]['k']+token*d*4,pack(row))
    for token,row in enumerate(values): kernel.load_memory('dram',layouts[0]['v']+token*dv*4,pack(row))
    state=dict(queries=[],K_union=sorted(set(i for item in data for i in item[4])),V_union=None,
        K_addresses=[],V_addresses=[],K_read_ids={},V_read_ids={},K_consumers={},V_consumers={},
        K_release_ids={},V_release_ids={},physical_weight_maps={},address_regions=regions,
        K_capacity_bytes=gc.k_slots*d*4,V_capacity_bytes=gc.v_slots*dv*4,
        operand_capacity_bytes=gc.operand_slots*operand_bytes,metadata_bytes=meta,
        query_state_capacity_bytes=sum(c.score_capacity_bytes for c in configs),
        operation_ids=[],provenance=dict(scope='one KV head and explicit query head group; preprojected Q/K/V',
            V_schedule='all query weight/histogram writes finish, then explicit union barrier and ordered bounded prefetch',
            cache='finite K/V rows held through every MAC consumer; timed shared read port plus finite operand slots held until MAC completion',
            union='precompiled bounded K candidate directory; runtime V histogram scan and sorted-directory compaction use finite lanes and reserved metadata',
            physical_memory_reads='one DRAM read per physical token in each K or V union',
            accumulation_order='each query visits its physical V token IDs in ascending order; each product and add round to FP32',
            source='one independent native-network state/seed bus per native sampled query; shared submit/delivery resources; no IID or shared-global-source claim',
            source_instances=[dict(query=h,backend=c.random_backend,seed=c.seed,logical_source_lanes=c.source_lanes,
                                   seed_word_interval=c.seed_word_interval,seed_startup=c.seed_startup,
                                   reseed_cycles=c.reseed_cycles,
                                   native_network=(c.random_backend=='native' and c.mode!='exact')) for h,c in enumerate(configs)],
            omitted='QKV projection, RoPE, screening, Wo, dynamic KV append, full decoder, PPA/STA',
            fixture=fixture.get('provenance',{})))
    cdc=configs[0].cdc_cycles
    def add(label,resource,**kw):
        ident=prefix+'.'+label
        kw.setdefault('cdc_cycles',cdc)
        kernel.add(Operation(ident,resource,**kw))
        state['operation_ids'].append(ident)
        return ident
    group_start=add('initialize','control',inputs={prefix+'.metadata.free':sum(meta.values())},
                    actions={'gqa_metadata_reserve_bytes':sum(meta.values())})
    def cache_read(label,read,size,other_deps=()):
        batches=math.ceil(size/gc.cache_bytes_per_cycle)
        return add(label,prefix+'.cache',deps=(read,*other_deps),latency_cycles=batches,ii_cycles=batches,
                   inputs={prefix+'.operand.free':operand_bytes},
                   actions={'shared_cache_read_bytes':size},metadata={'payload_read_id':read,'bytes':size})
    for order,token in enumerate(state['K_union']):
        release=f'{prefix}.K.{token}.release'
        dependencies=(group_start,) if order<gc.k_slots else (state['K_release_ids'][state['K_union'][order-gc.k_slots]],)
        address=layouts[0]['k']+token*d*4
        read=add(f'K.{token}.read','dram',deps=dependencies,memory=MemoryRequest(address,d*4),
                 inputs={prefix+'.K.free':d*4},actions={'K_read_bytes':d*4,'shared_K_rows':1},
                 metadata={'physical_token':token,'slot_lifetime':'through all QK consumers'})
        state['K_read_ids'][token]=read
        state['K_release_ids'][token]=release
        state['K_addresses'].append(address)
        state['K_consumers'][token]=[]
    class SharedK:
        def read(self,token):
            ident=state['K_read_ids'][token]
            cache=cache_read(f'K.{token}.cache.{len(state["K_consumers"][token])}',ident,d*4)
            return ident,cache
        def consume(self,token,operation): state['K_consumers'][token].append(operation)
        def consumer_outputs(self): return {prefix+'.operand.free':operand_bytes}
    ready={}
    def values_ready(head,query_state,dependency,weights,finish):
        if head in ready: raise AssertionError('head submitted V weights twice')
        ready[head]=(dependency,dict(weights),finish)
        state['physical_weight_maps'][head]=dict(weights)
        if len(ready)!=len(data): return
        barrier=add('V.union_barrier','control',deps=tuple(ready[h][0] for h in range(len(data))),
                    actions={'gqa_ready_heads':len(data)})
        state['V_barrier_id']=barrier
        scan_entries=sum(len(item[4]) for item in data)
        scan_cycles=math.ceil(scan_entries/gc.union_scan_lanes)
        def scanned(k,op):
            active=set(token for _,weights,_ in ready.values() for token in weights)
            union=[token for token in state['K_union'] if token in active]
            compact_cycles=math.ceil(len(state['K_union'])/gc.union_scan_lanes)
            add('V.union_compact',prefix+'.union',deps=(op.id,),latency_cycles=compact_cycles,
                ii_cycles=compact_cycles,actions={'gqa_union_bitmap_tests':len(state['K_union']),
                'gqa_V_union_entries':len(union)},on_complete=lambda k2,op2:schedule_values(union,op2.id))
        add('V.union_scan',prefix+'.union',deps=(barrier,),latency_cycles=scan_cycles,
            ii_cycles=scan_cycles,actions={'gqa_histogram_scan_entries':scan_entries},on_complete=scanned)
    def schedule_values(union,barrier):
        state['V_union']=union
        state['V_union_ready_id']=barrier
        acc=[[0.0]*dv for _ in data]
        last=[barrier]*len(data)
        for order,token in enumerate(union):
            dependencies=(barrier,) if order<gc.v_slots else (state['V_release_ids'][union[order-gc.v_slots]],)
            address=layouts[0]['v']+token*dv*4
            read=add(f'V.{token}.read','dram',deps=dependencies,memory=MemoryRequest(address,dv*4),
                     inputs={prefix+'.V.free':dv*4},actions={'V_read_bytes':dv*4,'shared_V_rows':1},
                     metadata={'physical_token':token})
            state['V_read_ids'][token]=read
            state['V_addresses'].append(address)
            consumers=[]
            for h in range(len(data)):
                if token not in ready[h][1]: continue
                weight=ready[h][1][token]
                cached=cache_read(f'V.{token}.cache.q{h}',read,dv*4,(last[h],))
                def accumulate(k,op,h=h,read=read,weight=weight,token=token):
                    row=unpack(k.memory_reads[read])
                    if row!=values[token]: raise AssertionError('shared V address/payload mismatch')
                    for j,value in enumerate(row): acc[h][j]=attention.fp32(acc[h][j]+attention.fp32(weight*value))
                consumer=add(f'q{h}.V.{token}.accumulate','v_accumulate',deps=(cached,last[h]),
                    latency_cycles=3+math.ceil(dv/configs[h].mac_lanes)-1,on_complete=accumulate,
                    outputs={prefix+'.operand.free':operand_bytes},
                    actions={'V_weighted_mac':dv},metadata={'query':h,'physical_token':token,
                        'weight':weight,'multiplicity':state['queries'][h]['histogram'].get(token)})
                last[h]=consumer
                consumers.append(consumer)
            state['V_consumers'][token]=consumers
            state['V_release_ids'][token]=add(f'V.{token}.release','control',deps=tuple(consumers),
                outputs={prefix+'.V.free':dv*4},actions={'shared_V_release':1})
        for h in range(len(data)): ready[h][2](last[h],acc[h])
        def group_finished(k,op): state['complete_ps']=k.now_ps
        add('release','control',deps=tuple([f'{prefix}.q{h}.output.write' for h in range(len(data))]+
            list(state['K_release_ids'].values())+list(state['V_release_ids'].values())),
            outputs={prefix+'.metadata.free':sum(meta.values())},on_complete=group_finished,
            actions={'gqa_metadata_release_bytes':sum(meta.values())})
    shared=SharedK()
    for h,((item,_,_,_,_),c,layout) in enumerate(zip(data,configs,layouts)):
        query=attention.build_attention(kernel,item,c,f'{prefix}.q{h}',address_layout=layout,shared_k=shared,
            value_sink=lambda st,dep,weights,finish,h=h:values_ready(h,st,dep,weights,finish))
        query['provenance']['omitted']='QKV projection, RoPE, screening, Wo, full decoder; GQA sharing supplied by group owner'
        query['provenance']['V_prefetch']='group-owned union barrier and bounded ordered prefetch'
        state['queries'].append(query)
    for token in state['K_union']:
        add(f'K.{token}.release','control',deps=tuple(state['K_consumers'][token]),
            outputs={prefix+'.K.free':d*4},actions={'shared_K_release':1})
    return state
