"""GPU transaction model of GF64/LFSR candidates and Bivium rank words.

One program serves four Q heads serially. State persists across queries per
layer/batch-slot/KV group within a scoring block; winner resets per Q query.
No claim of cycle/PPA equivalence. Tables bind the existing GF RTL XOR map.
"""
from pathlib import Path
import hashlib,numpy as np,torch,triton
import triton.language as tl

@triton.jit
def mix(x):
    x=x.to(tl.uint64)+0x9e3779b97f4a7c15
    x=(x^(x>>30))*0xbf58476d1ce4e5b9
    x=(x^(x>>27))*0x94d049bb133111eb
    return x^(x>>31)

@triton.jit
def biv_word(al,ah,bl,bh,BITS:tl.constexpr):
    word=tl.full((),0,tl.uint32)
    for j in range(160):
        t1=((ah>>1)^(ah>>28))&1;t2=((bh>>4)^(bh>>19))&1
        word=word|tl.where(j<BITS,(t1^t2).to(tl.uint32)<<j,0)
        fa=t2^((bh>>17)&(bh>>18)&1)^((ah>>4)&1)
        fb=t1^((ah>>26)&(ah>>27)&1)^((bh>>13)&1)
        ah=((ah<<1)|(al>>63))&0x1fffffff;al=(al<<1)|fa
        bh=((bh<<1)|(bl>>63))&0xfffff;bl=(bl<<1)|fb
    return word,al,ah,bl,bh

@triton.jit
def kernel(P,O,ST,CSTATE,FSTATE,TABLE,TRACE,RANKS,METRIC,SEED,
           N:tl.constexpr,S:tl.constexpr,BLOCK:tl.constexpr,G:tl.constexpr,
           MODE:tl.constexpr,BIV:tl.constexpr,DEBUG:tl.constexpr,RANK_BITS:tl.constexpr):
    group=tl.program_id(0);lane=tl.arange(0,BLOCK)
    ix=lane//64 if MODE==1 else (tl.full((BLOCK,),0,tl.int32) if MODE==2 else lane)
    state=tl.load(CSTATE+group*BLOCK+ix).to(tl.uint32)
    al=tl.load(FSTATE+group*4);ah=tl.load(FSTATE+group*4+1)
    bl=tl.load(FSTATE+group*4+2);bh=tl.load(FSTATE+group*4+3)
    fair_calls=0;retries=0;holds=0;failed=0
    for head in range(G):
        row=group*G+head;winner=0
        p=tl.load(P+(row*26)*N+lane,lane<N,0.)
        for t in range(S):
            if MODE==1:
                out=tl.full((BLOCK,),0,tl.uint64);nxt=tl.full((BLOCK,),0,tl.uint64)
                for byte in tl.static_range(4):
                    address=(byte*256+((state>>(byte*8))&255))*9
                    out=out^tl.load(TABLE+address+(lane%64)//8)
                    nxt=nxt^tl.load(TABLE+address+8)
                word=((out>>((lane%8)*8))&255).to(tl.uint32);state=nxt.to(tl.uint32)
            else:
                word=state&255
                for bit in tl.static_range(8):state=(state>>1)^tl.where((state&1)!=0,0x80200003,0).to(tl.uint32)
            bits=(word.to(tl.float32)<p*256)&(lane<N)
            count=tl.sum(bits.to(tl.int32),0)
            hold=(tl.sum((bits&(lane==winner)).to(tl.int32),0)>0)|(count==0)
            rank=-1
            if (~hold)&(count>1):
                if BIV:
                    mask=(count-1).to(tl.uint32)
                    mask=mask|(mask>>1);mask=mask|(mask>>2);mask=mask|(mask>>4);mask=mask|(mask>>8)
                    raw,al,ah,bl,bh=biv_word(al,ah,bl,bh,RANK_BITS);fair_calls+=1
                    rank=(raw&mask).to(tl.int32);retry=0
                    while (rank>=count)&(retry<63):
                        raw,al,ah,bl,bh=biv_word(al,ah,bl,bh,RANK_BITS)
                        rank=(raw&mask).to(tl.int32);retry+=1;fair_calls+=1;retries+=1
                    failed+=tl.where(rank>=count,1,0)
                    rank=tl.minimum(rank,count-1)
                else:
                    raw=tl.randint(SEED^0x5a912c31,((row*S+t)*128).to(tl.uint32)).to(tl.uint32)
                    den=count.to(tl.uint32);threshold=(0-den).to(tl.uint32)%den;retry=0
                    while (raw<threshold)&(retry<63):
                        retry+=1;raw=tl.randint(SEED^0x5a912c31,((row*S+t)*128+retry).to(tl.uint32)).to(tl.uint32)
                    failed+=tl.where(raw<threshold,1,0);rank=(raw%den).to(tl.int32)
                    fair_calls+=retry+1;retries+=retry
            if (~hold)&(count==1):rank=0
            prefix=tl.cumsum(bits.to(tl.int32),0)
            chosen=tl.min(tl.where(bits&(prefix==rank+1),lane,BLOCK),0)
            winner=tl.where(hold,winner,chosen);holds+=hold.to(tl.int32)
            tl.store(O+row*S+t,winner)
            if DEBUG:
                tl.store(TRACE+(row*S+t)*BLOCK+lane,word)
                tl.store(RANKS+row*S+t,rank)
        tl.store(ST+row*6,S);tl.store(ST+row*6+1,tl.where(failed==0,S,-1))
        for k in tl.static_range(2,6):tl.store(ST+row*6+k,0)
    save=(lane%64==0) if MODE==1 else ((lane==0) if MODE==2 else (lane<BLOCK))
    tl.store(CSTATE+group*BLOCK+ix,state,save)
    tl.store(FSTATE+group*4,al);tl.store(FSTATE+group*4+1,ah)
    tl.store(FSTATE+group*4+2,bl);tl.store(FSTATE+group*4+3,bh)
    tl.store(METRIC+group*4,fair_calls);tl.store(METRIC+group*4+1,retries)
    tl.store(METRIC+group*4+2,holds);tl.store(METRIC+group*4+3,failed)

MASK=(1<<64)-1
def mix_cpu(x):
    x=(x+0x9e3779b97f4a7c15)&MASK;x=((x^(x>>30))*0xbf58476d1ce4e5b9)&MASK
    x=((x^(x>>27))*0x94d049bb133111eb)&MASK;return x^(x>>31)
def biv_cpu(s,bits=8):
    a=int(s[0])|(int(s[1])<<64);b=int(s[2])|(int(s[3])<<64);w=0
    for j in range(160):
        x=((a>>65)^(a>>92))&1;y=((b>>68)^(b>>83))&1
        if j<bits:w|=(x^y)<<j
        fa=y^((b>>81)&(b>>82)&1)^((a>>68)&1)
        fb=x^((a>>90)&(a>>91)&1)^((b>>77)&1)
        a=((a<<1)|fa)&((1<<93)-1);b=((b<<1)|fb)&((1<<84)-1)
    return w,[a&MASK,a>>64,b&MASK,b>>64]

def initial(groups,block,seed):
    c=np.empty((groups,block),dtype=np.uint32);f=np.empty((groups,4),dtype=np.uint64)
    for group in range(groups):
        key=mix_cpu(seed+group*0x100000)
        for lane in range(block):c[group,lane]=mix_cpu(key^(lane+1))&0xffffffff or 1
        f[group]=[mix_cpu(key^4),mix_cpu(key^5)&0x1fffffff,mix_cpu(key^6),mix_cpu(key^7)&0xfffff]
    # Five160-bit advances, matching the existing diagnostic initialization.
    for _ in range(800):
        al,ah,bl,bh=[f[:,i].copy() for i in range(4)]
        x=((ah>>1)^(ah>>28))&1;y=((bh>>4)^(bh>>19))&1
        f[:,0]=(al<<1)|(y^((bh>>17)&(bh>>18)&1)^((ah>>4)&1))
        f[:,1]=((ah<<1)|(al>>63))&0x1fffffff
        f[:,2]=(bl<<1)|(x^((ah>>26)&(ah>>27)&1)^((bh>>13)&1))
        f[:,3]=((bh<<1)|(bl>>63))&0xfffff
    return c,f

class Sampler:
    def __init__(self,mode,k,base_seed):
        self.mode,self.k,self.base_seed=mode,k,base_seed;self.layer=0;self.pools={};self.calls=0;self.metrics=None
        raw=(Path(__file__).parent/'gf_tables.bin').read_bytes();self.table_sha256=hashlib.sha256(raw).hexdigest()
        self.table=torch.from_numpy(np.frombuffer(raw,dtype='<u8').copy()).cuda()
    def sample(self,planes,samples,seed,debug=False,pool_key=None,g=4):
        rows,n=planes.shape[0],planes.shape[-1]
        assert n<=self.k and rows%g==0,(n,self.k,rows,g)
        groups=rows//g;key=(self.layer,groups) if pool_key is None else pool_key
        if key not in self.pools:
            identity=f'{self.base_seed}:{key}:{self.k}'
            keyseed=int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8],'little')
            c,f=initial(groups,self.k,keyseed)
            self.pools[key]=(torch.from_numpy(c).cuda(),torch.from_numpy(f).cuda())
        c,f=self.pools[key]
        out=torch.empty((rows,samples),device='cuda',dtype=torch.int64);stats=torch.empty((rows,6),device='cuda',dtype=torch.int64)
        metrics=torch.empty((groups,4),device='cuda',dtype=torch.int64)
        words=torch.empty((rows,samples,self.k),device='cuda',dtype=torch.int32) if debug else stats
        ranks=torch.empty((rows,samples),device='cuda',dtype=torch.int32) if debug else stats
        kernel[(groups,)](planes,out,stats,c,f,self.table,words,ranks,metrics,seed,
            N=n,S=samples,BLOCK=self.k,G=g,MODE=1 if self.mode.startswith('gf64') else (2 if self.mode=='lfsr32_shared8' else 3),
            BIV=self.mode=='gf64_bivium',DEBUG=debug,RANK_BITS=max(8,(self.k-1).bit_length()),num_warps=4)
        if not bool((stats[:,1]==samples).all()):raise RuntimeError('bounded fair-rank generator cap; no result accepted')
        if not bool(((out>=0)&(out<n)).all()):raise RuntimeError('invalid sampled address')
        total=metrics.sum(0);self.metrics=total if self.metrics is None else self.metrics+total;self.calls+=1
        return out,stats,(words,ranks) if debug else None
    def report(self):
        return dict(source=self.mode,calls=self.calls,metrics=self.metrics.tolist() if self.metrics is not None else None,
            metric_columns=['fair_words','rank_retries','holds','cap_failures'],gf_table_sha256=self.table_sha256,
            state_schedule='persist per layer/batch-slot/KV group within32-window block; four Q heads serial; reset on block or batch-size transition; candidate steps only on sampling frames',
            rank_bits=max(8,(self.k-1).bit_length()),physical_TRNG=False,cycle_PPA_simulation=False)
