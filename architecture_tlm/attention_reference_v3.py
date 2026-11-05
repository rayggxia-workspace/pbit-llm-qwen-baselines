"""Numerical traces for transaction selection. Standard library, no model inference.

Real trace schema: {provenance: {...}, rows: [{token,layer,head,logits:[...]}]}.
Logits are post-RoPE QK/sqrt(d), before softmax, for one causal decode query.
An offline dense-logit trace is an oracle for validating the sparse path, NOT
an extra dense QK operation in the simulated sparse accelerator.
"""
import bisect
import hashlib
import json
import math
import random
from pathlib import Path


def softmax(x):
    m=max(x); p=[math.exp(v-m) for v in x]; s=sum(p)
    return [v/s for v in p]


def cdf(p):
    out=[]; s=0.
    for v in p:s+=v;out.append(s)
    out[-1]=1.
    return out


def categorical(p, samples, rng):
    c=cdf(p)
    return [min(len(c)-1,bisect.bisect_right(c,rng.random())) for _ in range(samples)]


def selector(logits, bias, temperature, rng, block=64):
    """Matches max4 score + free-block mean/std + calibrated sigmoid.

    Linearity gives q dot mean(K) = mean(q dot K); this reconstructs proxy
    scores from offline logits without requiring the K tensor in the trace.
    """
    if temperature<=0:raise ValueError('selector temperature must be positive')
    scores=[]
    for start in range(0,len(logits),block):
        sub=[logits[t:min(t+block//4,len(logits))] for t in range(start,min(start+block,len(logits)),block//4)]
        scores.append(max(sum(s)/len(s) for s in sub))
    n=len(scores); forced={0,n-1,max(0,n-2)}
    free=[scores[i] for i in range(n) if i not in forced]
    mu=sum(free)/max(1,len(free))
    std=max(.01,math.sqrt(sum((v-mu)**2 for v in free)/max(1,len(free))))
    probabilities=[]; selected=[]
    for i,s in enumerate(scores):
        a=max(-700.,min(700.,((s-mu)/std+bias)/temperature))
        p=1. if i in forced else 1/(1+math.exp(-a))
        probabilities.append(p)
        if rng.random()<p:selected.append(i)
    indices=[i for b in selected for i in range(b*block,min((b+1)*block,len(logits)))]
    return indices,dict(block_scores=scores,block_probabilities=probabilities,selected_blocks=selected)


def ising_random_scan(logits, samples, burn, spacing, rng):
    """Exact event compression of DISCRETE serial random-scan heat-bath.

    Reference logit is the maximum. Zero active bits represents that category;
    each other bit represents its own category. Hard inhibition allows at most
    one active bit. Every microstep chooses a site uniformly and heat-bath
    updates it. Geometric skipping eliminates null updates in the Python
    reference ONLY; hardware is charged for EVERY attempted microstep.
    This has the softmax stationary law, but its finite-time chain is NOT the
    previous continuous-time torch sampler and claims no transferred PPL.
    """
    if samples<1 or burn<0 or spacing<1:raise ValueError('invalid Ising horizon')
    ref=max(range(len(logits)),key=logits.__getitem__)
    sites=[i for i in range(len(logits)) if i!=ref]; n=len(sites)
    if not n:return [ref]*samples,dict(attempts=0,flips=0,sites=0)
    birth=[1/(1+math.exp(min(700.,logits[ref]-logits[i]))) for i in sites]
    total=sum(birth); birth_cdf=cdf([b/total for b in birth]) if total else []
    active=-1; clock=0; flips=0; out=[]
    def transition_time():
        probability=(total if active<0 else 1-birth[active])/n
        if probability<=0:return math.inf
        if probability>=1:return clock+1
        return clock+1+int(math.log1p(-rng.random())/math.log1p(-probability))
    next_event=transition_time()
    for sample in range(samples):
        t=n*(burn+spacing*(sample+1))
        while next_event<=t:
            clock=next_event
            active=min(n-1,bisect.bisect_right(birth_cdf,rng.random())) if active<0 else -1
            flips+=1;next_event=transition_time()
        out.append(ref if active<0 else sites[active])
    return out,dict(attempts=n*(burn+spacing*samples),flips=flips,sites=n)


class TraceSource:
    def __init__(self,cfg,shape):
        self.cfg=cfg;self.shape=shape;self.rows={};self.calibration=None
        self.provenance=dict(kind='SYNTHETIC_GAUSSIAN_LOGITS',model_ppl_validated=False,
            warning='routing/memory scenario only; NOT measured Qwen attention or PPL')
        if cfg.get('trace_file'):
            path=Path(cfg['trace_file']); data=json.loads(path.read_text(encoding='utf-8'))
            for r in data['rows']:
                key=(r['token'],r['layer'],r['head'])
                if key in self.rows:raise ValueError('duplicate trace row '+str(key))
                self.rows[key]=r['logits']
            self.provenance=dict(kind='USER_LOGIT_TRACE',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                declared_provenance=data.get('provenance',{}),model_ppl_validated=False)
        if cfg.get('calibration_file'):
            path=Path(cfg['calibration_file']);self.calibration=json.loads(path.read_text(encoding='utf-8'))
            self.provenance['calibration_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()

    def random(self,token,layer,head,stream):
        identity=f"{self.cfg['seed']}:{token}:{layer}:{head}:{stream}".encode()
        return random.Random(int.from_bytes(hashlib.sha256(identity).digest()[:8],'little'))

    def logits(self,token,layer,head,length):
        if self.cfg.get('trace_file'):
            try:row=self.rows[token,layer,head]
            except KeyError:raise ValueError('missing logit trace row '+str((token,layer,head)))
        else:
            rng=self.random(token,layer,head,'logits')
            row=[rng.gauss(0,self.cfg['fixture_logit_std']) for _ in range(length)]
        if len(row)!=length or not all(math.isfinite(v) for v in row):raise ValueError('invalid trace logits')
        return row

    def parameters(self,layer,head):
        if self.calibration:
            return self.calibration['parameter'][layer][head],self.calibration['temperature'][layer][head]
        return self.cfg['selector_bias'],self.cfg['selector_temperature']
