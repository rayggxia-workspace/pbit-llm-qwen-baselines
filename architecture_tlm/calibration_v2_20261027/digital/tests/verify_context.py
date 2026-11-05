"""Independent stored-context scoreboard and backpressure/feedback timing test."""
import argparse,collections,hashlib,json,random,subprocess
from pathlib import Path
from verify_digital import arithmetic,ROOT

def make_vectors(seed,slots):
    rng=random.Random(seed);rows=[];phases=[];held=None;index=0
    v0=[0]*7;v1=[0]*7;busy=set();tags=collections.deque()
    for cyc in range(1700):
        rst=int(cyc>=3 and cyc not in [1500,1501]);clear=int(slots==1 and cyc==1450)
        if cyc<700:phase='continuous_round_robin';offered=1;ready=1
        elif cyc<1000:phase='hot_context';offered=1;ready=1
        elif cyc<1400:phase='stall';offered=int(rng.random()<.8);ready=int(cyc%31>=20)
        elif cyc<1480:phase='idle';offered=0;ready=1
        elif cyc<1570:phase='wake_reset';offered=1;ready=1
        else:phase='drain';offered=0;ready=1
        if not rst:held=None
        if held is None and offered and rst:
            ctx=index%slots if phase in ['continuous_round_robin','wake_reset'] else 0 if phase=='hot_context' else rng.randrange(slots)
            # Moderate finite BF16 values keep long dependent sequences informative.
            a=(rng.randrange(2)<<15)|(rng.randrange(121,133)<<7)|rng.getrandbits(7)
            b=(rng.randrange(2)<<15)|(rng.randrange(121,133)<<7)|rng.getrandbits(7)
            held=(ctx,a,b);index+=1
        ctx,a,b=held or (0,0,0);iv=int(held is not None and rst and not clear)
        ready1=not v1[-1] or ready;ready0=not v0[-1] or ready1
        ir=ready0 and ctx not in busy and len(tags)<slots and not clear
        accepted=bool(iv and ir);retired=bool(v1[-1] and ready and rst)
        rows.append((rst,clear,iv,ready,ctx,a,b));phases.append(phase)
        if not rst:v0=[0]*7;v1=[0]*7;busy.clear();tags.clear()
        else:
            if retired:busy.remove(tags.popleft())
            if accepted:busy.add(ctx);tags.append(ctx)
            old=v0[-1]
            if ready0:v0=[int(accepted)]+v0[:-1]
            if ready1:v1=[old]+v1[:-1]
        if accepted:held=None
    return rows,phases

def run(args,seed,slots,out):
    out.mkdir(parents=True,exist_ok=False);rows,phases=make_vectors(seed,slots)
    text=str(len(rows))+'\n'+'\n'.join(f'{r} {cl} {iv} {ready} {ctx} {a:04x} {b:04x}' for r,cl,iv,ready,ctx,a,b in rows)+'\n'
    (out/'vectors.txt').write_text(text,encoding='ascii',newline='\n')
    exe=out/'sim.vvp';cmd=[args.iverilog]+(['-B',str(Path(args.ivl))] if args.ivl else [])+['-g2012','-Wall','-s','tb_context']
    if slots==1:cmd+=['-DSINGLE_CONTEXT']
    cmd+=['-o',str(exe),*[str(p) for p in sorted((ROOT/'rtl').glob('*.sv'))],str(ROOT/'tests/tb_context.sv')]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=120);(out/'compile.log').write_text(p.stdout+p.stderr,encoding='utf-8',newline='\n');assert p.returncode==0,p.stderr
    cmd=[args.vvp]+(['-M',str(Path(args.ivl))] if args.ivl else [])+[str(exe),'+VECTORS='+str(out/'vectors.txt'),'+OUTPUT='+str(out/'trace.txt'),'+PERIOD_NS='+str(args.period_ns)]
    if args.vcd:cmd+=['+VCD='+str(out/'wave.vcd')]
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=180);(out/'simulation.log').write_text(p.stdout+p.stderr,encoding='utf-8',newline='\n');assert p.returncode==0,p.stdout+p.stderr
    acc=[0]*slots;busy=set();q=collections.deque();done=0;blocked=None;lat=[];accept=[];hot=[];window=collections.Counter();incoming=collections.Counter()
    trace=(out/'trace.txt').read_text().splitlines();assert len(trace)==len(rows)
    for line,row,phase in zip(trace,rows,phases):
        cell=line.split();cyc=int(cell[0]);rst,clear,iv,ready,ctx,a,b=row
        assert not any('x' in s.lower() or 'z' in s.lower() for s in cell),line
        rr,ir,ov,orr=map(int,cell[1:5]);oc,y,flags,bmask,occ=map(lambda s:int(s,16),cell[5:])
        assert rr==rst and orr==ready
        if not rst:acc=[0]*slots;busy.clear();q.clear();blocked=None;continue
        if slots==16:assert bmask==sum(1<<c for c in busy) and occ==len(q),(line,busy,list(q))
        if blocked is not None:assert (ov,oc,y,flags)==blocked
        blocked=(ov,oc,y,flags) if ov and not ready else None
        if clear:assert not busy;acc=[0]*slots
        # Rejecting a still-busy context is mandatory even if it retires this edge.
        if iv and ctx in busy:assert not ir
        if ov and ready:
            ec,ey,ef,accepted=q.popleft();assert (oc,y,flags)==(ec,ey,ef),(line,(ec,hex(ey),ef))
            acc[oc]=y;busy.remove(oc);lat.append(cyc-accepted);done+=1;window[phase]+=1
        if iv and ir:
            assert ctx not in busy
            product,pf=arithmetic('mul',a<<16,b<<16);ey,ef=arithmetic('add',product,acc[ctx]);q.append((ctx,ey,pf|ef,cyc));busy.add(ctx);incoming[phase]+=1
            if phase=='continuous_round_robin':accept.append(cyc)
            if phase=='hot_context':hot.append(cyc)
    assert not q
    intervals=[b-a for a,b in zip(accept,accept[1:])];hot_ii=[b-a for a,b in zip(hot,hot[1:])]
    assert min(lat)==14 and min(intervals)==(1 if slots==16 else 15)
    assert min(hot_ii)==15,(slots,hot_ii)
    windows=[]
    for phase in dict.fromkeys(phases):
        ids=[i for i,p in enumerate(phases) if p==phase]
        windows.append(dict(name=phase,start_cycle=min(ids),end_cycle=max(ids)+1,start_ns=(min(ids)+1)*args.period_ns,end_ns=(max(ids)+2)*args.period_ns,frames=window[phase],accepted_samples=incoming[phase]))
    result=dict(status='passed',top='dig_bf16_context16' if slots==16 else 'dig_bf16_accum',seed=seed,contexts=slots,
        completed_transactions=done,minimum_latency_clocks=min(lat),independent_context_II=min(intervals),dependent_context_II=min(hot_ii),input_sha256=hashlib.sha256(text.encode()).hexdigest(),windows=windows,rtl_only=True)
    (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--iverilog',default='iverilog');p.add_argument('--vvp',default='vvp');p.add_argument('--ivl');p.add_argument('--period-ns',type=float,default=10.0);p.add_argument('--vcd',action='store_true');a=p.parse_args()
    if a.output.exists():raise SystemExit('Output exists')
    a.output.mkdir(parents=True);results=[]
    for slots in [1,16]:
        for seed in [17,31,193]:
            print('RUN context',slots,seed,flush=True);results.append(run(a,seed,slots,a.output/(str(slots)+'_'+str(seed))))
    (a.output/'SUMMARY.json').write_text(json.dumps(dict(status='passed',tests=results,technology_validation=False),indent=2)+'\n',encoding='utf-8',newline='\n');print('PASS',len(results),flush=True)
if __name__=='__main__':main()
