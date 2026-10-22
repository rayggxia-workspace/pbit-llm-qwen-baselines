"""Small three-seed statistical diagnostics, not NIST/quality/independence certification."""
import argparse
import json
import random
from pathlib import Path
from .backends import PROFILES, generate

def correlation(a,b):
    n=len(a);ma=sum(a)/n;mb=sum(b)/n
    va=sum((x-ma)**2 for x in a);vb=sum((x-mb)**2 for x in b)
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/(va*vb)**0.5 if va*vb else None

def run(frames=4096):
    rows=[]
    for kind,c in PROFILES.items():
        for seed in (17,503,1009):
            state=random.Random(seed).getrandbits(c['state_bits']) or 1
            for _ in range(c['warmup']):_,state=generate(kind,state)
            a=[];b=[];hist=[0]*256
            for _ in range(frames):
                words,state=generate(kind,state)
                a.append(int(words[0]<128));b.append(int(words[-1]<128));hist[words[0]]+=1
            ratios={}
            p=sum(a)/len(a)
            for T in (32,128):
                means=[sum(a[i:i+T])/T for i in range(0,len(a)-T+1,T)]
                avg=sum(means)/len(means)
                variance=sum((x-avg)**2 for x in means)/(len(means)-1)
                ratios[str(T)]=variance/(p*(1-p)/T) if 0<p<1 else None
            rows.append(dict(kind=kind,fixture_seed=seed,frames=frames,p1=p,
                temporal_rho1=correlation(a[:-1],a[1:]),
                first_last_lane_rho=correlation(a,b) if c['lanes']>1 else None,
                T_variance_over_iid=ratios,first_word_histogram=hist,
                scope='synthetic q=128; first/last lanes only, not all lags/adaptive conditions'))
    return dict(rows=rows,conclusion='diagnostic only; no quality acceptance or IID claim')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(run(),indent=2)+'\n',encoding='utf-8')
