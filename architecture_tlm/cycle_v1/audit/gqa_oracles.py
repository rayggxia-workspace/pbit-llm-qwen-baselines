"""Small independently specified GQA fixtures and scalar query answers.

No production Attention, shared-cache, source, or kernel implementation imports.
The default fixture has overlapping, non-contiguous physical token IDs whose
decimal strings sort in a different order from their numeric values.
"""
import math

from .scalar_oracles import f32


def overlap_fixture(*, mode="exact", reverse_heads=False):
    queries = [dict(q=[0.0, 0.0], candidate_ids=[1, 2, 10]),
               dict(q=[0.0, 0.0], candidate_ids=[10, 3, 2])]
    if mode == "pv":
        for query in queries:
            query["random_replay"] = {"uniforms": [.5]}
    if reverse_heads:
        queries.reverse()
    return dict(k=[[float(i), float(-i)] for i in range(11)],
                v=[[float(i), float(2*i-3), float(-i)/4] for i in range(11)],
                queries=queries)


def scalar_query(fixture, query, *, physical_counts=None):
    """Declared functional QK/softmax then ordered FP32 weighted-V boundary.

    Sampled answers accept independently specified physical multiplicities.
    They never use simulator-produced histogram or candidate-selection data.
    """
    ids = query["candidate_ids"]
    values = [[f32(v) for v in row] for row in fixture["v"]]
    if physical_counts is None:
        q = list(map(f32, query["q"]))
        logits = [f32(math.fsum(a*f32(b) for a,b in zip(q, fixture["k"][token]))/math.sqrt(len(q)))
                  for token in ids]
        exponentials = [math.exp(value-max(logits)) for value in logits]
        reciprocal = 1/math.fsum(exponentials)
        weight = {token:value*reciprocal for token,value in zip(ids, exponentials)}
    else:
        total = sum(physical_counts.values())
        if not total or not set(physical_counts) <= set(ids):
            raise ValueError("manual sample counts must refer to this query's physical candidates")
        weight = {token:count/total for token,count in physical_counts.items()}
    output = [0.0]*len(values[0])
    for token in sorted(weight):
        for j,value in enumerate(values[token]):
            output[j] = f32(output[j]+f32(weight[token]*value))
    return output
