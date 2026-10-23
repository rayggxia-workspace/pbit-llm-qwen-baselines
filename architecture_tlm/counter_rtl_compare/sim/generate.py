"""Independent scalar dot oracle; no reuse of RTL bit-plane/reduction algorithms."""
import argparse,hashlib,json,random
from pathlib import Path
def pack(values,width):
    return sum((v & ((1<<width)-1)) << (width*i) for i,v in enumerate(values))
def write_hex(p,values,width):
    p.write_text(''.join(format(v,'0%dx'%((width+3)//4))+'\n' for v in values),encoding='ascii')
def make(out,n=64,m=1,t=32,seed=17,random_frames=8,profile='functional'):
    out.mkdir(parents=True,exist_ok=False);rng=random.Random(seed);frames=[]
    def frame(label,w,sign,bins,bits,ones=None):
        ones=ones or [0]*n
        # Exact desired integer bin sums, computed with event counts per input.
        events=[sum(int(s[i] or ones[i]) for s in bits) for i in range(n)]
        gold=[sum(w[o*n+i]*(1-2*sign[i])*events[i] for i in range(n) if bins[i]==b)
              for o in range(m) for b in range(4)]
        sw=(n*t*128).bit_length()+1
        assert all(-(1<<(sw-1))<=v<(1<<(sw-1)) for v in gold)
        frames.append(dict(label=label,w=w,sign=sign,bins=bins,bits=bits,ones=ones,gold=gold))
    # Both endpoints, every bin, all-zero, forced-one, cancellation, and all W8 codes.
    for b in range(4):
        frame('positive_endpoint_bin%d'%b,[-128]*(m*n),[1]*n,[b]*n,[[1]*n for _ in range(t)])
        frame('negative_endpoint_bin%d'%b,[-128]*(m*n),[0]*n,[b]*n,[[1]*n for _ in range(t)])
    frame('all_zero',[127]*(m*n),[0]*n,[i%4 for i in range(n)],[[0]*n for _ in range(t)])
    frame('true_one',[-128]*(m*n),[1]*n,[i%4 for i in range(n)],[[0]*n for _ in range(t)],[1]*n)
    frame('cancellation',[127]*(m*n),[i%2 for i in range(n)],[0]*n,[[1]*n for _ in range(t)])
    for offset in range(0,256,n):
        frame('codes_%d'%offset,[((i+offset)%256)-128 for o in range(m) for i in range(n)],
              [i%2 for i in range(n)],[i%4 for i in range(n)],[[1]*n for _ in range(t)])
    for j in range(random_frames):
        w=[rng.randrange(-128,128) for _ in range(n*m)]
        sign=[rng.randrange(2) for _ in range(n)];bins=[rng.randrange(4) for _ in range(n)]
        # Probability-like shared random threshold within a sample; random weights remain fixed.
        bounds={'functional':(0,257),'mixed':(0,257),'sparse':(0,65),'dense':(192,257),'zero':(0,1)}
        q=[rng.randrange(*bounds[profile]) for _ in range(n)];bits=[]
        for k in range(t):
            r=rng.randrange(256);bits.append([int(r<x) for x in q])
        frame('random_%d'%j,w,sign,bins,bits)
    if profile!='functional':frames=[f for f in frames if f['label'].startswith('random_')]
    sw=(n*t*128).bit_length()+1
    write_hex(out/'weights.hex',[pack(f['w'],8) for f in frames],8*n*m)
    write_hex(out/'sign.hex',[pack(f['sign'],1) for f in frames],n)
    write_hex(out/'bins.hex',[pack(f['bins'],2) for f in frames],2*n)
    write_hex(out/'ones.hex',[pack(f['ones'],1) for f in frames],n)
    write_hex(out/'samples.hex',[pack(s,1) for f in frames for s in f['bits']],n)
    write_hex(out/'gold.hex',[pack(f['gold'],sw) for f in frames],m*4*sw)
    meta=dict(n=n,m=m,t=t,sw=sw,seed=seed,profile=profile,frames=len(frames),labels=[f['label'] for f in frames],
              bin_outputs=len(frames)*m*4,model_data='Synthetic functional stimulus, not LLM activations',
              sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.hex')})
    (out/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    return meta
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',type=Path,required=True)
    for k,v in [('n',64),('m',1),('t',32),('seed',17),('random-frames',8)]:a.add_argument('--'+k,type=int,default=v)
    x=a.parse_args();print(json.dumps(make(x.out,x.n,x.m,x.t,x.seed,x.random_frames)))
