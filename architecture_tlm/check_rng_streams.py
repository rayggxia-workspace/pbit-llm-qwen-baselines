"""Small reproducible functional diagnostic; no claim of entropy certification."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from rng_reference import FunctionalRng


def correlation(a,b):
    ma=sum(a)/len(a);mb=sum(b)/len(b)
    va=sum((x-ma)**2 for x in a);vb=sum((x-mb)**2 for x in b)
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(va*vb) if va*vb else None


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--samples',type=int,default=1024)
    p.add_argument('--seed',default='ffn-hierarchy-v1-demo')
    p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'results/rng_hierarchy_v1/streams.json')
    a=p.parse_args()
    if a.samples<2:p.error('--samples must be >=2')
    r=FunctionalRng(hashlib.sha256(a.seed.encode()).digest())
    weights=[[64]*64 for _ in range(4)]
    activations=[2048]*64
    w0=[];w1=[];x0=[];xy=[];dot=[];updates=cycles=rejects=0
    for _ in range(a.samples):
        x=r.input_bits(activations)
        w,d=r.weight_bits(0,weights)
        w0.append(w[0][0]);w1.append(w[1][0]);x0.append(x[0]);xy.append(x[0]*w[0][0])
        dot.append(sum(xi*wi for xi,wi in zip(x,w[0])))
        updates+=d['core_updates'];cycles+=d['cycles'];rejects+=d['rejected_bytes']
    result=dict(scope='functional 64-input, 4-output subarray; deterministic seed, not physical entropy or PPL',
        samples=a.samples,seed_label=a.seed,
        expected_weight_p=64/127,observed_weight_p=sum(w0)/a.samples,
        expected_input_p=.5,observed_input_p=sum(x0)/a.samples,
        expected_AND_p=.5*64/127,observed_AND_p=sum(xy)/a.samples,
        expected_unsigned_dot=64*.5*64/127,observed_unsigned_dot=sum(dot)/a.samples,
        input_weight_correlation=correlation(x0,w0),weight_cross_column_correlation=correlation(w0,w1),
        weight_lag1=correlation(w0[:-1],w0[1:]),
        actual_array_cycles=cycles,actual_core_updates=updates,rejected_bytes=rejects,
        uncertainty='finite-sample diagnostics only; no pass/fail entropy or IID claim')
    result['source_hashes']={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                             for name in ('rng_reference.py','check_rng_streams.py')}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
