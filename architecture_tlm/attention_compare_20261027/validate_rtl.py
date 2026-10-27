"""External-bit control replay against an independent Python clock oracle."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def write(p,obj):
    p.write_bytes((json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


class Oracle:
    """Queue a captured bitmap, evaluate after tree latency, independent decode."""
    def __init__(self,n):
        self.n=n;self.latency=math.ceil(math.log2(n)/2);self.reset()

    def reset(self):
        self.state=0;self.m=0;self.ref=0;self.target=0;self.cap=0
        self.out=0;self.index=0;self.done=0;self.failed=0
        self.proposals=0;self.accepted=0;self.consumed=0;self.multi=0;self.empty=0
        self.pending=None;self.due=-1

    def ports(self):
        return [self.state,self.m,int(self.state==0),int(self.state!=0),int(self.state==1),
                int(self.state==2 and not self.out and self.proposals<self.cap),int(self.state==4),
                self.out,self.index,self.done,self.failed,self.proposals,self.accepted,self.consumed,self.multi,self.empty]

    def edge(self,cycle,x):
        rst,start,ref,target,cap,cfg,pvalid,bits,fvalid,fair,ready=x
        if not rst:self.reset();return self.ports()
        state,old_out=self.state,self.out
        self.done=0
        if self.out and ready:self.out=0;self.consumed+=1
        if state==0 and start:
            self.ref=ref;self.target=target;self.cap=cap;self.m=0;self.out=0;self.failed=0
            self.proposals=self.accepted=self.consumed=self.multi=self.empty=0
            if target==0 or cap==0 or ref>=self.n:self.failed=1;self.done=1
            else:self.state=1
        elif state==1 and cfg:self.state=2
        elif state==2 and pvalid and (not old_out or ready) and self.proposals<self.cap:
            self.proposals+=1;self.pending=[i for i in range(self.n) if i!=self.ref and bits>>i&1]
            self.due=cycle+self.latency;self.state=3
        elif state==3 and cycle==self.due:
            active=self.pending
            if len(active)==1:self.resolve(active[0],self.m)
            elif len(active)>1:self.multi+=1;self.resolve(None,min(24,self.m+1))
            elif self.m==0:self.resolve(self.ref,self.m)
            else:self.state=4
        elif state==4 and fvalid:
            if fair & ((1<<self.m)-1):
                self.empty+=1;self.resolve(None,max(0,self.m-1))
            else:self.resolve(self.ref,self.m)
        elif state==5 and (not old_out or ready):self.state=0;self.done=1
        # proposal_ready is combinational and can consume an old output on
        # the next edge; expose ready using this cycle's out_ready stimulus.
        values=self.ports()
        values[5]=int(self.state==2 and (not self.out or ready) and self.proposals<self.cap)
        return values

    def resolve(self,index,new_m):
        old_m=self.m;self.m=new_m
        if index is not None:
            self.out=1;self.index=index;self.accepted+=1
            if self.accepted>=self.target:self.state=5
            elif self.proposals>=self.cap:self.failed=1;self.state=5
            else:self.state=2
        elif self.proposals>=self.cap:self.failed=1;self.state=5
        else:self.state=1 if new_m!=old_m else 2


def vectors(n,seed,cycles):
    rng=random.Random(seed);o=Oracle(n);stim=[];expected=[];coverage=Counter()
    for t in range(cycles):
        # Explicit reset while a proposal/config/output may be outstanding.
        rst=int(t not in (0,1,777,1555))
        start=int(o.state==0 and rng.random()<.8)
        target=4;cap=1 if (t//100)%3==0 else 100
        if t%257==0:target=0
        ref=rng.randrange(n)
        kind=(o.proposals//3)%4
        if kind==0:bits=(1<<n)-1
        elif kind==1:bits=0
        elif kind==2:bits=1<<rng.randrange(n)
        else:bits=sum(1<<i for i in range(n) if rng.random()<2/n)
        fair=0 if rng.random()<.45 else rng.getrandbits(24)
        x=[rst,start,ref,target,cap,int(rng.random()<.65),int(rng.random()<.8),bits,
           int(rng.random()<.7),fair,int((t%101)<70 and rng.random()<.6)]
        if 2<=t<650:
            # Force m to its upper bound, hold there, then exercise exact
            # low-m-bit zero correction while walking back to m=0.
            x=[rst,start,ref,4,200,1,1,(1<<n)-1 if t<350 else 0,1,1,1]
        before=o.ports();y=o.edge(t,x)
        for name,cond in [('config_wait',before[4] and not x[5]),('output_stall',before[7] and not x[10]),
                          ('empty_reject',y[-1]>before[-1]),('multi_reject',y[-2]>before[-2]),
                          ('cap_failure',y[10] and y[9]),('success',not y[10] and y[9]),
                          ('reset_busy',not rst and before[3]),('fair_wait',before[6] and not x[8])]:
            coverage[name]+=int(bool(cond))
        coverage['upper_shift_clamp']+=int(before[1]==24 and y[1]==24 and y[-2]>before[-2])
        coverage['reference_only_ignored']+=int(o.state==3 and bits==(1<<o.ref))
        stim.append(x);expected.append(y)
    return stim,expected,dict(coverage)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--iverilog',type=Path,required=True);p.add_argument('--vvp',type=Path,required=True)
    p.add_argument('--ivl-lib',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    rtl=HERE/'rtl';sources=list(rtl.glob('*.sv'))+[Path(__file__)]
    write(a.output/'SOURCE.json',dict(files={str(f.relative_to(HERE)):sha(f) for f in sources},
                                     binding='exact working source bytes; not HEAD alone'))
    cases=[]
    for n in (16,64,512):
        binary=(a.output/f'n{n}.vvp').resolve()
        cmd=[str(a.iverilog),'-B',str(a.ivl_lib),'-g2012','-Wall','-s','tb_rejection',
             f'-Ptb_rejection.N={n}','-o',str(binary),str(rtl/'nr_singleton_tree.sv'),
             str(rtl/'attention_rejection_control.sv'),str(rtl/'tb_rejection.sv')]
        c=subprocess.run(cmd,capture_output=True,text=True)
        (a.output/f'compile_n{n}.log').write_bytes((c.stdout+c.stderr).encode())
        if c.returncode:raise RuntimeError(c.stderr)
        for seed in (17,503,1009):
            stim,expected,coverage=vectors(n,seed,2500)
            name=f'n{n}_s{seed}';path=(a.output/(name+'.txt')).resolve()
            path.write_bytes(('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode())
            command=[str(a.vvp),'-M',str(a.ivl_lib),str(binary),'+VECTORS='+str(path)]
            r=subprocess.run(command,capture_output=True,text=True)
            log=a.output/(name+'.log');log.write_bytes((r.stdout+r.stderr).encode())
            actual=[list(map(int,line.split()[2:])) for line in r.stdout.splitlines() if line.startswith('C ')]
            if r.returncode or len(actual)!=len(expected):raise RuntimeError(f'{name}: incomplete simulator output; see {log}')
            differences=[dict(cycle=i,expected=x,actual=y) for i,(x,y) in enumerate(zip(expected,actual)) if x!=y]
            if differences:
                write(a.output/(name+'_FAIL.json'),differences[:20]);raise RuntimeError(f'{name}: oracle mismatch')
            required=('config_wait','output_stall','empty_reject','multi_reject','cap_failure','success',
                      'reset_busy','fair_wait','upper_shift_clamp')
            if not all(coverage[k] for k in required):raise RuntimeError(f'coverage missing: {coverage}')
            cases.append(dict(N=n,seed=seed,cycles=len(expected),functional='pass',coverage=coverage,
                              stimuli_sha256=sha(path),log_sha256=sha(log),tree_stages=math.ceil(math.log2(n)/2)))
    result=dict(status='pass',cases=cases,tool_sha256={str(t):sha(t) for t in (a.iverilog,a.vvp)},
                python=sys.version,clock_MHz=100,source_sha256=sha(a.output/'SOURCE.json'),
                synthesis='not_run',sta='not_run',power='not_run',postlayout='not_run',
                contract='external independent proposal/fair bits; cfg ack after settling; no RNG/LUT/QK/V in this RTL')
    write(a.output/'VALIDATION.json',result)
    print(json.dumps(dict(status='pass',cases=len(cases),cycles=sum(c['cycles'] for c in cases))))


if __name__=='__main__':main()
