"""Independent exact-integer oracle + RTL handshake test. No technology claim."""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
CASES={'dig_fp32_add':(7,1), 'dig_fp32_mul':(7,1), 'dig_bf16_mul':(7,1),
       'dig_fp32_to_bf16':(2,1), 'dig_bf16_mac':(14,1), 'dig_bf16_mac8':(14,8)}

def flush(x):
    if (x>>23)&255 == 0:
        return x & 0x80000000, 8 if x & 0x7fffff else 0
    return x,0

def unpack(x):
    e=(x>>23)&255
    return (-(1<<23)-(x&0x7fffff) if x>>31 else (1<<23)+(x&0x7fffff)),e-150

def pack_integer(value,exponent):
    if not value:return 0,0
    sign=int(value<0);v=abs(value);k=v.bit_length()-1;shift=k-23;e=k+exponent+127
    # Independently round on IEEE's subnormal lattice BEFORE flushing results.
    if e<=0:
        tiny_shift=-(exponent+149)
        if tiny_shift>0:
            q,r=divmod(v,1<<tiny_shift);half=1<<(tiny_shift-1)
            q+=int(r>half or (r==half and q&1));ix=int(r!=0)
        else:q=v<<(-tiny_shift);ix=0
        if q >= (1<<23):return (sign<<31)|0x00800000,ix
        return sign<<31,5
    if shift>0:
        q,r=divmod(v,1<<shift);half=1<<(shift-1)
        q+=int(r>half or (r==half and q&1));ix=int(r!=0)
    else:q=v<<(-shift);ix=0
    if q==(1<<24):q>>=1;e+=1
    if e>=255:return (sign<<31)|0x7f800000,ix|3
    assert e>0
    return (sign<<31)|(e<<23)|(q&0x7fffff),ix

def arithmetic(op,a,b):
    a,fa=flush(a);b,fb=flush(b);f=fa|fb
    ea=(a>>23)&255;eb=(b>>23)&255
    na=ea==255 and a&0x7fffff;nb=eb==255 and b&0x7fffff
    ia=ea==255;ib=eb==255;za=(a&0x7fffffff)==0;zb=(b&0x7fffffff)==0
    sign=(a^b)>>31
    if na or nb or (op=='add' and ia and ib and sign) or (op=='mul' and ((ia and zb) or (ib and za))):return 0x7fc00000,f|16
    if op=='add':
        if ia:return a,f
        if ib:return b,f
        if za and zb:return (a&b)&0x80000000,f
        if za:return b,f
        if zb:return a,f
    else:
        if ia or ib:return (sign<<31)|0x7f800000,f
        if za or zb:return sign<<31,f
    ma,xa=unpack(a);mb,xb=unpack(b)
    if op=='add':e=min(xa,xb);y,s=pack_integer((ma<<(xa-e))+(mb<<(xb-e)),e)
    else:y,s=pack_integer(ma*mb,xa+xb)
    return y,f|s

def convert(a):
    a,f=flush(a);e=(a>>23)&255
    if e==255:return (0x7fc0 if a&0x7fffff else a>>16),f|(16 if a&0x7fffff else 0)
    if not(a&0x7fffffff):return a>>16,f
    q,r=divmod(a,65536);q+=int(r>32768 or(r==32768 and q&1));s=int(r!=0)
    if ((q>>7)&255)==255:s|=3
    return q&65535,f|s

def oracle(top,a,b,c=0):
    if top=='dig_fp32_add':return arithmetic('add',a,b)
    if top=='dig_fp32_mul':return arithmetic('mul',a,b)
    if top=='dig_bf16_mul':return arithmetic('mul',(a&65535)<<16,(b&65535)<<16)
    if top=='dig_fp32_to_bf16':return convert(a)
    y,s=0,0
    for lane in range(CASES[top][1]):
        p,fp=arithmetic('mul',((a>>(16*lane))&65535)<<16,((b>>(16*lane))&65535)<<16)
        q,fq=arithmetic('add',p,(c>>(32*lane))&0xffffffff)
        y|=q<<(32*lane);s|=(fp|fq)<<(5*lane)
    return y,s

def values(rng,top,i):
    directed=[0,0x80000000,1,0x007fffff,0x00800000,0x00800001,0x3f800000,0xbf800000,
              0x3f800001,0x3f7fffff,0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00000,0x7f800001,
              0x3f808000,0x3f818000,0x33800000,0xb3800000]
    def one(j):
        if i<400:return directed[j%20],directed[(j//20)%20],directed[(j*7)%20]
        if i<440:
            return (0x00800000+(j%4)) | ((j&1)<<31),0x3f7fffff-(j%4),0
        if i%3==0:
            a=(rng.randrange(2)<<31)|(rng.randrange(1,255)<<23)|rng.getrandbits(23)
            b=(a^0x80000000)+(rng.randrange(-8,9))
            return a,b&0xffffffff,rng.getrandbits(32)
        return rng.getrandbits(32),rng.getrandbits(32),rng.getrandbits(32)
    n=CASES[top][1];aa=bb=cc=0
    for lane in range(n):
        a,b,c=one(i+lane)
        if 'bf16' in top and top!='dig_fp32_to_bf16':a>>=16;b>>=16;w=16
        else:w=32
        aa|=a<<(w*lane);bb|=b<<(w*lane);cc|=c<<(32*lane)
    return aa,bb,cc

def vectors(top,seed,count=1200):
    rng=random.Random(seed);lat,_=CASES[top];mac='mac' in top
    v0=[0]* (7 if mac else lat);v1=[0]*7
    held=None;out=[];phases=[];i=0
    # First continuous region measures intrinsic L/II; gaps, forced backpressure,
    # long idle, restart and reset-under-load follow with identical data oracles.
    for cyc in range(count+350):
        rst=0 if cyc<3 or cyc in [count+80,count+81] else 1
        if cyc<800:phase='continuous';iv=1;ready=1
        elif cyc<1000:phase='stall';iv=1;ready=int(cyc%23>=12)
        elif cyc<count:phase='sparse';iv=int(rng.random()<.65);ready=int(rng.random()<.72)
        elif cyc<count+60:phase='idle';iv=0;ready=1
        elif cyc<count+150:phase='wake_reset';iv=1;ready=1
        else:phase='drain_idle';iv=0;ready=1
        if not rst:held=None
        if held is None and iv and rst:held=values(rng,top,i);i+=1
        iv=int(held is not None and rst);a,b,c=held or (0,0,0)
        adv1=not v1[-1] or ready
        adv0=not v0[-1] or (adv1 if mac else ready)
        out.append((rst,iv,ready,a,b,c));phases.append(phase)
        if not rst:v0=[0]*len(v0);v1=[0]*len(v1)
        else:
            old=v0[-1]
            if adv0:v0=[iv]+v0[:-1]
            if mac and adv1:v1=[old]+v1[:-1]
        if iv and adv0:held=None
    return out,phases

def run(args,top,seed,out):
    out.mkdir(parents=True,exist_ok=False)
    vs,phases=vectors(top,seed,args.cycles)
    mac='mac' in top;lat,n=CASES[top]
    text=str(len(vs))+'\n'+'\n'.join(f'{r} {iv} {ready} {a:x} {b:x}'+(f' {c:x}' if mac else '') for r,iv,ready,a,b,c in vs)+'\n'
    (out/'vectors.txt').write_text(text,encoding='ascii',newline='\n')
    bench=ROOT/'tests'/('tb_mac.sv' if mac else 'tb_digital.sv')
    rtl=[str(p) for p in sorted((ROOT/'rtl').glob('*.sv'))]
    exe=out/'sim.vvp';cmd=[args.iverilog]
    if args.ivl:cmd+=['-B',str(Path(args.ivl))]
    defines=[f'-DMAC_TOP={top}',f'-DMAC_LANES={n}'] if mac else [f'-DDIG_TOP={top}']
    cmd+=['-g2012','-Wall',*defines,'-s','tb_mac' if mac else 'tb_digital','-o',str(exe),*rtl,str(bench)]
    cp=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    (out/'compile.log').write_text(cp.stdout+cp.stderr,encoding='utf-8',newline='\n')
    if cp.returncode:raise RuntimeError(cp.stderr)
    cmd=[args.vvp]+(['-M',str(Path(args.ivl))] if args.ivl else [])+[str(exe),'+VECTORS='+str(out/'vectors.txt'),'+OUTPUT='+str(out/'trace.txt'),'+PERIOD_NS='+str(args.period_ns)]
    if args.vcd:cmd+=['+VCD='+str(out/'wave.vcd')]
    cp=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    (out/'simulation.log').write_text(cp.stdout+cp.stderr,encoding='utf-8',newline='\n')
    if cp.returncode:raise RuntimeError(cp.stdout+cp.stderr)
    queue=collections.deque();ops=0;delay=[];last_accept=None;ii=[];window_counts=collections.Counter();accepted_counts=collections.Counter();blocked=None
    rows=(out/'trace.txt').read_text().splitlines()
    assert len(rows)==len(vs)
    for row,vec,phase in zip(rows,vs,phases):
        cells=row.split();cyc=int(cells[0]);r,iv,ready,a,b,c=vec
        if 'x' in ''.join(cells).lower() or 'z' in ''.join(cells).lower():raise AssertionError('unknown RTL '+row)
        rr,ir,ov,orr=map(int,cells[1:5]);y=int(cells[5],16);flags=int(cells[6],16)
        assert rr==r and orr==ready
        if not r:queue.clear();blocked=None;continue
        if blocked is not None:assert (ov,y,flags)==blocked,('blocked output changed',row)
        blocked=(ov,y,flags) if ov and not ready else None
        if ov and ready:
            assert queue,('unexpected output',top,seed,cyc)
            expected,ef,accepted=queue.popleft()
            assert (y,flags)==(expected,ef),(top,seed,cyc,hex(y),hex(expected),flags,ef)
            ops+=1;delay.append(cyc-accepted);window_counts[phase]+=1
        if iv and ir:
            accepted_counts[phase]+=1
            ey,ef=oracle(top,a,b,c);queue.append((ey,ef,cyc))
            if phase=='continuous' and last_accept is not None:ii.append(cyc-last_accept)
            last_accept=cyc
    assert not queue,'not drained'
    assert min(delay)==lat,(top,min(delay),lat)
    assert min(ii)==1 and max(ii)==1,(top,ii[:10])
    windows=[]
    for phase in dict.fromkeys(phases):
        ids=[i for i,p in enumerate(phases) if p==phase]
        windows.append(dict(name=phase,start_cycle=min(ids),end_cycle=max(ids)+1,
            start_ns=(min(ids)+1)*args.period_ns,end_ns=(max(ids)+2)*args.period_ns,
            completed_transactions=window_counts[phase],frames=window_counts[phase],accepted_samples=accepted_counts[phase],operations_per_transaction=n*(2 if mac else 1)))
    result=dict(top=top,seed=seed,status='passed',completed_transactions=ops,lanes=n,
        latency_no_stall_clocks=lat,observed_min_latency=min(delay),input_II_continuous=1,
        input_sha256=hashlib.sha256(text.encode()).hexdigest(),windows=windows,
        numerical_contract='IEEE RNE then output FTZ; input DAZ; canonical NaN; no subnormal outputs',rtl_only=True)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--ivl')
    p.add_argument('--case',choices=list(CASES));p.add_argument('--seed',type=int);p.add_argument('--cycles',type=int,default=1200)
    p.add_argument('--period-ns',type=float,default=10.0);p.add_argument('--vcd',action='store_true');args=p.parse_args()
    if args.output.exists():raise SystemExit('Output exists; use new immutable directory')
    args.output.mkdir(parents=True);results=[]
    for top in ([args.case] if args.case else CASES):
        for seed in ([args.seed] if args.seed is not None else [17,31,193]):
            print('RUN',top,seed,flush=True)
            results.append(run(args,top,seed,args.output/(top+'_'+str(seed))))
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['rtl','tests'] for p in sorted((ROOT/folder).glob('*')) if p.is_file()}
    summary=dict(status='passed',tests=results,source_sha256=sources,technology_validation=False)
    (args.output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS',len(results),flush=True)

if __name__=='__main__':main()
