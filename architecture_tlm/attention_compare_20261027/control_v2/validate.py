"""Parameterized RTL/flat-list oracle replay and measured cycle comparison."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import zipfile
from .oracle import WinnerOracle

HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())


def generate(n,prep,stream,seed,mode,cycles=3200,early=0,rankcap=8):
    rng=random.Random(seed);frame_rng=random.Random(seed+101);word_rng=random.Random(seed+202)
    model=WinnerOracle(n,prep,stream,rankcap,early)
    stim=[];expected=[];pre=[];coverage=Counter();pending=None
    mask=(1<<n)-1;initial=0;samples=128;burn=16;frames=[];outputs=[];commits=[]
    frame_pvalid=fair_pvalid=0;word=word_rng.getrandbits((n-1).bit_length());outvalues=[];accepted_bits=[]
    for t in range(cycles):
        stress=mode=='stress'
        rst=int(t not in ((0,1,991,1993) if stress else (0,1)))
        start=int(not model.active and ((rng.random()<.75) if stress else t==3))
        if start:
            mask=(1<<n)-1 if not stress else rng.getrandbits(n)|1
            initial=0;samples=128 if not stress else rng.choice((1,7,32,128));burn=16 if not stress else rng.choice((0,3,16))
        if pending is None:
            if mode=='all':pending=(1<<n)-1
            elif mode=='empty':pending=0
            elif mode=='single':pending=1<<frame_rng.randrange(n)
            elif mode=='three':pending=sum(1<<i for i in frame_rng.sample(range(n),3))
            elif mode=='cap':pending=11
            else:
                kind=(t//79)%5
                pending=0 if kind==0 else 1<<frame_rng.randrange(n) if kind==1 else (1<<n)-1 if kind==2 else frame_rng.getrandbits(n) if kind==3 else sum(1<<i for i in range(n) if frame_rng.random()<3/n)
        if not frame_pvalid:frame_pvalid=int(not stress or rng.random()<.8)
        if not fair_pvalid:fair_pvalid=int(not stress or rng.random()<.7)
        out_ready=int(not stress or ((t%113)<79 and rng.random()<.7))
        x=[rst,start,mask,initial,samples,burn,int(not stress or rng.random()<.65),
           frame_pvalid,pending,fair_pvalid,word,out_ready]
        if stress and 1450<=t<1480:x[10]=(1<<(n-1).bit_length())-1
        if mode=='cap':x[3]=n-1;x[10]=(1<<(n-1).bit_length())-1
        ports=model.ports(x);old=model.status();logic=model.logic(x)
        if not rst:pending=None;frame_pvalid=fair_pvalid=0
        elif x[7] and ports[3]:
            accepted_bits.append(pending);pending=None;frame_pvalid=0;frames.append(t)
        if rst and ports[4] and x[9]:fair_pvalid=0;word=word_rng.getrandbits((n-1).bit_length())
        if rst and ports[5] and out_ready:outputs.append(t);outvalues.append(ports[6])
        status=model.edge(x)
        if status[7]>old[7]:commits.append(t)
        coverage['rank_retry']+=int(status[-1]>old[-1])
        coverage['output_stall']+=int(ports[5] and not out_ready)
        coverage['source_wait']+=int(ports[3] and not x[7])
        coverage['fair_wait']+=int(ports[4] and not x[9])
        coverage['cfg_wait']+=int(ports[2] and not x[6])
        coverage['success']+=int(status[3] and not status[4])
        coverage['cap_failure']+=int(status[3] and status[4])
        coverage['reset_busy']+=int(not rst and old[0])
        coverage['hold']+=max(0,status[9]-old[9]);coverage['switch']+=max(0,status[10]-old[10])
        stim.append(x);pre.append(ports);expected.append(status)
    return stim,pre,expected,dict(coverage),dict(frame_edges=frames,output_edges=outputs,commit_edges=commits,
           output_sha256=hashlib.sha256(json.dumps(outvalues).encode()).hexdigest(),
           frame_sha256=hashlib.sha256(b''.join(v.to_bytes((n+7)//8,'little') for v in accepted_bits)).hexdigest())


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--iverilog',type=Path,required=True);p.add_argument('--vvp',type=Path,required=True)
    p.add_argument('--ivl-lib',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--vcd',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    sources=[HERE/'rtl'/f for f in ('ac_scan.sv','ac_winner.sv','tb_winner.sv')]+[HERE/'oracle.py',Path(__file__)]
    write(a.output/'SOURCE.json',dict(files={str(f.relative_to(HERE)):sha(f) for f in sources},
          parent_commit='0fc3969004433056e3074c0bc37a8626df3aabb0',binding='exact working-source bytes'))
    with zipfile.ZipFile(a.output/'SOURCE_FILES.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in sources:z.write(f,str(f.relative_to(HERE)))
    configs=[(4,2,1,1,0),(4,2,2,1,1),(64,8,1,1,0),(64,8,2,1,0),(64,16,2,0,0),
             (512,8,2,1,0),(512,16,1,1,0),(512,16,2,1,0),(512,16,2,0,0),
             (512,32,2,1,0),(512,16,2,1,1)]
    cases=[];paired={}
    configs=[(*c,0) for c in configs]+[(64,8,2,1,0,1),(512,16,2,1,0,1)]
    for n,group,prep,stream,onehot,early in configs:
        name=f'n{n}_g{group}_p{prep}_s{stream}_o{onehot}_e{early}'
        binary=(a.output/(name+'.vvp')).resolve()
        cmd=[str(a.iverilog),'-B',str(a.ivl_lib),'-g2012','-Wall','-s','tb_winner',
            *[f'-Ptb_winner.{k}={v}' for k,v in dict(N=n,GROUP=group,PREP_STAGES=prep,STREAM=stream,WINNER_ONEHOT=onehot,EARLY_HOLD=early).items()],
            '-o',str(binary),str(HERE/'rtl/ac_scan.sv'),str(HERE/'rtl/ac_winner.sv'),str(HERE/'rtl/tb_winner.sv')]
        compiled=subprocess.run(cmd,capture_output=True,text=True)
        (a.output/(name+'_compile.log')).write_bytes((compiled.stdout+compiled.stderr).encode())
        if compiled.returncode:raise RuntimeError(compiled.stderr)
        pairs=[(seed,'stress') for seed in (17,503,1009)]+[(17,m) for m in ('all','empty','single','three','cap')]
        for seed,mode in pairs:
            key=f'{name}_{mode}_{seed}';stim,pre,expected,coverage,timing=generate(n,prep,stream,seed,mode,early=early)
            vectors=(a.output/(key+'.txt')).resolve()
            vectors.write_bytes(('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode())
            cmd=[str(a.vvp),'-M',str(a.ivl_lib),str(binary),'+VECTORS='+str(vectors)]
            if a.vcd and seed==17 and mode=='three':cmd+=['+VCD='+str((a.output/(key+'.vcd')).resolve())]
            run=subprocess.run(cmd,capture_output=True,text=True)
            log=a.output/(key+'.log');log.write_bytes((run.stdout+run.stderr).encode())
            actual_p=[list(map(int,line.split()[2:])) for line in run.stdout.splitlines() if line.startswith('P ')]
            actual_c=[list(map(int,line.split()[2:])) for line in run.stdout.splitlines() if line.startswith('C ')]
            if run.returncode or len(actual_c)!=len(expected):raise RuntimeError('incomplete '+key)
            diff=[dict(cycle=i,expected_pre=pp,actual_pre=ap,expected_post=cc,actual_post=ac)
                  for i,(pp,ap,cc,ac) in enumerate(zip(pre,actual_p,expected,actual_c)) if pp!=ap or cc!=ac]
            if diff:write(a.output/(key+'_FAIL.json'),diff[:20]);raise RuntimeError('oracle mismatch '+key)
            required=('output_stall','fair_wait','cfg_wait','success','reset_busy','hold','switch')+ (('source_wait',) if stream else ())
            if mode=='stress' and not all(coverage.get(k) for k in required):
                raise RuntimeError('missing coverage '+key+' '+str(coverage))
            if mode=='all':
                expected_gap=1 if stream else prep+2
                assert timing['frame_edges'][1]-timing['frame_edges'][0]==expected_gap
                assert timing['commit_edges'][0]-timing['frame_edges'][0]==prep+1
                assert timing['output_edges'][-1]-timing['frame_edges'][0]==(144-1)*expected_gap+prep+2
            if mode=='cap':assert coverage['cap_failure']>0
            if mode in ('all','empty','single','three'):
                pairkey=(n,int(early or not stream),mode)
                pair=(timing['frame_sha256'],timing['output_sha256'])
                assert paired.setdefault(pairkey,pair)==pair,'paired frame/output mismatch'
            summary=dict(case=key,N=n,group=group,prep=prep,stream=stream,onehot=onehot,early=early,seed=seed,mode=mode,
                 cycles=len(expected),status='pass',coverage=coverage,input_sha256=sha(vectors),log_sha256=sha(log),
                 issued=expected[-1][6],committed=expected[-1][7],consumed=expected[-1][8],
                 fair_words=expected[-1][11],fair_bits=expected[-1][12],rank_retries=expected[-1][13],
                 first_frame=timing['frame_edges'][0] if timing['frame_edges'] else None,
                 frame_sha256=timing['frame_sha256'],output_sha256=timing['output_sha256'],
                 last_output=timing['output_edges'][-1] if timing['output_edges'] else None,
                 active_span=(timing['output_edges'][-1]-timing['frame_edges'][0]+1) if timing['output_edges'] else None)
            cases.append(summary)
    write(a.output/'VALIDATION.json',dict(status='pass',cases=cases,clock_MHz=100,
         tools={str(t):sha(t) for t in (a.iverilog,a.vvp)},python=sys.version,
         source_sha256=sha(a.output/'SOURCE.json'),synthesis='not_run',sta='not_run',power='not_run'))
    print(json.dumps(dict(status='pass',cases=len(cases),cycles=sum(c['cycles'] for c in cases))))


if __name__=='__main__':main()
