"""Independent cycle oracle and reproducible activity windows, Python >=3.6."""
import argparse
import hashlib
import json
import random
from pathlib import Path


def pack(fields):
    value=0
    for width,x in fields:
        if not 0 <= x < 1<<width:raise ValueError('field out of range')
        value=(value<<width)|x
    return value


def advance(s):
    # Independent bit-list realization of the published Galois map (16 steps).
    a=[(s>>k)&1 for k in range(32)]
    for _ in range(16):
        low=a[0];a=a[1:]+[0]
        for k in (0,1,21,31):a[k]^=low
    return sum(v<<k for k,v in enumerate(a))


def make(out,n=64,m=64,t=32,k=32,ext=0,kind=0,seed=1):
    if t<1 or k<1 or k>256 or k&(k-1) or t%k:raise ValueError('invalid T/K')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    rng=random.Random(seed)
    state=dict(rng=1,seeded=0,running=0,count=0,done=0,error=0)
    inp=[];exp=[];windows=[];accepted=0
    cur=dict(rst=1,sv=0,seed=0,start=0,ready=1,q=0,one=0,w=0,ev=1,ew=0,bits=0)
    def emit(**changes):
        nonlocal accepted
        cur.update(changes);c=cur;s=state
        sr=not s['running'];fr=not s['running'] and (ext or s['seeded']) and not c['sv']
        valid=bool(s['running'] and (not ext or c['ev']))
        er=bool(ext and s['running'] and c['ready'])
        word=c['ew'] if ext else s['rng']%256
        threshold=(s['count']//(t//k))*(256//k)+word%(256//k) if s['running'] else 0
        bits=sum((bool(s['running']) and (bool((c['one']>>i)&1) or threshold<((c['q']>>(8*i))&255)))<<i for i in range(n))
        weight_bytes=c['w'].to_bytes(n*m,'little')
        events=[((c['bits'] if kind==2 else bits)>>i)&1 for i in range(n)]
        # Numerical byte multiplication is independent of the RTL AND implementation.
        product=int.from_bytes(bytes(w*events[j%n] for j,w in enumerate(weight_bytes)),'little')
        result=[(1,int(sr)),(1,s['error']),(1,int(fr)),(1,int(er)),(1,int(valid)),
                (n,bits),(8,threshold),(8*n*m,product),(1,s['done'])]
        if kind==1:result[-2]=(8*n*m,0)
        if kind>=2:result=[(1,0)]*5+[(n,c['bits'] if kind==2 else 0),(8,0),(8*n*m,product if kind==2 else c['w']),(1,0)]
        inp.append(pack([(1,c['rst']),(1,c['sv']),(32,c['seed']),(1,c['start']),(1,c['ready']),
                         (8*n,c['q']),(n,c['one']),(8*n*m,c['w']),(1,c['ev']),(8,c['ew']),(n,c['bits'])]))
        exp.append(pack(result))
        fire=valid and c['ready']
        if kind<=1:accepted+=int(fire and c['rst'])
        if not c['rst']:s.update(rng=1,seeded=0,running=0,count=0,done=0,error=0)
        else:
            s.update(done=0,error=0)
            if c['sv'] and sr:
                if c['seed']==0:s['error']=1
                else:s.update(rng=c['seed'],seeded=1)
            if c['start'] and fr:s.update(running=1,count=0)
            if fire:
                if not ext:s['rng']=advance(s['rng'])
                if s['count']==t-1:s.update(running=0,count=0,done=1)
                else:s['count']+=1
    def window(name,start,before,mode):
        windows.append(dict(name=name,start_ns=20+10*start,end_ns=20+10*len(inp),
                            cycles=len(inp)-start,accepted_samples=accepted-before,mode=mode,
                            completed_frames=1 if mode=='active' and kind<=1 else 0))
    emit(rst=0);emit(rst=1,sv=1,seed=0);emit(sv=0)
    emit(sv=1,seed=(seed or 1));emit(sv=0)
    for case in range(6):
        start=len(inp);before=accepted
        q=[];ones=0
        for i in range(n):
            code=[0,256,128,1+i*254//max(1,n-1),rng.choice([0,4,8,16,32]),rng.randrange(257)][case]
            q.append(min(code,255));ones|=(code==256)<<i
        weights=[rng.randrange(256) for _ in range(n*m)]
        weights[:min(4,len(weights))]=[0,127,128,255][:min(4,len(weights))]
        w=int.from_bytes(bytes(weights),'little');qpacked=int.from_bytes(bytes(q),'little')
        def event_bits():
            return sum((bool((ones>>i)&1) or rng.randrange(256)<q[i])<<i for i in range(n))
        emit(start=1,q=qpacked,one=ones,w=w,ready=1,ev=1,ew=rng.randrange(256),bits=0)
        emit(start=0,ew=cur['ew'],bits=event_bits())
        # One deliberate backpressure case. External valid/word are held when stalled.
        while state['running']:
            pause=(case==5 and len(inp)%7 in (0,1))
            stalled=bool(cur['ev'] and not cur['ready'])
            ev=cur['ev'] if stalled else (0 if ext and case==5 and len(inp)%11==3 else 1)
            emit(ready=int(not pause),ev=ev,ew=(cur['ew'] if stalled else rng.randrange(256)),
                 sv=1 if case==5 and len(inp)%13==0 else 0,seed=0x12345678,bits=event_bits())
        emit(sv=0,start=0,ready=1,ev=1,bits=0)
        window('active_%d'%case,start,before,'active')
        start=len(inp);before=accepted
        for _ in range(16):emit(bits=0)
        window('idle_%d'%case,start,before,'idle')
    # Reset while running and restart; functional only, excluded from PPA windows.
    emit(start=1);emit(start=0,ready=0);emit(rst=0);emit(rst=1,sv=1,seed=123);emit(sv=0,start=0)
    iw=1+1+32+1+1+8*n+n+8*n*m+1+8+n;ow=5+n+8+8*n*m+1
    for name,values,width in [('input.hex',inp,iw),('expected.hex',exp,ow)]:
        with (out/name).open('w',encoding='ascii',newline='\n') as f:
            f.writelines(('{:0%dx}\n'%((width+3)//4)).format(v) for v in values)
    receipt=dict(n=n,m=m,t=t,k=k,external_rng=ext,kind=kind,seed=seed,cycles=len(inp),
                 windows=windows,accepted=accepted,input_width=iw,output_width=ow,
                 word_source='existing Galois LFSR32, pre-update low8, 16 shifts/accepted sample',
                 data='synthetic endpoint/ramp/sparse/random activation and W8 signed extremes; not real model trace')
    receipt['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [out/'input.hex',out/'expected.hex']}
    with (out/'vectors.json').open('w',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2);f.write('\n')
    return receipt


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('out',type=Path)
    for name,default in [('n',64),('m',64),('t',32),('k',32),('ext',0),('kind',0),('seed',1)]:a.add_argument('--'+name,type=int,default=default)
    args=vars(a.parse_args());result=make(**args);print(json.dumps({k:result[k] for k in ['cycles','accepted','kind','seed']}))
