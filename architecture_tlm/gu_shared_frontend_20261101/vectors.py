"""Independent integer/bit-plane GU oracles, paired fixtures, T64 strata."""
from pathlib import Path
import hashlib
import json
import random

ROOT=Path(__file__).resolve().parent


def save(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode())


def fixtures(c,seed):
    M=c['M'];groups=M//8;WO=1152*groups;tail=WO+512*M
    rng=random.Random(seed+913);rows=[];expected=[];count=[0]*M;accepted=0;done=False;events_seen=0
    maxabs=0
    resident=[[rng.randrange(-127,128) for n in range(64)] for m in range(M)]
    def frame(mode='random'):
        if mode=='zero':return [(0,0,0)]*64
        if mode=='full':return [(255,0,1)]*64
        if mode=='negative':return [(0,1,1)]*64
        if mode=='mixed':return [(255,n%2,1) for n in range(64)]
        return [(rng.randrange(256),rng.randrange(2),int((n+seed)%29==0)) for n in range(64)]
    zero=frame('zero')
    def add(x,w,t=0,en=1,clear=0,rst=1,ex=0,eg=-7,eu=-6,source_active=True):
        nonlocal accepted,done,count,events_seen,maxabs
        lane=0;sample=[]
        for n,(p,sg,full) in enumerate(x):
            r=(t%64)*4+rng.randrange(4) if source_active else 0
            lane|=(p|(sg<<8)|(full<<9)|(r<<10))<<(18*n)
            sample.append(int(full or r<p)*(-1 if sg else 1))
        di=sum(lane<<(1152*j) for j in range(groups))
        for m in range(M):
            for n,v in enumerate(w[m]):di|=(abs(v)|(int(v<0)<<7))<<(WO+8*(m*64+n))
        di|=(ex&31)<<tail;di|=(eg&31)<<(tail+5);di|=(eu&31)<<(tail+10);di|=clear<<(tail+15)
        if not rst or clear:accepted=0;done=False;count=[0]*M
        elif en and not done:
            for m in range(M):
                direct=sum(a*b for a,b in zip(sample,w[m]))
                planes=sum(sum(a*((abs(b)>>p)&1)*(-1 if b<0 else 1) for a,b in zip(sample,w[m]))<<p for p in range(7))
                assert direct==planes
                count[m]+=direct;maxabs=max(maxabs,abs(count[m]));assert -(1<<19)<=count[m]<(1<<19)
            accepted+=1;done=accepted==64;events_seen+=sum(a!=0 for a in sample)
        out=0
        if done and not clear:
            out=sum((v&0xffffffff)<<(32*m) for m,v in enumerate(count))
            out|=((ex+eg-6)&255)<<(32*M);out|=((ex+eu-6)&255)<<(32*M+8);out|=1<<(32*M+16)
        rows.append(di|(en<<c['din_bits'])|(rst<<(c['din_bits']+1)));expected.append(out)
    add(zero,resident,rst=0,en=0,clear=1);add(zero,resident,rst=0,en=0,clear=1)
    for mode in ('full','negative','mixed','zero','random'):
        x=frame(mode);w=[[127]*64 for _ in range(M)] if mode in ('full','negative') else resident
        add(x,w,clear=1,en=0)
        for t in range(64):
            if t==11:add(x,w,t,en=0)
            add(x,w,t,ex=3,eg=-8,eu=-5)
        assert (not mode in ('full','negative')) or max(abs(z) for z in count)==520192
        for _ in range(3):add(x,w,63,en=1,ex=3,eg=-8,eu=-5)
    # Reset abort and reconfiguration: no unfinished count may leak to next frame.
    x=frame();add(x,resident,clear=1)
    for t in range(7):add(x,resident,t)
    add(x,resident,rst=0);add(zero,resident,clear=1,en=0)
    windows=[]
    for mode,values,changing in [('idle_clock_source_active',zero,True),('idle_source_stopped',zero,False),('hold_nonzero',x,False)]:
        add(values,resident,clear=1,en=0,source_active=False);start=len(rows)
        for t in range(64):add(values,resident,t,en=0,source_active=changing)
        windows.append(dict(mode=mode,start_ns=10+10*start,end_ns=10+10*len(rows),operations=0,samples=0))
    start=len(rows)
    for f in range(8):
        x=frame();ex=(-2,0,2,4)[f%4];eg=-7;eu=-6
        add(x,resident,clear=1,en=0,ex=ex,eg=eg,eu=eu)
        for t in range(64):add(x,resident,t,ex=ex,eg=eg,eu=eu)
        add(x,resident,63,en=0,ex=ex,eg=eg,eu=eu)
    windows.append(dict(mode='replay64',start_ns=10+10*start,end_ns=10+10*len(rows),operations=8,samples=512,outputs=8*M,cycles_per_frame=66))
    dst=ROOT/'fixtures'/c['name']/str(seed);dst.mkdir(parents=True,exist_ok=True)
    for name,values,width in [('stim.hex',rows,c['din_bits']+2),('expect.hex',expected,c['dout_bits'])]:
        (dst/name).write_bytes(('\n'.join(format(v,'0%dx'%((width+3)//4)) for v in values)+'\n').encode())
    save(dst/'WINDOWS.json',dict(transactions=len(rows),windows=windows,synthetic=True,seed=seed,weights='Same resident W across8active frames;loaded outside window',source='64strata with2bit per-lane jitter;all8column source copies identical;not physical PRNG',max_abs_count=maxabs))
    return dict(case=c['name'],seed=seed,transactions=len(rows),max_abs_count=maxabs,accepted_events=events_seen,
        stim_sha256=hashlib.sha256((dst/'stim.hex').read_bytes()).hexdigest(),expect_sha256=hashlib.sha256((dst/'expect.hex').read_bytes()).hexdigest())
