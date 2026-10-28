"""Rejection prefetch oracle and matched proposal/coin trace evaluation."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import subprocess
import sys
from .validate import sha,write,HERE


class RejectionOracle:
    def __init__(self,n,prefetch,levels=2):
        self.n,self.prefetch,self.latency=n,prefetch,math.ceil(math.log2(n)/levels)
        self.reset()
    def reset(self):
        self.state=self.m=self.ref=self.target=self.cap=0
        self.out=self.index=self.done=self.failed=0
        self.proposals=self.accepted=self.consumed=self.multi=self.empty=self.words=self.bits=0
        self.pending=None;self.due=-1;self.pref_zero=False
    def ready(self,x):
        base=self.state==2 and (not self.out or x[-1]) and self.proposals<self.cap
        return bool(base and (not self.prefetch or not self.m or x[8])), bool((base and x[6] and self.m) if self.prefetch else self.state==4)
    def status(self,x):
        p,f=self.ready(x)
        return list(map(int,[self.state,self.m,self.state==0,self.state!=0,self.state==1,p,f,self.out,self.index,
               self.done,self.failed,self.proposals,self.accepted,self.consumed,self.multi,self.empty,self.words,self.bits]))
    def decide(self,index,m):
        old=self.m;self.m=m
        if index is not None:
            self.out=1;self.index=index;self.accepted+=1
            if self.accepted>=self.target:self.state=5
            elif self.proposals>=self.cap:self.failed=1;self.state=5
            else:self.state=2
        elif self.proposals>=self.cap:self.failed=1;self.state=5
        else:self.state=1 if old!=m else 2
    def edge(self,t,x):
        rst,start,ref,target,cap,cfg,pvalid,bitmap,fvalid,fair,ready=x
        if not rst:self.reset();return self.status(x)
        p,f=self.ready(x);old_state=self.state;old_out=self.out;self.done=0
        if self.out and ready:self.out=0;self.consumed+=1
        if f and fvalid:self.words+=1;self.bits+=self.m
        if old_state==0 and start:
            self.ref=ref;self.target=target;self.cap=cap;self.m=0;self.out=0;self.failed=0
            self.proposals=self.accepted=self.consumed=self.multi=self.empty=self.words=self.bits=0;self.pref_zero=False
            if not target or not cap:self.failed=self.done=1
            else:self.state=1
        elif old_state==1 and cfg:self.state=2
        elif old_state==2 and pvalid and p:
            self.proposals+=1;self.pending=[i for i in range(self.n) if i!=self.ref and bitmap>>i&1]
            self.due=t+self.latency;self.pref_zero=(fair&((1<<self.m)-1))==0;self.state=3
        elif old_state==3 and t==self.due:
            if len(self.pending)==1:self.decide(self.pending[0],self.m)
            elif len(self.pending)>1:self.multi+=1;self.decide(None,min(24,self.m+1))
            elif not self.m:self.decide(self.ref,self.m)
            elif not self.prefetch:self.state=4
            elif self.pref_zero:self.decide(self.ref,self.m)
            else:self.empty+=1;self.decide(None,self.m-1)
        elif old_state==4 and fvalid:
            if not (fair&((1<<self.m)-1)):self.decide(self.ref,self.m)
            else:self.empty+=1;self.decide(None,max(0,self.m-1))
        elif old_state==5 and (not old_out or ready):self.state=0;self.done=1
        return self.status(x)


def generate(n,pref,seed,mode,cfg_delay):
    rng=random.Random(seed);o=RejectionOracle(n,pref);stim=[];expected=[];coverage=Counter();cfg_left=cfg_delay
    last_state=0;pending=None;first=None;done_edge=None;outputs=[]
    for t in range(4500):
        stress=mode=='stress';rst=int(t not in ((0,1,997,2501) if stress else (0,1)))
        start=int(o.state==0 and (rng.random()<.7 if stress else t==3))
        target=16 if stress else 128;cap=5 if stress and (t//113)%3==0 else 10000
        if o.state==1 and last_state!=1:cfg_left=cfg_delay
        cfg=int(o.state==1 and cfg_left==0)
        if o.state==1 and cfg_left:cfg_left-=1
        if pending is None:
            i=o.proposals
            if mode=='mixed':
                # Multi -> m+1; single at high m; zero reject -> m-1; zero accept.
                pending=(1<<n)-1 if i%4==0 else 2 if i%4==1 else 0
            else:
                kind=rng.randrange(4);pending=0 if kind==0 else 1<<rng.randrange(n) if kind==1 else (1<<n)-1 if kind==2 else sum(1<<i for i in range(n) if rng.random()<2/n)
        # Proposal-keyed coin: same logical coin for both prefetch policies.
        coin=1 if mode=='mixed' and (o.proposals if o.state==2 else o.proposals-1)%4==2 else 0
        if stress:coin=rng.getrandbits(24)
        x=[rst,start,0,target,cap,cfg,int(not stress or rng.random()<.8),pending,
           int(not stress or rng.random()<.7),coin,int(not stress or (t%103<73 and rng.random()<.65))]
        p,f=o.ready(x);old=o.status(x);last_state=o.state
        if not rst or start:pending=None
        elif p and x[6]:
            pending=None
            if first is None:first=t
        if rst and o.out and x[-1]:outputs.append(o.index)
        y=o.edge(t,x)
        coverage['multi']+=int(y[14]>old[14]);coverage['empty_reject']+=int(y[15]>old[15])
        coverage['stall']+=int(old[7] and not x[-1]);coverage['fair_wait']+=int(f and not x[8])
        coverage['cfg_wait']+=int(old[4] and not cfg);coverage['success']+=int(y[9] and not y[10])
        coverage['cap']+=int(y[9] and y[10]);coverage['reset_busy']+=int(not rst and old[3])
        if y[9] and not stress:done_edge=t
        stim.append(x);expected.append(y)
    return stim,expected,dict(coverage),dict(first=first,done=done_edge,outputs=outputs)


def main():
    p=argparse.ArgumentParser();p.add_argument('--iverilog',type=Path,required=True);p.add_argument('--vvp',type=Path,required=True)
    p.add_argument('--ivl-lib',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);cases=[];paired={}
    sources=[HERE/'rtl/ac_rejection.sv',HERE/'rtl/tb_rejection_v2.sv',HERE.parent/'rtl/nr_singleton_tree.sv',Path(__file__)]
    write(a.output/'SOURCE.json',dict(files={str(f):sha(f) for f in sources}))
    for n in (64,512):
        for pref in (0,1):
            binary=(a.output/f'n{n}_p{pref}.vvp').resolve()
            cmd=[str(a.iverilog),'-B',str(a.ivl_lib),'-g2012','-Wall','-s','tb_rejection_v2',
                 f'-Ptb_rejection_v2.N={n}',f'-Ptb_rejection_v2.PREFETCH_FAIR={pref}','-o',str(binary),
                 str(HERE.parent/'rtl/nr_singleton_tree.sv'),str(HERE/'rtl/ac_rejection.sv'),str(HERE/'rtl/tb_rejection_v2.sv')]
            c=subprocess.run(cmd,capture_output=True,text=True);(a.output/f'compile_n{n}_p{pref}.log').write_bytes((c.stdout+c.stderr).encode())
            if c.returncode:raise RuntimeError(c.stderr)
            configs=[(s,'stress',1) for s in (17,503,1009)]+[(17,'mixed',d) for d in (1,8)]
            for seed,mode,delay in configs:
                name=f'n{n}_p{pref}_{mode}_d{delay}_s{seed}';stim,expected,coverage,timing=generate(n,pref,seed,mode,delay)
                f=(a.output/(name+'.txt')).resolve();f.write_bytes(('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode())
                r=subprocess.run([str(a.vvp),'-M',str(a.ivl_lib),str(binary),'+VECTORS='+str(f)],capture_output=True,text=True)
                log=a.output/(name+'.log');log.write_bytes((r.stdout+r.stderr).encode())
                actual=[list(map(int,line.split()[2:])) for line in r.stdout.splitlines() if line.startswith('C ')]
                if r.returncode or len(actual)!=len(expected):raise RuntimeError('incomplete '+name)
                diff=[dict(cycle=i,expected=x,actual=y) for i,(x,y) in enumerate(zip(expected,actual)) if x!=y]
                if diff:write(a.output/(name+'_FAIL.json'),diff[:20]);raise RuntimeError('oracle '+name)
                if mode=='mixed':
                    assert len(timing['outputs'])==128
                    previous=paired.setdefault((n,delay),timing['outputs']);assert previous==timing['outputs']
                cases.append(dict(case=name,N=n,prefetch=pref,seed=seed,mode=mode,cfg_delay=delay,cycles=len(stim),
                   status='pass',coverage=coverage,proposals=expected[-1][11],accepted=expected[-1][12],
                   fair_words=expected[-1][16],fair_bits=expected[-1][17],first_proposal=timing['first'],done=timing['done'],
                   active_span=timing['done']-timing['first']+1 if timing['done'] is not None else None,
                   input_sha256=sha(f),log_sha256=sha(log),output_sha256=hashlib.sha256(json.dumps(timing['outputs']).encode()).hexdigest()))
    write(a.output/'VALIDATION.json',dict(status='pass',cases=cases,source_sha256=sha(a.output/'SOURCE.json'),
          synthesis='not_run',sta='not_run',power='not_run'))
    print(dict(status='pass',cases=len(cases),cycles=sum(c['cycles'] for c in cases)))


if __name__=='__main__':main()
