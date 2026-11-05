"""Opt-in transaction-level Attention, retaining the existing full decode/FFN.

All paths issue addressed DRAM requests, serialized scratch-port transactions,
resource-reserved arithmetic and explicit RNG/sampler work. The default is a
conservative blocking mapping (no claimed ideal overlap). Digital macro costs
are parameters, not measured hardware. The Ising mapping is a specified serial
random-scan hard-onehot engine, NOT an assumed free parallel p-bit network.
"""
import copy
import hashlib
import math
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from system_decode import DecodeModel, Link, MIB
from system_decode_local_shared_v2 import LocalSharedDecode
from attention_reference_v3 import TraceSource, softmax, categorical, selector, ising_random_scan

MODES=('dense','pv','ising','screen_exact','screen_pv')


class AttentionMixin:
    def __init__(self,cfg,variant,evidence,shape):
        super().__init__(cfg,variant,evidence,shape)
        self.ac=copy.deepcopy(cfg['attention_v3'])
        a=self.ac
        if a['mode'] not in MODES:raise ValueError('unknown attention mode')
        if a['block_size']!=64 or a['subblocks']!=4:raise ValueError('only verified max4 router supported')
        if a['ising_mapping']!='serial_random_scan_hard_onehot':raise ValueError('unsupported Ising mapping')
        if a['uniform_bits']!=32:raise ValueError('Attention v3 leaf uses 32-bit uniform words; FFN A8 is separate')
        if a['summary_initialization'] not in ('cold_build','prefill_prebuilt'):raise ValueError('summary init')
        for k in ('samples','kv_tile_tokens','uniform_bits','rng_words_per_cycle','sampler_comparisons_per_cycle',
                  'ising_spacing_sweeps','ising_cycles_per_attempt','leaf_seed_bits'):
            if not isinstance(a[k],int) or isinstance(a[k],bool) or a[k]<1:raise ValueError(k)
        for k,v in a.items():
            if isinstance(v,(float,int)) and (not math.isfinite(v) or v<0) and k!='selector_bias':raise ValueError(k)
        if shape['num_attention_heads']%shape['num_key_value_heads']:raise ValueError('invalid GQA')
        self.source=TraceSource(a,shape)
        self.attn_port=Link(cfg['scratchpad']['bandwidth_GBs'])
        self.attn_rng_free=self.sampler_free=0.
        self.attn_seed_epoch=-1
        self.attn_events=[];self.attn_rows=[];self.attn_calls=defaultdict(int)
        self.summary_built=set();self.attn_elapsed=0.;self.attn_root=None
        self.qheads=shape['num_attention_heads'];self.kheads=shape['num_key_value_heads']
        self.dim=shape['hidden_size']//self.qheads;self.group=self.qheads//self.kheads
        self.vecbytes=self.dim*2
        self.screen=a['mode'].startswith('screen')
        self.random_attention=a['mode']!='dense'
        self.attn_work_peak=0
        # Add persistent summary address regions before the first request.
        # KV remains the existing [K_all_heads,V_all_heads] interleaved layout.
        if self.screen:
            layout=self.ext.layout;cursor=math.ceil(layout.total_bytes/4096)*4096
            b=math.ceil((cfg['context_tokens']+cfg['decode_tokens'])/64)
            size=self.kheads*b*4*self.dim*4
            for layer in range(shape['num_hidden_layers']):
                allocated=math.ceil(size/4096)*4096
                layout.regions[f'L{layer}/summary']=dict(base=cursor,logical_bytes=size,allocated_bytes=allocated)
                cursor+=allocated
            layout.total_bytes=cursor
            if hasattr(self.ext,'capacity') and cursor>self.ext.capacity:raise ValueError('summary exceeds DRAM capacity')

    def record(self,name,start,end,**fields):
        if end<start:raise AssertionError('negative transaction duration')
        if self.ac['record_transactions']:
            self.attn_events.append(dict(name=name,start_ns=start,end_ns=end,**self.coord,**fields))
        return end

    def scratch(self,t,read=0,write=0,kind='buffer'):
        if read<0 or write<0:raise ValueError('negative scratch access')
        start=max(t,self.attn_port.free)
        end=self.attn_port.transfer(t,read+write) if read+write else t
        c=self.cfg['scratchpad']
        self.energy['ATT_scratch']+=(read*c['read_pJ_per_byte']+write*c['write_pJ_per_byte'])*1e-12
        self.traffic['attention_scratch_read_bytes']+=read;self.traffic['attention_scratch_write_bytes']+=write
        return self.record('scratch_'+kind,start,end,read_bytes=read,write_bytes=write,resource='scratch_port')

    def op(self,t,name,mac=0,vec=0,nl=0):
        c=self.cfg['digital'];start=max(t,self.digital_free)
        # One reserved digital engine; phases explicitly serialized.
        cycles=(math.ceil(mac/c['macs_per_cycle'])+math.ceil(vec/c['vector_ops_per_cycle'])+
                math.ceil(nl/c['nonlinear_ops_per_cycle']))
        end=start+cycles*self.period;self.digital_free=end
        self.actions['ATT_'+name+'_MAC']+=mac;self.actions['ATT_'+name+'_vector']+=vec
        self.actions['ATT_'+name+'_nonlinear']+=nl
        self.actions['digital_MAC']+=mac;self.actions['vector_ops']+=vec;self.actions['nonlinear_ops']+=nl
        self.energy['ATT_MAC']+=mac*c['mac_pJ']*1e-12
        self.energy['ATT_vector']+=vec*c['vector_op_pJ']*1e-12
        self.energy['ATT_nonlinear']+=nl*c['nonlinear_op_pJ']*1e-12
        return self.record(name,start,end,mac=mac,vector=vec,nonlinear=nl,resource='digital')

    def ranges(self,t,ranges,kind):
        """Align actual addresses, deduplicate physical bursts within this DMA.

        Sparse V reads pay burst overfetch and per-DMA latency; no N/L multiplier.
        Different DMAs are not assumed to have a free DRAM cache.
        """
        burst=64 if self.cfg['external_memory'].get('backend')=='dramsys' else self.cfg['external_memory']['burst_bytes']
        lines=set();useful=sum(n for _,n in ranges)
        for address,size in ranges:
            lines.update(range(address//burst,(address+size-1)//burst+1))
        runs=[]
        for line in sorted(lines):
            if runs and line==runs[-1][-1]+1:runs[-1].append(line)
            else:runs.append([line])
        self.traffic['attention_'+kind+'_useful_bytes']+=useful
        self.traffic['attention_'+kind+'_physical_bytes']+=len(lines)*burst
        for run in runs:
            addr=run[0]*burst;n=len(run)*burst;start=t
            t=self.ext.access(t,n,'ATT_'+kind,False,address=addr)
            self.record('DRAM_'+kind,start,t,address=addr,bytes=n,resource='external_memory')
        return t

    def kv_address(self,layer,index,kvhead,value=False):
        offset=index*self.ext.layout.kv_token_bytes+((self.kheads if value else 0)+kvhead)*self.vecbytes
        return self.ext.layout.address(f'L{layer}/KV',offset,self.vecbytes)

    def ensure_attention_seed(self,t):
        if self.rng_hierarchy:
            root=self.rng_hierarchy
        else:
            if self.attn_root is None:
                from rng_hierarchy import HierarchicalRng
                root=HierarchicalRng(self.cfg['rng_hierarchy'],1,self.f,local_weights=False)
                root.cfg['shared']['cores']=0;root.instances=0
                self.attn_root=root
            root=self.attn_root
        t=root.ensure_seeded(t)
        if root.epoch!=self.attn_seed_epoch:
            s=root.cfg['seed'];bits=self.ac['leaf_seed_bits']
            t+=math.ceil(bits/s['expand_bits_per_cycle'])/s['expand_hz']*1e9
            t+=math.ceil(bits/s['bus_bits'])/s['bus_hz']*1e9
            self.energy['ATT_leaf_seed']+=bits*(s['expand_pJ_per_bit']+s['bus_pJ_per_bit'])*1e-12
            self.actions['ATT_leaf_rekeys']+=1;self.attn_seed_epoch=root.epoch
        return t

    def random_words(self,t,words,kind):
        if not words:return t
        words=math.ceil(words);start=t
        t=self.ensure_attention_seed(t)
        begin=max(t,self.attn_rng_free)
        end=begin+math.ceil(words/self.ac['rng_words_per_cycle'])*self.period
        self.attn_rng_free=end
        bits=words*self.ac['uniform_bits']
        self.actions['ATT_random_words']+=words;self.actions['ATT_random_bits']+=bits
        self.energy['ATT_PRNG']+=words*self.ac['rng_update_pJ_per_word']*1e-12
        self.energy['ATT_rng_distribution']+=bits*self.ac['rng_route_pJ_per_bit']*1e-12
        return self.record('RNG_'+kind,start,end,words=words,bits=bits,resource='attention_rng_leaf')

    def ising_stream(self,t,info):
        """Bounded-state online update loop, NEVER buffer all uniform words.

        Every attempt serially obtains RNG words, reads bias/state, then commits
        the single-site decision. Macro timing uses expected rejection draws,
        rounded service per attempt; not a statistical worst-case guarantee.
        RNG, scratch and control are reserved for this non-interleaved loop.
        """
        a=self.ac;n=info['attempts'];sites=info['sites']
        if not n:return t
        t=self.ensure_attention_seed(t)
        width=(sites-1).bit_length() if sites>1 else 0
        index_per_attempt=2**width/sites if width else 0
        index_words=n*index_per_attempt
        words=math.ceil(index_words+n);bits=words*a['uniform_bits']
        start=max(t,self.attn_rng_free,self.attn_port.free,self.sampler_free)
        sp=self.cfg['scratchpad']
        cycles=n*(a['ising_cycles_per_attempt']+
            math.ceil((1+index_per_attempt)/a['rng_words_per_cycle'])+
            math.ceil(8/(sp['bandwidth_GBs']*self.period)))
        write=info['flips']*4
        end=start+cycles*self.period+write/sp['bandwidth_GBs']
        self.attn_rng_free=self.attn_port.free=self.sampler_free=end
        self.actions['ATT_ising_index_words_expected']+=index_words
        self.actions['ATT_random_words']+=words;self.actions['ATT_random_bits']+=bits
        self.actions['ATT_ising_attempts']+=n;self.actions['ATT_ising_state_flips']+=info['flips']
        comparisons=2*n+math.ceil(index_words)
        self.actions['ATT_ising_update_comparisons']+=comparisons
        self.energy['ATT_PRNG']+=words*a['rng_update_pJ_per_word']*1e-12
        self.energy['ATT_rng_distribution']+=bits*a['rng_route_pJ_per_bit']*1e-12
        self.energy['ATT_sampler']+=comparisons*a['sampler_compare_pJ']*1e-12
        self.energy['ATT_ising_control']+=(n*a['ising_control_pJ_per_attempt']+
            info['flips']*a['ising_state_flip_pJ'])*1e-12
        self.energy['ATT_scratch']+=(n*8*sp['read_pJ_per_byte']+write*sp['write_pJ_per_byte'])*1e-12
        self.traffic['attention_scratch_read_bytes']+=n*8;self.traffic['attention_scratch_write_bytes']+=write
        return self.record('ising_online_update_loop',start,end,resource='ising_pipeline',
            reserved_resources=['scratch_port','attention_rng_leaf','attention_sampler'],
            attempts=n,flips=info['flips'],rng_words=words,read_bytes=n*8,write_bytes=write,
            retained_rng_words=2,index_rng_draws='expected rejection count')

    def sampler(self,t,comparisons,name,cycles=None):
        start=max(t,self.sampler_free)
        if cycles is None:cycles=math.ceil(comparisons/self.ac['sampler_comparisons_per_cycle'])
        end=start+cycles*self.period;self.sampler_free=end
        self.actions['ATT_'+name+'_comparisons']+=comparisons
        self.energy['ATT_sampler']+=comparisons*self.ac['sampler_compare_pJ']*1e-12
        return self.record(name,start,end,comparisons=comparisons,resource='attention_sampler')

    def summary(self,t,L,layer):
        b=math.ceil(L/64);size=self.kheads*b*4*self.dim*4
        name=f'L{layer}/summary'
        if layer not in self.summary_built:
            if self.ac['summary_initialization']=='cold_build':
                for start in range(0,L,self.ac['kv_tile_tokens']):
                    ids=range(start,min(L,start+self.ac['kv_tile_tokens']))
                    reads=[(self.kv_address(layer,i,k),self.vecbytes) for i in ids for k in range(self.kheads)]
                    t=self.ranges(t,reads,'summary_build_K')
                    n=len(reads)*self.dim
                    t=self.scratch(t,write=n*2,kind='summary_input');t=self.scratch(t,read=n*2,kind='summary_input')
                    t=self.op(t,'summary_build',vec=n)
                addr=self.ext.layout.address(name,0,size);start=t
                t=self.ext.access(t,size,'ATT_summary',True,address=addr)
                self.record('DRAM_summary_initial_write',start,t,address=addr,bytes=size,resource='external_memory')
            self.summary_built.add(layer)
        else:
            # Sub-summary sums are laid out [block, sub, KV head, dim].
            offset=(((L-1)//64)*4+((L-1)%64)//16)*self.kheads*self.dim*4
            n=self.kheads*self.dim*4;addr=self.ext.layout.address(name,offset,n)
            if (L-1)%16:
                t=self.ranges(t,[(addr,n)],'summary_update')
            t=self.op(t,'summary_update',vec=self.kheads*self.dim)
            start=t;t=self.ext.access(t,n,'ATT_summary',True,address=addr)
            self.record('DRAM_summary_update_write',start,t,address=addr,bytes=n,resource='external_memory')
        addr=self.ext.layout.address(name,0,size)
        t=self.ranges(t,[(addr,size)],'summary_read')
        t=self.scratch(t,write=size,kind='summary');t=self.scratch(t,read=size,kind='summary')
        # Sum-to-mean conversion shared by the Q heads in a GQA group.
        t=self.op(t,'summary_means',vec=self.kheads*math.ceil(L/16)*self.dim,nl=math.ceil(L/16))
        return t,size

    def score_and_route(self,t,L,layer,token):
        a=self.ac;rows=[];summary_bytes=0
        if self.screen:
            t,summary_bytes=self.summary(t,L,layer)
            b=math.ceil(L/64);valid_subs=math.ceil(L/16)
            t=self.op(t,'router_proxy',mac=self.qheads*valid_subs*self.dim,
                vec=self.qheads*(valid_subs+3*b+9*b),nl=self.qheads*(b+2))
            t=self.scratch(t,read=self.qheads*b*4,write=self.qheads*b*4,kind='router_probabilities')
            t=self.random_words(t,self.qheads*b,'router')
            t=self.scratch(t,write=self.qheads*b*4,read=self.qheads*b*4,kind='router_uniform_buffer')
            t=self.sampler(t,self.qheads*b,'router_keep')
        for head in range(self.qheads):
            logits=self.source.logits(token,layer,head,L)
            if self.screen:
                bias,temp=self.source.parameters(layer,head)
                indices,info=selector(logits,bias,temp,self.source.random(token,layer,head,'router'))
            else:indices=list(range(L));info={}
            rows.append(dict(head=head,indices=indices,logits=[logits[i] for i in indices],router=info))
        return t,rows,summary_bytes

    def qk_tiles(self,t,L,layer,rows,fused_pv=False):
        sets=[set(r['indices']) for r in rows]
        for offset in range(0,L,self.ac['kv_tile_tokens']):
            end=min(L,offset+self.ac['kv_tile_tokens']);ranges=[];active=0
            for k in range(self.kheads):
                union=set().union(*sets[k*self.group:(k+1)*self.group])
                for index in sorted(i for i in union if offset<=i<end):
                    ranges.append((self.kv_address(layer,index,k),self.vecbytes))
                    if fused_pv:ranges.append((self.kv_address(layer,index,k,True),self.vecbytes))
            for s in sets:active+=sum(offset<=i<end for i in s)
            if not active:continue
            t=self.ranges(t,ranges,'KV_fused' if fused_pv else 'K')
            size=sum(n for _,n in ranges)
            t=self.scratch(t,write=size,kind='KV_tile');t=self.scratch(t,read=size,kind='KV_tile')
            t=self.op(t,'QK',mac=active*self.dim,vec=active)
            if fused_pv:
                # Streaming log-sum-exp + online weighted accumulator rescaling.
                live=sum(any(offset<=i<end for i in s) for s in sets)
                t=self.op(t,'online_softmax',vec=4*active+live*(2*self.dim+3),nl=active+live)
                t=self.op(t,'PV',mac=active*self.dim)
            else:
                t=self.scratch(t,write=active*4,kind='logits')
        if fused_pv:t=self.op(t,'online_finalize',vec=self.qheads*self.dim,nl=self.qheads)
        return t

    def gather(self,t,layer,head,indices,cache):
        counts=Counter(indices);self.actions['ATT_V_additions']+=len(indices)*self.dim
        self.actions['ATT_V_unique_head_indices']+=len(counts)
        self.actions['ATT_V_sample_events']+=len(indices)
        slots=self.ac['v_cache_bytes']//self.vecbytes
        # Merge equal indices with a counter, but retain repeated-add arithmetic.
        # One reusable dense counter row, explicitly cleared for each head.
        # Read index + prior count; write incremented count. The retained table
        # is covered by the extra L*8 working-buffer reservation in attention().
        length=getattr(self,'attention_length',self.cfg['context_tokens'])
        t=self.scratch(t,write=length*4,kind='histogram_clear')
        t=self.op(t,'histogram',vec=len(indices))
        t=self.scratch(t,read=8*len(indices),write=4*len(indices),kind='histogram')
        kvhead=head//self.group
        for index,count in sorted(counts.items()):
            key=(kvhead,index)
            if key not in cache:
                t=self.ranges(t,[(self.kv_address(layer,index,kvhead,True),self.vecbytes)],'V_gather')
                t=self.scratch(t,write=self.vecbytes,kind='V_cache_fill')
                self.actions['ATT_V_cache_misses']+=1
                if slots:
                    cache[key]=True;cache.move_to_end(key)
                    if len(cache)>slots:cache.popitem(last=False)
            else:
                cache.move_to_end(key);self.actions['ATT_V_cache_hits']+=1
            t=self.scratch(t,read=self.vecbytes,kind='V_operand')
            # Repeated additions use one resident vector operand, not N DRAM reads.
            t=self.op(t,'V_accumulate',vec=count*self.dim)
        return self.op(t,'sample_mean',vec=self.dim,nl=1)

    def sampled_rows(self,t,layer,token,rows):
        a=self.ac;cache=OrderedDict()
        for row in rows:
            head=row['head'];logits=row['logits'];n=len(logits)
            t=self.scratch(t,read=n*4,kind='logits')
            rng=self.source.random(token,layer,head,a['mode']+'_samples')
            if a['mode']=='ising':
                ids,info=ising_random_scan(logits,a['samples'],a['ising_burn_sweeps'],a['ising_spacing_sweeps'],rng)
                t=self.op(t,'ising_bias',vec=max(0,2*n-2),nl=max(0,n-1))
                t=self.scratch(t,write=max(0,n-1)*4,kind='ising_bias')
                t=self.ising_stream(t,info)
                t=self.sampler(t,a['samples'],'ising_readout')
            else:
                p=softmax(logits);ids=categorical(p,a['samples'],rng);info={}
                t=self.op(t,'softmax',vec=4*n-2,nl=n+1)
                t=self.scratch(t,write=n*4,kind='probabilities')
                t=self.scratch(t,read=n*4,write=n*4,kind='cdf')
                t=self.op(t,'cdf',vec=max(0,n-1))
                t=self.random_words(t,a['samples'],'categorical')
                t=self.scratch(t,write=a['samples']*4,read=a['samples']*4,kind='uniform_buffer')
                # Fixed-depth padded binary search. No free categorical oracle.
                depth=math.ceil(math.log2(n+1)) if n>1 else 0
                comparisons=a['samples']*depth
                t=self.scratch(t,read=comparisons*4,kind='cdf_search')
                t=self.sampler(t,comparisons,'cdf_search')
            indices=[row['indices'][i] for i in ids]
            t=self.scratch(t,write=len(indices)*4,kind='sample_indices')
            t=self.gather(t,layer,head,indices,cache)
            self.attn_rows.append(dict(**self.coord,head=head,selected_tokens=n,unique_V=len(set(indices)),
                samples=len(indices),adjacent_repeat=sum(x==y for x,y in zip(indices,indices[1:]))/max(1,len(indices)-1),
                **info))
        return t

    def attention(self,ready,L,layer):
        self.attention_length=L
        token=self.attn_calls[layer];self.attn_calls[layer]+=1
        self.coord=dict(token=token,layer=layer)
        a=self.ac;start=ready
        t,rows,summary_bytes=self.score_and_route(ready,L,layer,token)
        selected=sum(len(r['indices']) for r in rows)
        self.actions['ATT_selected_QK_tokens']+=selected
        self.actions['ATT_possible_QK_tokens']+=self.qheads*L
        fused=a['mode'] in ('dense','screen_exact')
        # Peak live on-chip state; persistent summaries live in external memory.
        state=self.qheads*self.dim*4+self.ac['kv_tile_tokens']*self.kheads*self.vecbytes*2
        state+=summary_bytes+self.qheads*math.ceil(L/64)*5
        if not fused:state+=self.qheads*L*4+L*8+a['samples']*4+a['v_cache_bytes']+math.ceil(L/8)
        self.attn_work_peak=max(self.attn_work_peak,state)
        if state>self.cfg['scratchpad']['capacity_MiB']*MIB:raise ValueError('Attention live buffers exceed scratch capacity; increase capacity or implement spill')
        t=self.qk_tiles(t,L,layer,rows,fused_pv=fused)
        if fused:
            for r in rows:self.attn_rows.append(dict(**self.coord,head=r['head'],selected_tokens=len(r['indices']),samples=0))
        else:t=self.sampled_rows(t,layer,token,rows)
        t=self.scratch(t,write=self.qheads*self.dim*2,kind='attention_output')
        self.attn_elapsed+=t-start
        return t

    def run(self):
        d=super().run();tokens=self.cfg['decode_tokens']
        end=sum(d['time_ns'].values());seconds=end*1e-9
        extra_area=0.
        if self.random_attention:
            extra_area=self.ac['rng_area_mm2']+self.ac['sampler_area_mm2']
            self.energy['ATT_leaf_idle']=(self.ac['rng_idle_W']+self.ac['sampler_idle_W'])*seconds
            if self.ac['mode']=='ising':extra_area+=(self.cfg['context_tokens']+tokens-1)*self.ac['ising_state_area_mm2_per_bit']
        if self.attn_root:
            root=self.attn_root.finish(end)
            for k,v in root['energy_J'].items():self.energy['ATT_root_'+k]=v
            extra_area+=root['area_mm2'];d['attention_root_rng']=root
        d['energy_J']=dict(self.energy)
        d['metrics']['scenario_mJ_per_token']=sum(self.energy.values())/tokens*1000
        d['metrics']['parameterized_area_mm2']+=extra_area
        d['metrics']['area_budget_feasible']=d['metrics']['parameterized_area_mm2']<=self.cfg['area_budget_mm2']
        d['metrics']['attention_ms_per_token']=self.attn_elapsed/tokens/1e6
        direct=sum(v for k,v in self.energy.items() if k.startswith(('ATT_','external_ATT_')))
        d['metrics']['attention_direct_mJ_per_token']=direct/tokens*1000
        d['metrics']['attention_direct_excludes']='QK/V/O projections, shared idle, shared root and DRAMPower core when using DRAMSys; see full system energy'
        d['quality_reference_ppl']=None
        if 'quality_reference' in d:
            d['inherited_ffn_only_quality_reference']=d.pop('quality_reference')
        d['quality_warning']='NEW attention transaction mapping has NO full-model PPL claim; prior FFN/attention PPL is not a combined hardware validation'
        d['implementation']='attention_v3 explicit transactions + inherited full decode/local FFN; Python LT, optional real DRAMSys'
        if 'QK_softmax_PV' in d['time_ns']:
            d['time_ns']['Attention_core']=d['time_ns'].pop('QK_softmax_PV')
        for event in d['events']:
            if event['name']=='QK_softmax_PV':event['name']='Attention_'+self.ac['mode']
        d['attention_v3']=dict(config=self.ac,trace=self.source.provenance,rows=self.attn_rows,
            events=self.attn_events,peak_live_bytes=self.attn_work_peak,
            mapping='blocking DMA/scratch/compute; GQA union K reads, finite LRU V cache, histogram with repeated adds',
            ising='serial random-scan hard-onehot with geometric reference skipping; all attempted hardware updates charged',
            limitations=['macro costs uncharacterized; not a cycle-accurate or measured chip',
                'uniform index rejection uses expected word count; numerical random.Random is ideal-uniform reference',
                'finite uniform precision / real PRNG / BF16 rounding require independent numerical validation',
                'no prefill; prebuilt summary mode assumes prefill already paid its construction',
                'whole system outside Attention inherits v2 timing and interface approximations'])
        d['bounds']['scratch_peak_bytes']=max(d['bounds']['scratch_peak_bytes'],self.attn_work_peak)
        for file in ('attention_tlm_v3.py','attention_reference_v3.py'):
            d['source_hashes'][file]=hashlib.sha256((Path(__file__).parent/file).read_bytes()).hexdigest()
        return d


class AttentionLocalDecode(AttentionMixin,LocalSharedDecode):
    pass


class AttentionDigitalDecode(AttentionMixin,DecodeModel):
    pass
