"""Four live uniform words, on-demand CDF probes, actual word/bank collisions.

This is a bounded hardware service protocol. Python floats remain an ideal
numerical reference, not a validation of the real 32-bit leaf PRNG.
"""
import math
from collections import OrderedDict,Counter
from attention_reference_v3 import softmax,cdf,selector


class LocalSamplerMixin:
    def score_and_route(self,t,L,layer,token):
        if not self.screen:return super().score_and_route(t,L,layer,token)
        t,summary_bytes=self.summary(t,L,layer)
        b=math.ceil(L/64);subs=math.ceil(L/16)
        t=self.op(t,'router_proxy',mac=self.qheads*subs*self.dim,
            vec=self.qheads*(subs+12*b),nl=self.qheads*(b+2))
        # Keep probabilities; draw each group of uniforms only when consumed.
        t=self.scratch(t,write=self.qheads*b*4,kind='router_probabilities')
        lanes=min(4,self.ac['rng_words_per_cycle'],self.ac['sampler_comparisons_per_cycle'])
        for start in range(0,self.qheads*b,lanes):
            count=min(lanes,self.qheads*b-start)
            t=self.random_words(t,count,'router_local_stream')
            address=self.arena['router'][0]+start*4
            t=self.work_mem.transfer(t,address,count*4,False,'router_probability_stream')
            self.traffic['attention_scratch_read_bytes']+=count*4
            t=self.sampler(t,count,'router_keep')
        self.traffic['omitted_uniform_SRAM_bytes']+=2*self.qheads*b*4
        rows=[]
        for head in range(self.qheads):
            logits=self.source.logits(token,layer,head,L)
            bias,temp=self.source.parameters(layer,head)
            indices,info=selector(logits,bias,temp,self.source.random(token,layer,head,'router'))
            rows.append(dict(head=head,indices=indices,logits=[logits[i] for i in indices],router=info))
        return t,rows,summary_bytes

    def sampled_rows(self,t,layer,token,rows):
        if self.ac['mode']=='ising':return super().sampled_rows(t,layer,token,rows)
        a=self.ac;cache=OrderedDict();lanes=min(4,a['rng_words_per_cycle'],a['sampler_comparisons_per_cycle'])
        for row in rows:
            head=row['head'];logits=row['logits'];n=len(logits)
            self.active_head=head
            t=self.scratch(t,read=n*4,kind='logits')
            probabilities=softmax(logits);cumulative=cdf(probabilities)
            t=self.op(t,'softmax',vec=4*n-2,nl=n+1)
            t=self.scratch(t,write=n*4,kind='probabilities')
            t=self.scratch(t,read=n*4,write=n*4,kind='cdf')
            t=self.op(t,'cdf',vec=max(0,n-1))
            depth=math.ceil(math.log2(n+1)) if n>1 else 0
            rng=self.source.random(token,layer,head,a['mode']+'_samples')
            ids=[];base=self.arena['row'][0]
            for first in range(0,a['samples'],lanes):
                count=min(lanes,a['samples']-first)
                t=self.random_words(t,count,'categorical_local_stream')
                uniform=[rng.random() for _ in range(count)]
                lo=[0]*count;hi=[n]*count
                for _ in range(depth):
                    probes=[(i,(lo[i]+hi[i])//2) for i in range(count) if lo[i]<hi[i]]
                    if probes:
                        t=self.work_mem.gather(t,[base+mid*4 for _,mid in probes],tag='CDF_random_probe')
                        self.traffic['attention_scratch_read_bytes']+=4*len(probes)
                    # Padded fixed-depth search: inactive lanes are masked,
                    # but do not get a free comparator-energy credit.
                    t=self.sampler(t,count,'cdf_search')
                    for i,mid in probes:
                        if uniform[i]>=cumulative[mid]:lo[i]=mid+1
                        else:hi[i]=mid
                ids.extend(min(n-1,i) for i in lo)
            indices=[row['indices'][i] for i in ids]
            self.traffic['omitted_uniform_SRAM_bytes']+=a['samples']*8
            self.actions['ATT_local_uniform_live_words_peak']=max(self.actions['ATT_local_uniform_live_words_peak'],lanes)
            t=self.scratch(t,write=len(indices)*4,kind='sample_indices')
            t=self.gather(t,layer,head,indices,cache)
            self.attn_rows.append(dict(**self.coord,head=head,selected_tokens=n,
                unique_V=len(set(indices)),samples=len(indices),
                adjacent_repeat=sum(x==y for x,y in zip(indices,indices[1:]))/max(1,len(indices)-1)))
        return t

    def gather(self,t,layer,head,indices,cache):
        counts=Counter(indices);self.actions['ATT_V_additions']+=len(indices)*self.dim
        self.actions['ATT_V_unique_head_indices']+=len(counts)
        self.actions['ATT_V_sample_events']+=len(indices)
        slots=self.ac['v_cache_bytes']//self.vecbytes
        if slots<1:raise ValueError('v5 needs at least one V-vector slot')
        length=self.attention_length
        t=self.scratch(t,write=length*4,kind='histogram_clear')
        t=self.op(t,'histogram',vec=len(indices))
        t=self.scratch(t,read=8*len(indices),write=4*len(indices),kind='histogram')
        kvhead=head//self.group;base=self.arena['V'][0]
        for index,count in sorted(counts.items()):
            key=(kvhead,index)
            if key not in cache:
                t=self.ranges(t,[(self.kv_address(layer,index,kvhead,True),self.vecbytes)],'V_gather')
                if len(cache)>=slots:_,slot=cache.popitem(last=False)
                else:slot=len(cache)
                cache[key]=slot
                t=self.work_mem.transfer(t,base+slot*self.vecbytes,self.vecbytes,True,'V_cache_fill')
                self.traffic['attention_scratch_write_bytes']+=self.vecbytes
                self.actions['ATT_V_cache_misses']+=1
            else:
                slot=cache[key];cache.move_to_end(key);self.actions['ATT_V_cache_hits']+=1
            t=self.work_mem.transfer(t,base+slot*self.vecbytes,self.vecbytes,False,'V_operand')
            self.traffic['attention_scratch_read_bytes']+=self.vecbytes
            t=self.op(t,'V_accumulate',vec=count*self.dim)
        return self.op(t,'sample_mean',vec=self.dim,nl=1)
