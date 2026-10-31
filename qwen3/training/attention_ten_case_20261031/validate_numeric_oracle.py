"""Exact small-state checks of the proposed P8 law, not an LLM/GPU sampler."""
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import json

def main():
    lut=json.loads((Path(__file__).parent/'NUMERIC_TABLES.json').read_text(encoding='utf-8'))['sigmoid_lut']
    tested=0;population_checks=0
    for scores in [(0,-16,-32,-48),(0,0,-1,-64),(0,-32,-160,-255)]:
        p=[F(lut[min(max(scores)-z,255)],256) for z in scores]
        odds=[x/(1-x) for x in p];normalizer=sum(odds)
        pi=[x/normalizer for x in odds];n=len(scores);M=n-1
        # Enumerate every Bernoulli pattern and exact uniform arbitration for WH.
        wh=[[F(0) for _ in scores] for _ in scores]
        for state in range(n):
            for bits in product([0,1],repeat=n):
                mass=F(1)
                for j,b in enumerate(bits):mass*=p[j] if b else 1-p[j]
                active=[j for j,b in enumerate(bits) if b]
                choices=[state] if bits[state] or not active else active
                for dest in choices:wh[state][dest]+=mass/len(choices)
        assert all(sum(row)==1 for row in wh)
        assert all(sum(pi[i]*wh[i][j] for i in range(n))==pi[j] for j in range(n))
        # Dense Gibbs in reference/one-hot states, one random node per update.
        gibbs=[[F(0) for _ in scores] for _ in scores]
        for i in range(1,n):
            gibbs[0][i]=p[i]/M;gibbs[i][0]=(1-p[i])/M
        for i in range(n):gibbs[i][i]=1-sum(gibbs[i])
        assert all(sum(pi[i]*gibbs[i][j] for i in range(n))==pi[j] for j in range(n))
        # Population feedback equals explicit all-to-all sum for every bit pattern.
        for b in product([0,1],repeat=M):
            A=sum(b)
            for i in range(M):
                dense=sum(b[j] for j in range(M) if j!=i)
                assert dense==A-b[i]
                q_dense=max(scores)-scores[i+1]+384*dense
                q_broadcast=max(scores)-scores[i+1]+384*(A-b[i])
                assert lut[min(q_dense,255)]==lut[min(q_broadcast,255)]
                if dense:assert lut[min(q_dense,255)]==0
                population_checks+=1
        tested+=1
    print(json.dumps(dict(status='passed',score_rows=tested,exact_stationarity_checks=6,
        population_equivalence_cases=population_checks,
        scope='small-state exact Fraction proof for proposed P8 WH/Gibbs laws; no CR training/LLM/PPA validation')))

if __name__=='__main__':main()
