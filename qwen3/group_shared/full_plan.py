"""Pure full-WT2 planning, shard-independent RNG keys and strict aggregation."""
import hashlib
import math
from qwen3.stochastic.vendor.scoring import full_window_plan,ids_sha256,target_positions


def window_seed(seed,segment):
    if seed not in (0,1,2) or type(segment) is not int or segment<0:
        raise ValueError('invalid full-WT2 seed/segment')
    return int.from_bytes(hashlib.sha256(f'issue206-full-v1/{seed}/{segment}'.encode()).digest()[:6],'little')


def split_plan(plan,part,parts):
    if type(parts) is not int or parts<1 or type(part) is not int or not 0<=part<parts:
        raise ValueError('invalid shard')
    return plan[len(plan)*part//parts:len(plan)*(part+1)//parts]


def verify_rows(rows,expected):
    if len(rows)!=len(expected):raise ValueError('missing/duplicate windows')
    actual=sorted(rows,key=lambda r:r['segment_id'])
    for r,e in zip(actual,expected):
        if any(r[k]!=v for k,v in e.items()):raise ValueError('window/target coverage mismatch')
        if not math.isfinite(r['nll_sum']) or r['nll_sum']<0:raise ValueError('invalid loss')
    n=sum(r['scored_tokens'] for r in actual);s=math.fsum(r['nll_sum'] for r in actual)
    if n<1:raise ValueError('empty scoring')
    return dict(scored_tokens=n,nll_sum=s,perplexity=math.exp(s/n),
        target_positions_sha256=ids_sha256(p for r in actual for p in target_positions(r)))
