"""Banked SRAM + bounded ping-pong schedules on the existing full decode model.

Local PRNG generation, checkpointing and root seeding remain in local_shared_v2;
no random words are spilled to SRAM. No changes to stored weights or samples.
"""
import copy
import hashlib
import math
from pathlib import Path
from collections import defaultdict
from banked_sram_v5 import BankedSram
from memory_local_sampler_v5 import LocalSamplerMixin
from attention_tlm_v3 import AttentionLocalDecode, AttentionDigitalDecode

MIB=2**20


class StagedWeights:
    def __init__(self,owner):
        self.owner=owner;self.ext=owner.ext;self.mem=owner.weight_mem
        p=owner.plan;self.chunk=p['chunk_bytes'];self.slot_free=[0.,0.]
        self.base=128*1024 if p.get('unified_bytes') else 0
        self.pin_budget=max(0,self.mem.capacity-self.base-2*self.chunk) if p['pin'] else 0
        if 2*self.chunk>self.mem.capacity-self.base:raise ValueError('two staging slots do not fit')
        self.line=4096;self.cache={};self.hits=self.misses=self.peak=0
        self.serial=0;self.last_slot=None

    def request(self,tensor,offset,size,ready):
        if size>self.chunk:raise ValueError('request larger than staging slot')
        owner=self.owner;slot=self.serial%2;self.serial+=1
        ready=max(ready,self.slot_free[slot]);self.last_slot=slot
        pinned=(tensor=='lm_head' and offset+size<=self.pin_budget)
        keys=list(range(offset//self.line,(offset+size-1)//self.line+1))
        cache_key=(offset,size)
        resident=pinned and cache_key in self.cache
        if resident:
            ready=max(ready,self.cache[cache_key]);self.hits+=len(keys)
            local=self.base+2*self.chunk+offset
        else:
            self.misses+=len(keys)
            address=self.ext.layout.address(tensor,offset,size)
            ready=self.ext.access(ready,size,'weights',False,address=address)
            local=self.base+2*self.chunk+offset if pinned else self.base+slot*self.chunk
            ready=self.mem.transfer(ready,local,size,True,'weight_DMA')
            if pinned:
                self.cache[cache_key]=ready
        done=self.mem.transfer(ready,local,size,False,'weight_consume')
        occupied=self.base+2*self.chunk+max((o+n for o,n in self.cache),default=0)
        self.peak=max(self.peak,occupied)
        if self.peak>self.mem.capacity:raise ValueError('pin/staging overflow')
        return done

    def release(self,done):self.slot_free[self.last_slot]=max(self.slot_free[self.last_slot],done)

    def tile_ready(self,tensor,offset,size,ready,tiles=1):
        done=self.request(tensor,offset,size,ready)
        self.owner.energy['weight_resident_prepare']+=tiles*self.owner.cfg['weight_macro']['resident_read_pJ_per_tile']*1e-12
        return done


class BankedMixin:
    def __init__(self,cfg,variant,evidence,shape,calibration,plan):
        self.plan=copy.deepcopy(plan)
        # Parent capacity assertions include full logits. v5 optionally streams
        # greedy argmax, so bypass only that obsolete full-vocabulary allocation.
        actual=copy.deepcopy(cfg)
        actual['scratchpad']['capacity_MiB']=max(1.,plan['scratch_bytes']/MIB)
        actual['weight_macro']['cache_MiB']=plan['weight_bytes']/MIB
        super().__init__(actual,variant,evidence,shape)
        self.weight_mem=BankedSram(calibration,4096,128,plan['corner'],plan['weight_bytes'],
            plan['weight_lanes'],80e6,plan['fabric_GBs'],plan['stripe_bytes'])
        self.work_mem=BankedSram(calibration,plan['scratch_depth'],128,plan['corner'],plan['scratch_bytes'],
            plan['scratch_lanes'],80e6 if plan['scratch_depth']==4096 else 100e6,
            plan['fabric_GBs'],plan['stripe_bytes'])
        if plan.get('unified_bytes'):
            if plan['pin']:raise ValueError('unified phase reuse requires pin disabled')
            self.weight_mem=BankedSram(calibration,4096,128,plan['corner'],plan['unified_bytes'],
                plan['weight_lanes'],80e6,plan['fabric_GBs'],plan['stripe_bytes'])
            self.work_mem=self.weight_mem
        self.cfg['scratchpad']['capacity_MiB']=self.work_mem.capacity/MIB
        self.cfg['weight_macro']['cache_MiB']=self.weight_mem.capacity/MIB
        self.weights=StagedWeights(self)
        if not plan['stream_logits'] and shape['vocab_size']*4+shape['hidden_size']*2>self.work_mem.capacity:
            raise ValueError('full logits do not fit; enable streaming greedy argmax')
        self.local_timing=defaultdict(float);self.stream_argmax_done=False
        self.attn_peak=0;self.other_peak=0;self.arena={}

    def scratch(self,t,read=0,write=0,kind='buffer'):
        # Compatibility guard: no uniform arrays. LocalSamplerMixin implements
        # the bounded on-demand consumer and actual CDF probe protocol.
        if kind in ('uniform_buffer','router_uniform_buffer'):
            self.traffic['omitted_uniform_SRAM_bytes']+=read+write
            return t
        start=t
        region={'KV_tile':'KV','summary_input':'KV','summary':'summary',
                'router_probabilities':'router','logits':'logits',
                'probabilities':'row','cdf':'row','cdf_search':'row',
                'histogram_clear':'row','histogram':'row',
                'sample_indices':'indices','V_cache_fill':'V','V_operand':'V',
                'attention_output':'state'}.get(kind,'state')
        address,capacity=self.arena.get(region,(0,self.work_mem.capacity))
        if kind=='logits' and read:
            address+=getattr(self,'active_head',0)*self.attention_length*4
            capacity=self.attention_length*4
        for amount,write_flag in ((write,True),(read,False)):
            left=amount
            while left:
                n=min(left,capacity)
                t=self.work_mem.transfer(t,address,n,write_flag,kind);left-=n
        self.attn_port.free=t
        self.traffic['attention_scratch_read_bytes']+=read
        self.traffic['attention_scratch_write_bytes']+=write
        return self.record('banked_scratch_'+kind,start,t,read_bytes=read,write_bytes=write,resource='scratch_port')

    def score_and_route(self,t,L,layer,token):
        if self.ac['mode']=='dense':
            # Dense timing/accesses depend only on shape, not synthetic values.
            return t,[dict(head=h,indices=range(L),logits=(),router={}) for h in range(self.qheads)],0
        return super().score_and_route(t,L,layer,token)

    def qk_tiles(self,t,L,layer,rows,fused_pv=False):
        tile=self.ac['kv_tile_tokens'];blocks=math.ceil(L/tile)
        if self.ac['mode']=='dense':
            active=[self.qheads*min(tile,L-i*tile) for i in range(blocks)]
            live=[self.qheads]*blocks;grouped=None
        else:
            active=[0]*blocks;live=[0]*blocks;grouped=[[set() for _ in range(self.kheads)] for _ in range(blocks)]
            head_counts=[[0]*self.qheads for _ in range(blocks)]
            for row in rows:
                seen=set();group=row['head']//self.group
                for index in row['indices']:
                    b=index//tile;active[b]+=1;seen.add(b);grouped[b][group].add(index)
                    head_counts[b][row['head']]+=1
                for b in seen:live[b]+=1
        head_cursors=[0]*self.qheads
        for b,amount in enumerate(active):
            if not amount:continue
            offset=b*tile;n=min(tile,L-offset)
            if grouped is None:
                address=self.ext.layout.address(f'L{layer}/KV',offset*self.ext.layout.kv_token_bytes,n*self.ext.layout.kv_token_bytes)
                ranges=[(address,n*self.ext.layout.kv_token_bytes)]
            else:
                ranges=[]
                for k,indices in enumerate(grouped[b]):
                    for index in sorted(indices):
                        ranges.append((self.kv_address(layer,index,k),self.vecbytes))
                        if fused_pv:ranges.append((self.kv_address(layer,index,k,True),self.vecbytes))
            t=self.ranges(t,ranges,'KV_fused' if fused_pv else 'K')
            size=sum(n for _,n in ranges)
            t=self.scratch(t,write=size,kind='KV_tile');t=self.scratch(t,read=size,kind='KV_tile')
            t=self.op(t,'QK',mac=amount*self.dim,vec=amount)
            if fused_pv:
                t=self.op(t,'online_softmax',vec=4*amount+live[b]*(2*self.dim+3),nl=amount+live[b])
                t=self.op(t,'PV',mac=amount*self.dim)
            else:
                for head,count in enumerate(head_counts[b]):
                    if count:
                        address=self.arena['logits'][0]+head*L*4+head_cursors[head]*4
                        t=self.work_mem.transfer(t,address,count*4,True,'QK_head_logits')
                        self.traffic['attention_scratch_write_bytes']+=count*4
                        head_cursors[head]+=count
                self.attn_port.free=t
        if fused_pv:t=self.op(t,'online_finalize',vec=self.qheads*self.dim,nl=self.qheads)
        return t

    def vectors(self,ready,ops=0,nonlinear=0):
        if self.stream_argmax_done and ops==self.shape['vocab_size'] and nonlinear==0:
            self.stream_argmax_done=False;return ready
        d=self.cfg['digital'];n=ops*d['vector_interface_bytes_per_op']+nonlinear*d['nonlinear_interface_bytes_per_op']
        live=min(n,max(4096,self.shape['intermediate_size']*8))
        self.other_peak=max(self.other_peak,65536+live)
        if 65536+live>self.work_mem.capacity:raise ValueError('vector workspace overflow')
        # Interface is processed in finite chunks, not a full n-byte allocation.
        t=ready;remaining=math.ceil(n/2)
        while remaining:
            size=min(remaining,live)
            t=self.work_mem.transfer(t,65536,size,False,'vector_input');remaining-=size
        start=max(t,self.digital_free)
        cycles=math.ceil(ops/d['vector_ops_per_cycle'])+math.ceil(nonlinear/d['nonlinear_ops_per_cycle'])
        t=start+cycles*self.period;self.digital_free=t
        self.actions['vector_ops']+=ops;self.actions['nonlinear_ops']+=nonlinear
        self.energy['digital_vector']+=ops*d['vector_op_pJ']*1e-12
        self.energy['digital_nonlinear']+=nonlinear*d['nonlinear_op_pJ']*1e-12
        remaining=math.ceil(n/2)
        while remaining:
            size=min(remaining,live)
            t=self.work_mem.transfer(t,65536,size,True,'vector_output');remaining-=size
        return t

    def digital_matrix(self,name,inp,out,ready,bytes_per_weight=2):
        d=self.cfg['digital'];chunk=self.plan['chunk_bytes'];total=inp*out*bytes_per_weight
        stream=(name=='lm_head' and self.plan['stream_logits'])
        if stream:chunk=max(inp*bytes_per_weight,(chunk//(inp*bytes_per_weight))*inp*bytes_per_weight)
        current=self.work_mem.transfer(ready,0,inp*2,False,'matrix_input');fetch_at=ready
        for offset in range(0,total,chunk):
            size=min(chunk,total-offset)
            arrived=self.weights.request(name,offset,size,fetch_at)
            start=max(arrived,self.digital_free,current)
            macs=size//bytes_per_weight
            done=start+math.ceil(macs/d['macs_per_cycle'])*self.period
            self.digital_free=done;self.weights.release(done)
            self.actions['digital_MAC']+=macs
            price=d['mixed_fp_int8_mac_pJ'] if bytes_per_weight==1 else d['mac_pJ']
            self.energy['digital_MAC']+=macs*price*1e-12
            if stream:
                rows=size//(inp*bytes_per_weight)
                self.other_peak=max(self.other_peak,inp*2+rows*4+16)
                done=self.work_mem.transfer(done,0,rows*4,True,'lm_logits_tile')
                done=self.vectors(done,rows)
            current=done
            fetch_at=start if self.cfg['double_buffer'] else done
        if stream:self.stream_argmax_done=True
        else:
            n=(inp+out)*2+8192;self.other_peak=max(self.other_peak,n)
            if n>self.work_mem.capacity:raise ValueError('matrix interface overflow')
            current=self.work_mem.transfer(current,8192+inp*2,out*2,True,'matrix_output')
        return current

    def stochastic_matrix(self,name,inp,out,ready):
        if inp%64 or out%64:raise ValueError('64x64 mapping required')
        T=self.cfg['samples'];E=self.engines;current=ready;groups=out//64
        self.other_peak=max(self.other_peak,out*4+64*9//8)
        for k in range(inp//64):
            encoded=self.vectors(current,64*self.cfg['sc_cost']['input_encode_vector_ops'])
            current=self.rng_hierarchy.begin_tile(encoded,(self.tile_serial,name,k));self.tile_serial+=1
            fetch_at=current
            for j in range(0,groups,E):
                count=min(E,groups-j)
                loaded=self.weights.tile_ready(name,(k*groups+j)*4096,count*4096,fetch_at,tiles=count)
                start=self.rng_hierarchy.restore_wave(max(current,loaded))
                kernel=(T+1)*self.period
                _,rng_time=self.rng_hierarchy.input_wave(start,count,T)
                duration=max(kernel,rng_time);current=start+duration
                self.weights.release(current)
                self.raw_bits+=T*8;self.sc_compute_ns+=kernel;self.rng_service_ns+=rng_time
                self.sc_active_engine_ns+=count*kernel;self.sc_wait_engine_ns+=count*(duration-kernel)
                self.actions['sc_tile_frames']+=count;self.actions['sc_product_trials']+=count*4096*T
                self.energy['SC_logic_active']+=self.body_W*count*kernel*1e-9
                self.energy['SC_shared_input_frontend']+=self.front_W*kernel*1e-9
                self.energy['SC_wait']+=count*max(0,duration-kernel)*self.cfg['sc_cost']['wait_W_per_engine']*1e-9
                fetch_at=start if self.cfg['double_buffer'] else current
            self.rng_hierarchy.end_tile()
            current=self.vectors(current,out*self.cfg['sc_cost']['finalize_vector_ops_per_partial'])
            current=self.work_mem.transfer(current,0,out*4,False,'partial_read')
            current=self.work_mem.transfer(current,0,out*4,True,'partial_write')
            self.traffic['scratch_partial_bytes']+=2*out*4
        return current

    def attention(self,ready,L,layer):
        # Parent v3 includes a temporary uniform array. Only that allocation is
        # omitted; logits/CDF/indices/V cache are retained and capacity checked.
        a=self.ac;screen=a['mode'].startswith('screen');fused=a['mode'] in ('dense','screen_exact')
        if self.plan.get('unified_bytes') and max(self.weights.slot_free)>ready+1e-5:
            raise ValueError('cannot reclaim SRAM while a weight slot is in use')
        summary=self.kheads*math.ceil(L/64)*4*self.dim*4 if screen else 0
        state=self.qheads*self.dim*4+a['kv_tile_tokens']*self.kheads*self.vecbytes*2
        state+=summary+self.qheads*math.ceil(L/64)*5
        if not fused:state+=self.qheads*L*4+L*8+a['samples']*4+a['v_cache_bytes']+math.ceil(L/8)
        sizes=[('state',self.qheads*self.dim*4+8192),
               ('KV',a['kv_tile_tokens']*self.kheads*self.vecbytes*2),
               ('summary',summary),('router',self.qheads*math.ceil(L/64)*5)]
        if not fused:sizes += [('logits',self.qheads*L*4),('row',L*8),
            ('indices',a['samples']*4),('V',a['v_cache_bytes']),('mask',math.ceil(L/8))]
        arena={};cursor=0
        for name,size in sizes:
            if size:
                cursor=math.ceil(cursor/64)*64;arena[name]=(cursor,size);cursor+=size
        state=max(state,cursor);self.attn_peak=max(self.attn_peak,state)
        if state>self.work_mem.capacity:raise ValueError('Attention buffers exceed SRAM')
        # Numeric uniform buffering was never in the old peak formula. Runtime
        # uniform SRAM actions are omitted by scratch() above; all other state stays.
        self.arena=arena
        try:return super().attention(ready,L,layer)
        finally:self.arena={}

    def run(self):
        d=super().run();end=sum(d['time_ns'].values());n=self.cfg['decode_tokens']
        old_mem_area=(self.cfg['weight_macro']['cache_MiB']*self.cfg['weight_macro']['area_mm2_per_MiB']+
                      self.cfg['scratchpad']['capacity_MiB']*self.cfg['scratchpad']['area_mm2_per_MiB'])
        for key in ('weight_sram_access','weight_sram_leakage','scratch_access','scratch_leakage','ATT_scratch'):
            self.energy.pop(key,None)
        memory_objects=(('shared',self.work_mem),) if self.plan.get('unified_bytes') else (('weights',self.weight_mem),('work',self.work_mem))
        reports={name:m.report(end) for name,m in memory_objects}
        for name,r in reports.items():
            self.energy['SRAM_'+name+'_dynamic']=r['dynamic_J']
            self.energy['SRAM_'+name+'_leakage']=r['leakage_J']
        d['energy_J']=dict(self.energy)
        d['metrics']['scenario_mJ_per_token']=sum(self.energy.values())/n*1000
        # The inherited v3 direct metric has no attribution for the new shared
        # SRAM. Keep its value under an explicit name, never call it full energy.
        d['metrics']['attention_legacy_direct_excluding_banked_SRAM_mJ_per_token']=d['metrics'].pop('attention_direct_mJ_per_token')
        d['metrics']['attention_direct_excludes']+='; v5 banked SRAM dynamic and leakage are in the whole-system ledger only'
        d['metrics']['parameterized_area_mm2']+=sum(r['area_mm2'] for r in reports.values())-old_mem_area
        d['metrics']['area_budget_feasible']=d['metrics']['parameterized_area_mm2']<=self.cfg['area_budget_mm2']
        d['memory_v5']=dict(plan=self.plan,SRAM=reports,work_peak_bytes=max(self.attn_peak,self.other_peak),
            placement=('shared SRAM: 128KiB activation/temp + two weight slots in projection/FFN; '
                'all banks reclaimed for Attention; no cross-layer pinned weights'
                if self.plan.get('unified_bytes') else 'independent weight staging/cache and activation/Scratch banks'),
            rng_storage='local live/checkpoint/seed state only; no random stream SRAM',
            opaque_SC_resident='existing resident-weight interface retained; not a proof SRAM exposes all weights in parallel',
            SRAM_area_excludes='mux/CDC/skid/control/CTS/interconnect',
            limitations=['blocking descriptors/one lane owner; no intra-request bank reordering',
                'bulk transfers use conservative service bounds; CDF probes use actual reference indices per four-word group',
                'calibrated SRAM only; digital/core/RNG coefficients remain provisional',
                'synthetic Attention trajectory, not real Qwen trace or PPL',
                'four live uniform words per categorical consumer; no uniform SRAM array'])
        d['implementation']='v5 banked SRAM, bounded ping-pong, optional streaming greedy lm_head'
        d['quality_reference_ppl']=None
        d['bounds']['scratch_peak_bytes']=max(self.attn_peak,self.other_peak)
        for name in ('banked_sram_v5.py','memory_schedule_v5.py','memory_local_sampler_v5.py'):
            d['source_hashes'][name]=hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
        # Keep summaries small; full transaction traces are optional old-v3 files.
        d['attention_v3'].pop('events',None)
        return d


class BankedLocalDecode(BankedMixin,LocalSamplerMixin,AttentionLocalDecode):pass
class BankedDigitalDecode(BankedMixin,LocalSamplerMixin,AttentionDigitalDecode):pass
