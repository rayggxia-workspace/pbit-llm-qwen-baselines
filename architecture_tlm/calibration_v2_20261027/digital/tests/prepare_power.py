"""Generate normal-valued synthetic power fixtures; never claim real LLM activity."""
import argparse,collections,hashlib,json,random
from pathlib import Path
from verify_digital import CASES,vectors,oracle,arithmetic
from verify_context import make_vectors

TOPS=list(CASES)+['dig_bf16_accum','dig_bf16_context16']

def normal_word(rng,center):
    return (rng.randrange(2)<<31)|(rng.randrange(center-4,center+5)<<23)|rng.getrandbits(23)

def prepare(top,mode,seed,out,period_ns=10.):
    if out.exists():raise ValueError('Fixture directory already exists')
    out.mkdir(parents=True)
    ctxmode=top in ['dig_bf16_accum','dig_bf16_context16'];slots=16 if top=='dig_bf16_context16' else 1
    if ctxmode:rows,phases=make_vectors(seed,slots)
    else:
        rows,phases=vectors(top,seed)
        rng=random.Random(seed+10000);cache={};normal=[]
        for r,iv,ready,a,b,c in rows:
            key=(a,b,c)
            if key not in cache:
                aa=bb=cc=0
                for lane in range(CASES[top][1]):
                    x=normal_word(rng,127);w=normal_word(rng,126);z=normal_word(rng,127)
                    width=16 if 'bf16' in top and top!='dig_fp32_to_bf16' else 32
                    if width==16:x>>=16;w>>=16
                    aa|=x<<(width*lane);bb|=w<<(width*lane);cc|=z<<(32*lane)
                cache[key]=(aa,bb,cc)
            aa,bb,cc=cache[key];normal.append((r,iv,ready,aa,bb,cc))
        rows=normal
    mac=top in ['dig_bf16_mac','dig_bf16_mac8'] or ctxmode
    lat=14 if mac else CASES[top][0]
    v0=[0]*(7 if mac else lat);v1=[0]*7;q=collections.deque();acc=[0]*slots;busy=set();expected=[];accepted=[];retired=[]
    for cyc,row in enumerate(rows):
        if ctxmode:r,cl,iv,ready,ctx,a,b=row;c=acc[ctx]
        else:r,iv,ready,a,b,c=row;cl=0;ctx=0
        r1=(not v1[-1]) or ready;r0=(not v0[-1]) or (r1 if mac else ready)
        ir=bool(r and r0 and (not ctxmode or (ctx not in busy and len(q)<slots and not cl)))
        ov=bool(r and (v1[-1] if mac else v0[-1]));item=dict(cycle=cyc,in_ready=int(ir),out_valid=int(ov))
        if ov:
            ct,yy,ff=q[0];item.update(y=hex(yy),status=hex(ff),context=ct)
        expected.append(item)
        if not r:v0=[0]*len(v0);v1=[0]*7;q.clear();busy.clear();acc=[0]*slots;continue
        if cl:assert not busy;acc=[0]*slots
        if ov and ready:
            ct,yy,ff=q.popleft();retired.append(cyc)
            if ctxmode:busy.remove(ct);acc[ct]=yy
        fire=bool(iv and ir)
        if fire:
            if ctxmode:
                p,pf=arithmetic('mul',a<<16,b<<16);yy,ff=arithmetic('add',p,acc[ctx]);ff|=pf;busy.add(ctx)
            else:yy,ff=oracle(top,a,b,c)
            q.append((ctx,yy,ff));accepted.append(cyc)
        old=v0[-1]
        if r0:v0=[int(fire)]+v0[:-1]
        if mac and r1:v1=[old]+v1[:-1]
    assert not q
    windows={'continuous':(64,640),'idle':((1620,1690) if ctxmode else (1400,1500)),
             'stall':((1050,1350) if ctxmode else (850,950))}
    lo,hi=windows[mode]
    if ctxmode:text=str(len(rows))+'\n'+'\n'.join(f'{r} {cl} {iv} {ready} {ct} {a:x} {b:x}' for r,cl,iv,ready,ct,a,b in rows)+'\n'
    else:text=str(len(rows))+'\n'+'\n'.join(f'{r} {iv} {ready} {a:x} {b:x}'+(f' {c:x}' if mac else '') for r,iv,ready,a,b,c in rows)+'\n'
    (out/'vectors.txt').write_text(text,encoding='ascii',newline='\n')
    (out/'expected.json').write_text(json.dumps(expected,separators=(',',':'))+'\n',encoding='utf-8',newline='\n')
    cfg=dict(top=top,mode=mode,seed=seed,period_ns=period_ns,
        activity='Synthetic signed normal FP32/BF16 operands. Not a measured LLM trace.',
        vector_sha256=hashlib.sha256(text.encode()).hexdigest(),
        expected_sha256=hashlib.sha256((out/'expected.json').read_bytes()).hexdigest(),
        start_cycle=lo,end_cycle=hi,start_ns=(lo+1)*period_ns,end_ns=(hi+1)*period_ns,
        frames=sum(lo<=x<hi for x in retired),accepted_samples=sum(lo<=x<hi for x in accepted),
        primitive_operations_per_transaction=(16 if top=='dig_bf16_mac8' else 2 if mac else 1),
        macs_per_transaction=(8 if top=='dig_bf16_mac8' else 1 if mac else 0),
        bench='tb_context' if ctxmode else 'tb_mac' if mac else 'tb_digital',
        defines=(['SINGLE_CONTEXT'] if slots==1 else []) if ctxmode else ([f'MAC_TOP={top}',f'MAC_LANES={CASES[top][1]}'] if mac else [f'DIG_TOP={top}']),
        plusargs=[f'+VECTORS={{CASE_DIR}}/vectors.txt',f'+OUTPUT={{RUN_DIR}}/trace.txt',f'+PERIOD_NS={period_ns}',f'+WSTART_CYCLE={lo}',f'+WEND_CYCLE={hi}'])
    (out/'FIXTURE.json').write_text(json.dumps(cfg,indent=2)+'\n',encoding='utf-8',newline='\n');return cfg

def check(fixture,trace):
    cfg=json.loads((fixture/'FIXTURE.json').read_text());expected=json.loads((fixture/'expected.json').read_text());lines=trace.read_text().splitlines()
    assert len(lines)==len(expected)
    ctx=cfg['bench']=='tb_context'
    for line,ref in zip(lines,expected):
        v=line.split();cyc=int(v[0]);assert cyc==ref['cycle']
        assert not any('x' in x.lower() or 'z' in x.lower() for x in v),line
        assert int(v[2])==ref['in_ready'] and int(v[3])==ref['out_valid'],(line,ref)
        if ref['out_valid']:
            off=1 if ctx else 0
            assert int(v[5+off],16)==int(ref['y'],16) and int(v[6+off],16)==int(ref['status'],16),(line,ref)
            if ctx:assert int(v[5],16)==ref['context']
    return dict(status='passed',cycles=len(lines),top=cfg['top'],vector_sha256=cfg['vector_sha256'])

def main():
    p=argparse.ArgumentParser();p.add_argument('--top',choices=TOPS);p.add_argument('--mode',choices=['continuous','idle','stall'],default='continuous');p.add_argument('--seed',type=int,default=17);p.add_argument('--output',type=Path);p.add_argument('--period-ns',type=float,default=10.);p.add_argument('--check-fixture',type=Path);p.add_argument('--trace',type=Path);a=p.parse_args()
    result=check(a.check_fixture,a.trace) if a.check_fixture else prepare(a.top,a.mode,a.seed,a.output,a.period_ns)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
