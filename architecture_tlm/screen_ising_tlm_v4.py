"""QK screening -> compact exact QK -> Ising black box -> sparse V addition.

New opt-in adapter, leaving v3 results and serial Ising implementation intact.
"""
import copy
import hashlib
import math
from collections import Counter,OrderedDict
from pathlib import Path
from attention_tlm_v3 import AttentionLocalDecode,AttentionDigitalDecode
from ising_macro_v4 import IsingMacro


def budget_blocks(scores,chosen,budget):
    """Mandatory first/last2, then selected-by-score, then fill-by-score.

    This is a NEW probability-screen + deterministic quota-repair policy.
    It is not the old independent Bernoulli distribution or pure top-k.
    """
    n=len(scores);forced={0,n-1,max(0,n-2)};target=min(n,budget)
    if target<len(forced):raise ValueError('budget cannot hold mandatory blocks')
    chosen=set(chosen)
    ranked=sorted(range(n),key=lambda i:(i in forced,i in chosen,scores[i],-i),reverse=True)
    return sorted(ranked[:target])


class ScreenIsingMixin:
    def __init__(self,cfg,variant,evidence,shape):
        actual=copy.deepcopy(cfg);v=actual['screen_ising_v4']
        if v['selection'] not in ('fixed_budget','variable'):raise ValueError('selection mode')
        if type(v['budget_blocks'])!=int or v['budget_blocks']<1:raise ValueError('budget_blocks')
        if v['selection']=='fixed_budget' and v['candidate_capacity']<v['budget_blocks']*64:
            raise ValueError('fixed block budget exceeds macro capacity')
        # Reuse max4 screening/RNG and metadata utilities; sampled_rows is replaced.
        actual['attention_v3'].update(mode='screen_pv',samples=v['samples'])
        super().__init__(actual,variant,evidence,shape)
        self.v4=copy.deepcopy(v);self.macro=self.make_sampler(v)

    def make_sampler(self,v):
        return IsingMacro(v['ising'],v['candidate_capacity'])

    def prepare_sampler_input(self,t,n,cap):
        # Historical v4 behavior. Explicit samplers may implement these stages
        # internally; the hook prevents charging max/encode/programming twice.
        t=self.op(t,'ising_bias_encode',vec=4*n)
        config_size=math.ceil(cap*(self.v4['ising']['bias_bits']+1)/8)
        return self.scratch(t,write=config_size,read=config_size,kind='ising_configuration')

    def sampler_work_bytes(self,cap,samples):
        return cap*8+math.ceil(cap*(self.v4['ising']['bias_bits']+1)/8)+samples*4

    def score_and_route(self,t,L,layer,token):
        t,rows,summary_bytes=super().score_and_route(t,L,layer,token)
        if self.v4['selection']=='fixed_budget':
            b=math.ceil(L/64);padded=1<<(b-1).bit_length();levels=int(math.log2(padded))
            for row in rows:
                old=row['router']['selected_blocks']
                selected=budget_blocks(row['router']['block_scores'],old,self.v4['budget_blocks'])
                # SRAM-backed bitonic sorting schedule: fixed compare-exchange
                # stages, 12-byte score/index/flags records incl invalid padding.
                t=self.scratch(t,write=padded*12,kind='budget_records')
                for _ in range(levels*(levels+1)//2):
                    t=self.scratch(t,read=padded*12,write=padded*12,kind='budget_sort_stage')
                    t=self.sampler(t,padded//2,'budget_compare_exchange')
                t=self.scratch(t,read=min(b,self.v4['budget_blocks'])*12,kind='budget_result')
                row['router'].update(raw_selected_blocks=old,selected_blocks=selected,
                    budget_added=len(set(selected)-set(old)),budget_removed=len(set(old)-set(selected)))
                row['indices']=[i for block in selected for i in range(block*64,min((block+1)*64,L))]
                logits=self.source.logits(token,layer,row['head'],L)
                row['logits']=[logits[i] for i in row['indices']]
        for row in rows:
            if len(row['indices'])>self.macro.capacity:
                raise ValueError('variable selection exceeds Ising capacity; increase capacity or select fixed_budget')
        selected=sum(len(r['indices']) for r in rows)
        t=self.op(t,'candidate_compaction',vec=self.qheads*math.ceil(L/64)+selected)
        # Persist compact-local -> original-token mappings for later V gathers.
        t=self.scratch(t,write=selected*4,kind='candidate_map')
        self.actions['ATT_candidate_map_entries']+=selected
        return t,rows,summary_bytes

    def compact_gather(self,t,layer,head,local_ids,candidates,cache):
        counts=Counter(local_ids);n=len(candidates)
        self.actions['ATT_V_additions']+=len(local_ids)*self.dim
        self.actions['ATT_V_sample_events']+=len(local_ids)
        self.actions['ATT_V_unique_head_indices']+=len(counts)
        t=self.scratch(t,write=n*4,kind='compact_histogram_clear')
        t=self.op(t,'histogram',vec=len(local_ids))
        t=self.scratch(t,read=len(local_ids)*8,write=len(local_ids)*4,kind='compact_histogram')
        # Scan the counters once; count>0 entries form the sparse V work list.
        t=self.scratch(t,read=n*4,kind='compact_histogram_scan')
        t=self.op(t,'histogram_nonzero',vec=n)
        t=self.scratch(t,read=len(counts)*4,kind='local_to_global_map')
        t=self.op(t,'index_remap',vec=len(counts))
        slots=self.ac['v_cache_bytes']//self.vecbytes;kvhead=head//self.group
        for local,count in sorted(counts.items()):
            index=candidates[local];key=(kvhead,index)
            if key not in cache:
                t=self.ranges(t,[(self.kv_address(layer,index,kvhead,True),self.vecbytes)],'V_gather')
                t=self.scratch(t,write=self.vecbytes,kind='V_cache_fill');self.actions['ATT_V_cache_misses']+=1
                if slots:
                    cache[key]=True;cache.move_to_end(key)
                    if len(cache)>slots:cache.popitem(last=False)
            else:cache.move_to_end(key);self.actions['ATT_V_cache_hits']+=1
            t=self.scratch(t,read=self.vecbytes,kind='V_operand')
            t=self.op(t,'V_accumulate',vec=count*self.dim)
        return self.op(t,'sample_mean',vec=self.dim,nl=1)

    def attention(self,ready,L,layer):
        token=self.attn_calls[layer];self.attn_calls[layer]+=1
        self.coord=dict(token=token,layer=layer);self.attention_length=L
        t,rows,summary_bytes=self.score_and_route(ready,L,layer,token)
        count=sum(len(r['indices']) for r in rows);cap=self.macro.capacity;N=self.v4['samples']
        self.actions['ATT_selected_QK_tokens']+=count;self.actions['ATT_possible_QK_tokens']+=self.qheads*L
        # Scores + index maps for all heads, one histogram/bias staging buffer,
        # full response index buffer and finite V cache. No LxL attention map.
        b=math.ceil(L/64);sort_records=(1<<(b-1).bit_length())*24 if self.v4['selection']=='fixed_budget' else 0
        peak=(summary_bytes+self.qheads*b*5+sort_records+count*8+
            self.sampler_work_bytes(cap,N)+
            self.qheads*self.dim*4+self.ac['kv_tile_tokens']*self.kheads*self.vecbytes*2+self.ac['v_cache_bytes'])
        self.attn_work_peak=max(self.attn_work_peak,peak)
        if peak>self.cfg['scratchpad']['capacity_MiB']*1024**2:raise ValueError('v4 scratch capacity exceeded')
        t=self.qk_tiles(t,L,layer,rows,fused_pv=False)
        cache=OrderedDict()
        for row in rows:
            h=row['head'];n=len(row['logits'])
            t=self.scratch(t,read=n*4,kind='compact_logits')
            # Max/subtract/scale/encode only. No external sigmoid or Softmax.
            t=self.prepare_sampler_input(t,n,cap)
            ids,service=self.macro.request(t,row['logits'],N,
                self.source.random(token,layer,h,'ising_macro_oracle'),(token,layer,h),row['indices'],
                output_ns_per_index=4/self.cfg['scratchpad']['bandwidth_GBs'])
            t=self.record('Ising_macro',service['start_ns'],service['end_ns'],resource='ising_macro',
                **{k:v for k,v in service.items() if k not in ('start_ns','end_ns')})
            self.actions['ATT_Ising_macro_requests']+=1
            self.actions['ATT_Ising_output_indices']+=N
            self.actions['ATT_Ising_config_bits']+=service['config_bits']
            self.energy['ATT_Ising_macro_active_config']+=service['energy_J']
            # Results stream directly into reserved host scratch while sampling.
            # No unpriced N-entry result buffer hidden inside the Ising macro.
            self.attn_port.free=t
            self.traffic['attention_scratch_write_bytes']+=N*4
            self.energy['ATT_scratch']+=N*4*self.cfg['scratchpad']['write_pJ_per_byte']*1e-12
            self.record('Ising_output_stream',service['first_sample_ns'],t,resource='scratch_port',
                write_bytes=N*4,read_bytes=0,retained_internal_output_indices=1)
            t=self.compact_gather(t,layer,h,ids,row['indices'],cache)
            self.attn_rows.append(dict(**self.coord,head=h,selected_tokens=n,capacity=cap,
                masked_slots=cap-n,samples=N,unique_V=len(set(ids)),
                budget_added=row['router'].get('budget_added',0),budget_removed=row['router'].get('budget_removed',0),
                candidate_map=row['indices'],sample_source=self.macro.provenance['kind']))
        t=self.scratch(t,write=self.qheads*self.dim*2,kind='attention_output')
        self.attn_elapsed+=t-ready
        return t

    def run(self):
        d=super().run();end=sum(d['time_ns'].values());m=self.macro.finish(end);tokens=self.cfg['decode_tokens']
        self.energy['ATT_Ising_macro_idle']=m['idle_J']
        d['energy_J']=dict(self.energy)
        d['metrics']['scenario_mJ_per_token']=sum(self.energy.values())/tokens*1000
        d['metrics']['parameterized_area_mm2']+=m['area_mm2']
        d['metrics']['area_budget_feasible']=d['metrics']['parameterized_area_mm2']<=self.cfg['area_budget_mm2']
        d['metrics']['attention_direct_mJ_per_token']+=m['idle_J']/tokens*1000
        d['metrics']['ising_active_ms_per_token']=m['active_ns']/tokens/1e6
        d['metrics']['ising_mJ_per_token']=(m['active_and_config_J']+m['idle_J'])/tokens*1000
        a=d.pop('attention_v3')
        a.update(config=self.v4,ising=m,
            mapping='max4 Bernoulli screen + optional fixed quota repair -> compact QK -> abstract Ising sample indices -> V gather/add',
            limitations=['Ising internal circuit omitted by design; all service/PPA parameters are uncharacterized',
                'default ideal IID oracle creates addresses only; no mixing, correlation, bias quantization or PPL validation',
                'fixed quota repair changes old selector semantics and requires new numerical quality evaluation',
                'blocking single macro reused over heads/layers; no implied parallel array speedup',
                'other digital/FFN/DRAM assumptions inherited from v3'])
        d['attention_v4']=a;d['implementation']='screen_ising_v4 macro-contract TLM with full-model integration'
        for event in d['events']:
            if event['name']=='Attention_screen_pv':event['name']='Attention_screen_Ising_V'
        for name in ('screen_ising_tlm_v4.py','ising_macro_v4.py'):
            d['source_hashes'][name]=hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
        return d


class ScreenIsingLocal(ScreenIsingMixin,AttentionLocalDecode):pass
class ScreenIsingDigital(ScreenIsingMixin,AttentionDigitalDecode):pass
