"""Independent scalar GF/Bivium/state schedule oracles for the GPU model."""
from pathlib import Path
import re,json,hashlib,numpy as np

HERE=Path(__file__).parent
def table():return np.frombuffer((HERE/'gf_tables.bin').read_bytes(),dtype='<u8').reshape(4,256,9)
def gf_step(state):
    a=table();w=np.bitwise_xor.reduce(np.stack([a[i,(int(state)>>(8*i))&255] for i in range(4)]),axis=0)
    return [int(w[j//8])>>((j%8)*8)&255 for j in range(64)],int(w[8])&0xffffffff
def cpu_gate():
    source=(HERE/'gf_map.sv').read_text();symbols={};out=[None]*512;nxt=[None]*32
    def term(t):
        t=t.strip()
        if t.startswith('state['):return 1<<int(t[6:-1])
        return symbols[t]
    for name,index,rhs in re.findall(r'assign\s+(\w+)(?:\[(\d+)\])?\s*=\s*([^;]+);',source):
        value=0
        for t in rhs.split('^'):value^=term(t)
        if index:(out if name=='random_word' else nxt)[int(index)]=value
        else:symbols[name]=value
    for offset,width,rhs in re.findall(r'assign\s+random_word\[(\d+)\s*\+:\s*(\d+)\]\s*=\s*\{([^}]+)\};',source):
        terms=rhs.split(',');assert len(terms)==int(width)
        for bit,t in enumerate(reversed(terms)):out[int(offset)+bit]=term(t)
    assert all(x is not None for x in out+nxt)
    a=table()
    for b in range(4):
        for value in range(256):
            s=value<<(b*8);oracle=[0]*9
            for i,mask in enumerate(out):oracle[i//64]|=((s&mask).bit_count()&1)<<(i%64)
            for i,mask in enumerate(nxt):oracle[8]|=((s&mask).bit_count()&1)<<i
            assert a[b,value].tolist()==oracle,(b,value)
    return dict(passed=True,GF_RTL_all_table_entries=1024,gf_map_sha256=hashlib.sha256((HERE/'gf_map.sv').read_bytes()).hexdigest(),gf_table_sha256=hashlib.sha256((HERE/'gf_tables.bin').read_bytes()).hexdigest())

def gpu_gate():
    import torch,time
    from hardware_rng import Sampler,initial,biv_cpu
    checked=[]
    for k in (128,256,2048):
        for mode in ('gf64_bivium',):
            sampler=Sampler(mode,k,101);rng=np.random.default_rng(1981109)
            n=k-1;p=rng.integers(0,129,(4,n));p[0]=0;p[3]=255;p[3,0]=0
            planes=torch.zeros((4,26,n),device='cuda');planes[:,0]=torch.from_numpy(p).cuda()/256
            c,f=initial(1,k,709);sampler.pools['fixture']=(torch.from_numpy(c.copy()).cuda(),torch.from_numpy(f.copy()).cuda())
            for call in range(2):
                out,stats,(words,ranks)=sampler.sample(planes,8,198,debug=True,pool_key='fixture')
                actual=out.cpu().numpy();wordtrace=words.cpu().numpy();ranktrace=ranks.cpu().numpy()
                fair=f[0].tolist();cand=c[0].tolist()
                for head in range(4):
                    winner=0
                    for step in range(8):
                        if mode.startswith('gf64'):
                            w=[]
                            for bank in range(k//64):
                                ws,cand[bank]=gf_step(cand[bank]);w+=ws
                        else:
                            w=[]
                            for lane in range(1 if mode=='lfsr32_shared8' else k):
                                s=cand[lane];w.append(s&255)
                                for _ in range(8):s=(s>>1)^(0x80200003 if s&1 else 0)
                                cand[lane]=s
                            if mode=='lfsr32_shared8':w=w*k
                        assert np.array_equal(wordtrace[head,step],w),(mode,k,head,step,'words')
                        active=[i for i in range(n) if w[i]<p[head,i]]
                        hold=(winner in active) or not active;rank=-1
                        if not hold:
                            if len(active)==1:rank=0
                            elif mode=='gf64_bivium':
                                mask=(1<<(len(active)-1).bit_length())-1
                                for retry in range(64):
                                    raw,fair=biv_cpu(fair,max(8,(k-1).bit_length()));rank=raw&mask
                                    if rank<len(active):break
                                assert rank<len(active)
                            else:rank=int(ranktrace[head,step]);assert 0<=rank<len(active)
                            winner=active[rank]
                        assert int(actual[head,step])==winner,(mode,k,head,step,'winner')
                        assert int(ranktrace[head,step])==rank
                if mode=='gf64_bivium':assert sampler.pools['fixture'][1].cpu().numpy()[0].tolist()==fair
                got=sampler.pools['fixture'][0].cpu().numpy()[0]
                length=k//64 if mode.startswith('gf64') else (1 if mode=='lfsr32_shared8' else k)
                assert got[:length].tolist()==cand[:length];c[0]=got;f[0]=sampler.pools['fixture'][1].cpu().numpy()[0]
            checked.append(dict(k=k,source=mode,calls=2,oracle_words_and_winners=True))
            if k==2048:
                assert (actual>255).any(), 'wide-rank test must visit an address above255'
    timings=[]
    for k in (128,256,2048):
        for mode in ('gf64_bivium',):
            sampler=Sampler(mode,k,101);planes=torch.zeros((32,26,k),device='cuda');planes[:,0]=.25
            sampler.sample(planes,64,198);torch.cuda.synchronize();start=time.perf_counter()
            sampler.sample(planes,64,199);torch.cuda.synchronize();seconds=time.perf_counter()-start
            timings.append(dict(k=k,source=mode,rows=32,S=64,seconds=seconds))
    return dict(passed=True,scalar_oracles=checked,timings=timings)

if __name__=='__main__':
    import sys
    if sys.argv[1]=='cpu':print(json.dumps(cpu_gate()))
    else:print(json.dumps(gpu_gate()))
