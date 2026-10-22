"""Independent arithmetic/transaction scoreboards and RTL edge-latency records."""
import argparse
import hashlib
import importlib.util
import json
import math
import platform
from pathlib import Path
import random
import re
import struct
import subprocess
import sys

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('exact_ref',ROOT/'format_conversion_rtl_20261016/sim/reference.py')
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
KINDS=(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,20,21,22)


def fbits(x):
    try:return struct.unpack('>I',struct.pack('>f',x))[0]
    except OverflowError:return 0xff800000 if x<0 else 0x7f800000


def number(x):return struct.unpack('>f',struct.pack('>I',x))[0]


def add(a,b):return R.add(a,b)[0]


def mul(a,b):
    ta,sa,na,ea=R.decode(a,23);tb,sb,nb,eb=R.decode(b,23);sg=sa^sb
    if ta=='nan' or tb=='nan' or (ta=='inf' and tb=='finite' and nb==0) or (tb=='inf' and ta=='finite' and na==0):return 0x7fc00000
    if ta=='inf' or tb=='inf':return (sg<<31)|0x7f800000
    if na==0 or nb==0:return sg<<31
    return R.pack((-1 if sg else 1)*na*nb,ea+eb,23)[0]


def scaled(x,e,f=23):
    t,s,n,p=R.decode(x,23)
    if t=='nan':return (255<<f)|(1<<(f-1))
    if t=='inf':return (s<<(f+8))|(255<<f)
    if not n:return s<<(f+8)
    return R.pack(-n if s else n,p+e,f)[0]


def unary(x,kind):
    t,s,n,p=R.decode(x,23)
    if t=='nan':return 0x7fc00000
    if kind<2:
        if (x&0x7fffffff)>=0x41800000:return (0 if s else 0x3f800000) if kind==0 else (0 if s else 0x3f800000)
        if kind==1 and not s:return 0x3f800000
        q=min(131072,R.rounded(n,p+13)[0]);i=q>>8;fraction=fbits((q&255)/256)
        if kind==0:
            fn=lambda j:fbits(1/(1+math.exp((1 if s else -1)*j/32)))
        else:fn=lambda j:fbits(math.exp(-j/32))
        a,b=fn(i),fn(min(512,i+1))
        return add(a,mul(add(b,a^0x80000000),fraction))
    if not n and t=='finite':return (s<<31)|0x7f800000
    if kind==3 and s:return 0x7fc00000
    if t=='inf':return (s<<31) if kind==2 else 0
    lead=n.bit_length()-1;e=lead+p;mant=(n<<(23-lead))&0x7fffff;i=mant>>15
    fn=lambda j:fbits(1/(1+j/256) if kind==2 else 1/math.sqrt(1+j/256))
    a,b=fn(i),fn(i+1);v=add(a,mul(add(b,a^0x80000000),fbits((mant&32767)/32768)))
    if kind==2:return scaled(v|(s<<31),-e)
    if e&1:v=mul(v,0x3f3504f3)
    return scaled(v,-(e//2))


def encoder(words,frac):
    decoded=[R.decode(x,frac) for x in words]
    assert all(t=='finite' for t,_,_,_ in decoded)
    mag=max(x&((1<<(frac+8))-1) for x in words)
    _,_,n,p=R.decode(mag,frac)
    top=(n.bit_length()-1+p+int(n&(n-1)!=0)) if n else 0
    qs=bins=signs=ones=0
    for i,(raw,(_,s,n,p)) in enumerate(zip(words,decoded)):
        b=0
        for j in range(1,4):
            delta=top-2*j
            if not n or (n<<(max(0,p-delta))) <= (1<<max(0,delta-p)):b=j
        q=min(255,R.rounded(n,p+8-top+2*b)[0])
        one=n!=0 and (n<<max(0,p-top+2*b)) >= (1<<max(0,top-2*b-p))
        qs|=q<<(8*i);bins|=b<<(2*i);signs|=s<<i;ones|=int(one)<<i
    return qs|(bins<<512)|(signs<<640)|(ones<<704)|((top&65535)<<768)


def vectors(kind,seed):
    rng=random.Random(seed);items=[];expected=[];latencies=[];state=0;cdf=emitted=offset=0
    edges=[0,0x80000000,1,0x007fffff,0x00800000,0x3f800000,0xbf800000,0x7f7fffff,0x7f800000,0xff800000,0x7fc00000]
    total=288 if kind not in (4,5,6,22) else 48
    for i in range(total):
        a=fbits(rng.uniform(-12,12));b=fbits(rng.uniform(-8,8));u0=fbits(1/14);u1=fbits(1e-6);e=rng.randint(-5,5);mean=7
        first=i%14==0;last=i%14==13 or i==total-1;valid=1
        if kind in (0,1,21):
            if i<len(edges)**2:a=edges[i//len(edges)];b=edges[i%len(edges)]
            else:a=rng.getrandbits(32);b=rng.getrandbits(32)
            y=add(a,b) if kind==0 else (mul(a,b) if kind==1 else R.evaluate(6,a,0,0,0,0)[0])
        elif kind in (2,8,9):
            if i==0:first=last=True
            if i==1:first=True
            a=(a>>16)&65535;b=(b>>16)&65535
            operand=(a<<16) if kind==8 else mul(a<<16,(a if kind==9 else b)<<16)
            state=add(0 if first else state,operand)
            if kind==8:y=scaled(state,-mean,7)
            elif kind==9:y=unary(add(mul(state,u0),u1),3)
            else:y=state
        elif kind==3:
            a>>=16;b>>=16;y=R.evaluate(6,add(a<<16,b<<16),0,0,0,0)[0]
        elif kind in (4,5):
            frac=7 if kind==4 else 23;w=frac+9;words=[]
            for j in range(64):
                value=fbits(((-1)**j)*2**(j%20-10)*(1+(rng.random() if i%3 else 0)))
                if i%4==0 and j%9==0:value=0
                if i==1:value=rng.randrange(1,1<<23)
                words.append(value>>16 if frac==7 else value)
            if i==0:words=[0]*64
            a=sum(x<<(w*j) for j,x in enumerate(words));b=0;y=encoder(words,frac)
        elif kind in (6,22):
            counts=[rng.randint(0,2048) for _ in range(64)];a=sum(v<<(12*j) for j,v in enumerate(counts));u0=fbits(rng.uniform(.001,.1));integer=0
            for bn in range(4):
                for bit in range(8):integer+=(counts[(bn*2)*8+bit]-counts[(bn*2+1)*8+bit])*(-1 if bit==7 else 1)*(1<<(bit+2*(3-bn)))
            if kind==22:y=mul(R.pack(integer,e-11,23)[0],u0)
            else:
                y=0
                for bn in range(4):
                    integer_bin=sum((counts[(bn*2)*8+bit]-counts[(bn*2+1)*8+bit])*(-1 if bit==7 else 1)*(1<<bit) for bit in range(8))
                    y=add(y,mul(R.pack(integer_bin,e-2*bn-5,23)[0],u0))
        elif kind==7:
            test_g=edges+[0x41800000,0xc1800000,0x42000000,0xc2000000]
            if i<len(test_g):a=test_g[i]
            y=mul(mul(a,unary(a,0)),b)
        elif kind==10:
            a>>=16;b>>=16;u0=fbits(rng.uniform(.2,2));y=R.evaluate(6,mul(mul(a<<16,u0),b<<16),0,0,0,0)[0]
        elif kind in (11,12,13):
            a=fbits(-rng.random()*20) if kind==11 else fbits(2**rng.uniform(-140,120))
            if i<len(edges):a=edges[i]
            y=unary(a,kind-10)
        elif kind==14:
            if i<len(edges)**2:a=edges[i//len(edges)];b=edges[i%len(edges)]
            ia=rng.randrange(1000);ib=rng.randrange(1000);av,bv=number(a),number(b)
            invalid=math.isnan(av) or math.isnan(bv)
            swap=(math.isnan(av) and not math.isnan(bv)) or (not invalid and ((av>bv) or (av==bv and ia>ib)));a|=ia<<32;b|=ib<<32
            lo,hi=(b&0xffffffff,a&0xffffffff) if swap else (a&0xffffffff,b&0xffffffff)
            il,ih=(ib,ia) if swap else (ia,ib);y=lo|(hi<<32)|(il<<64)|(ih<<80)|(int(invalid)<<96)
        elif kind==15:
            a=rng.getrandbits(64);count=0;y=0
            for j in range(64):y|=count<<(j*7);count+=(a>>j)&1
            y|=count<<448
        elif kind==16:
            first=i%32==0;last=i%32==31 or i==total-1;a=rng.randrange(1<<29);u0=rng.getrandbits(32)
            if first:cdf=emitted=0;offset=u0&((1<<25)-1)
            cdf=(1<<32) if last else min(1<<32,cdf+a)
            nxt=0 if cdf<=offset else (cdf-offset+(1<<25)-1)>>25
            y=nxt-emitted;emitted=nxt
        elif kind==17:
            a=0;b=rng.getrandbits(512)
            for _ in range(i%5):a|=1<<rng.randrange(512)
            bits=a&b;count=min(2,bits.bit_count());index=(bits&-bits).bit_length()-1 if bits else 511
            y=index|(count<<9)
        elif kind==20:
            x0=a>>16;x1=b>>16;a=x0|(x1<<16);ang=rng.uniform(-3,3);u0=fbits(math.cos(ang));u1=fbits(math.sin(ang))
            y0=add(mul(x0<<16,u0),mul(x1<<16,u1)^0x80000000);y1=add(mul(x0<<16,u1),mul(x1<<16,u0));y=y0|(y1<<32)
        else:raise ValueError(kind)
        items.append((valid,int(first),int(last),a,b,u0,u1,e&65535,mean))
        if kind not in (2,8,9) or last:expected.append(y)
        if i%11==4:items.append((0,0,0,0,0,0,0,0,0))
    return items,expected


def run(cmd,log,cwd):
    p=subprocess.run(list(map(str,cmd)),cwd=cwd,capture_output=True,text=True,timeout=180)
    log.append(dict(command=list(map(str,cmd)),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
    if p.returncode:raise RuntimeError(p.stdout+'\n'+p.stderr)
    return p.stdout


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--iverilog',type=Path,required=True);ap.add_argument('--vvp',type=Path,required=True);ap.add_argument('--ivl-lib',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    rtl=sorted((HERE/'rtl').glob('*.sv'))+sorted((ROOT/'format_conversion_rtl_20261016/rtl').glob('*.sv'))
    sources=rtl+sorted((HERE/'rtl').glob('*.svh'))+list((HERE/'sim').glob('*.*'))+[ROOT/'format_conversion_rtl_20261016/sim/reference.py']
    git_result=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True)
    record=dict(scope='functional RTL and synthetic activity, not DC/PT/PPL',git_head=git_result.stdout.strip() if git_result.returncode==0 else None,
                python=sys.version,platform=platform.platform(),tool_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.iverilog,args.vvp)},
                source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.suffix in ('.sv','.svh','.py')},results=[],power_activity=[])
    log=[]
    def save():
        (out/'VALIDATION.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
        (out/'COMMANDS.json').write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    try:
        base=[args.iverilog,'-B',args.ivl_lib,'-g2012','-Wall','-I',HERE/'rtl']
        for kind in KINDS:
            binary=out/f'kind{kind}.vvp'
            run(base+[f'-DKIND={kind}','-s','tb_probe','-o',binary,*rtl,HERE/'sim/tb_probe.sv'],log,out)
            for seed in (20261022,7,1234567):
                items,gold=vectors(kind,seed);file=out/f'kind{kind}_{seed}.hex'
                file.write_text(''.join(' '.join(f'{x:x}' for x in row)+'\n' for row in items),encoding='ascii',newline='\n')
                stdout=run([args.vvp,'-M',args.ivl_lib,binary,'+VECTORS='+str(file)],log,out)
                actual=[int(m[1],16) for m in re.findall(r'^RESULT (\d+) ([0-9a-fA-F]+)$',stdout,re.M)]
                if actual!=gold:
                    different=next((i for i,(a,b) in enumerate(zip(actual,gold)) if a!=b),min(len(actual),len(gold)))
                    record['failed']=dict(kind=kind,seed=seed,index=different,actual=hex(actual[different]) if different<len(actual) else None,expected=hex(gold[different]) if different<len(gold) else None)
                    raise AssertionError(str(record['failed']))
                accepted=[tuple(map(int,x)) for x in re.findall(r'^ACCEPT (\d+) (\d+) (\d+)$',stdout,re.M)]
                cycles=[int(m[0]) for m in re.findall(r'^RESULT (\d+) ([0-9a-fA-F]+)$',stdout,re.M)]
                trigger=[x[0] for x in accepted if kind not in (2,8,9) or x[2]]
                delays={b-a for a,b in zip(trigger,cycles)}
                assert len(delays)==1,(kind,delays)
                record['results'].append(dict(kind=kind,seed=seed,outputs=len(actual),accept_to_output_cycles=next(iter(delays)),input_file_sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
        for top,file in [('tb_control','tb_control.sv'),('tb_memory','tb_memory.sv'),('tb_arrays','tb_arrays.sv')]:
            binary=out/(top+'.vvp');run(base+['-s',top,'-o',binary,*rtl,HERE/'sim'/file],log,out)
            stdout=run([args.vvp,'-M',args.ivl_lib,binary],log,out);assert 'PASS' in stdout
            record['results'].append(dict(test=top,stdout=stdout.strip()))
        for kind in KINDS:
            binary=out/f'power_kind{kind}.vvp'
            run(base+[f'-DKIND={kind}','-s','tb_power','-o',binary,*rtl,HERE/'sim/tb_power.sv'],log,out)
            for mode in (0,1,2):
                case=out/f'power_kind{kind}_mode{mode}';case.mkdir()
                stdout=run([args.vvp,'-M',args.ivl_lib,binary,'+CYCLES=128',f'+MODE={mode}','+SEED=7','+VCD=power.vcd'],log,case)
                assert 'PASS power' in stdout
                window=dict(line.split('=',1) for line in (case/'window.txt').read_text().splitlines())
                assert int(window['inputs'])=={0:0,1:128,2:32}[mode]
                record['power_activity'].append(dict(kind=kind,mode=mode,window=window,vcd_sha256=hashlib.sha256((case/'power.vcd').read_bytes()).hexdigest()))
        record['passed']=True
    finally:save()
    print(json.dumps(dict(passed=record['passed'],groups=len(record['results']),outputs=sum(x.get('outputs',0) for x in record['results']),power_scenarios=len(record['power_activity']))))


if __name__=='__main__':main()
