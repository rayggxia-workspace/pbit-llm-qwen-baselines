"""Exact Python storage/comparator oracle and reproducible synthetic activity."""
from pathlib import Path
import hashlib,json,random
P=Path(__file__).resolve().parent
def save(p,x):p.write_bytes((json.dumps(x,indent=2)+'\n').encode())
def pack(xs,w):return sum(x<<(i*w) for i,x in enumerate(xs))
def main():
    specs=[]
    for w,g,c in [(12,0,0),(12,1,0),(16,0,0),(16,1,0),(12,1,1),(16,1,1),(11,1,0)]:
        top='bank_w%d_g%d_c%d'%(w,g,c);spec=dict(top=top,width=w,gated=g,compare=c)
        specs.append(spec);ow=128 if c else 128*w
        rtl='module %s(input wire clk,wr_en,input wire[2:0] wr_group,input wire[%d:0] wr_data,input wire[%d:0] random_words,output wire[%d:0] result);\nthreshold_bank #(.W(%d),.GATED(%d),.COMPARE(%d)) u(clk,wr_en,wr_group,wr_data,random_words,result);\nendmodule\n'%(top,16*w-1,128*w-1,ow-1,w,g,c)
        (P/(top+'.sv')).write_bytes(rtl.encode())
        for seed in [17,503,1009]:
            rng=random.Random(seed);q=[None]*128;lines=[];counts=dict(checked=0,writes=0,compared_bits=0)
            # Warm load (8), settle (4), measured load (8), sample (160), idle (32).
            for cycle in range(212):
                load=cycle<8 or 12<=cycle<20
                group=cycle if cycle<8 else (cycle-12 if load else 0)
                data=[rng.randrange(1<<(w-1)) for _ in range(16)] if load else [0]*16
                # Score buffer uses all bits; threshold <=1/2 including exact 1/2.
                if load and w==11:data=[rng.getrandbits(w) for _ in range(16)]
                if load and w!=11 and group==0:data[:4]=[0,1,1<<(w-1),(1<<(w-1))-1]
                rand=[rng.getrandbits(w) for _ in range(128)] if 20<=cycle<180 else [0]*128
                if load:q[group*16:group*16+16]=data;counts['writes']+=16
                check=all(x is not None for x in q)
                if check:
                    expected=pack([int(a<b) for a,b in zip(rand,q)],1) if c else pack(q,w)
                    counts['checked']+=1;counts['compared_bits']+=ow
                else:expected=0
                lines.append('%x %x %x %x %x %x'%(load,group,pack(data,w),pack(rand,w),check,expected))
            d=P/'vectors'/top/str(seed);d.mkdir(parents=True,exist_ok=False)
            (d/'vectors.txt').write_bytes(('\n'.join(lines)+'\n').encode())
            save(d/'META.json',dict(seed=seed,cycles=212,counts=counts,windows=[
                dict(name='load',start=120,end=200,cycles=8),dict(name='sample_hold',start=200,end=1800,cycles=160),
                dict(name='idle',start=1800,end=2120,cycles=32),dict(name='transaction',start=120,end=1800,cycles=168)],
                vectors_sha256=hashlib.sha256((d/'vectors.txt').read_bytes()).hexdigest()))
    save(P/'CASES.json',specs)
    print('GENERATED',len(specs),'tops, 21 traces, each 212 cycles')
if __name__=='__main__':main()
