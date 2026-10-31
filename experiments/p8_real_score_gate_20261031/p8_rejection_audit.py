"""Small analytic P8/corrected-rejection audit, not a model or hardware run."""
import hashlib,json,math,sys
from pathlib import Path
import numpy as np

lut=np.array([round(256/(1+math.exp(i/16))) for i in range(256)],dtype=int)

def uniform_rejection(n,S=128):
    M=n-1;states=25
    q=np.array([lut[min(round(16*m*math.log(2)),255)] for m in range(states)])
    p=q/256
    p0=np.exp(M*np.log1p(-p))
    p1=np.where(p>0,M*p*np.exp((M-1)*np.log1p(-p)),0.)
    up=np.maximum(0,1-p0-p1)
    accept_ref=p0*2.**(-np.arange(states))
    down=p0-accept_ref
    accept=p1+accept_ref
    fail=np.zeros((states,states))
    for m in range(states):
        fail[m,min(m+1,24)]+=up[m]
        fail[m,max(m-1,0)]+=down[m]
    fundamental=np.linalg.inv(np.eye(states)-fail)
    accepted_transition=fundamental@np.diag(accept)
    assert np.max(abs(accepted_transition.sum(1)-1))<1e-8
    time=fundamental@np.ones(states)
    ref_prob=fundamental@accept_ref
    dist=np.zeros(states);dist[0]=1.
    expected_time=0.;expected_ref=0.
    for _ in range(S):
        expected_time+=float(dist@time)
        expected_ref+=float(dist@ref_prob)
        dist=dist@accepted_transition
    # Actual cap completion probability, retaining accepted-count and m states.
    mass=np.zeros((S+1,states));mass[0,0]=1.
    for _ in range(S*64):
        base=mass[:-1];nxt=np.zeros_like(mass)
        nxt[1:]+=base*accept
        nxt[:-1,1:]+=base[:,:-1]*up[:-1]
        nxt[:-1,:-1]+=base[:,1:]*down[1:]
        nxt[:-1,0]+=base[:,0]*down[0]
        nxt[:-1,-1]+=base[:,-1]*up[-1]
        nxt[-1]+=mass[-1]
        mass=nxt
    assert abs(mass.sum()-1)<1e-8
    return dict(candidates=n,S=S,expected_trials_uncapped=expected_time,
        expected_trials_per_retained_address=expected_time/S,
        expected_reference_fraction_uncapped=expected_ref/S,
        ideal_reference_fraction=1/n,
        mean_histogram_reference_excess_lower_bound=expected_ref/S-1/n,
        probability_complete_within_cap=float(mass[-1].sum()),cap=S*64,
        q_by_m=q.tolist())

def main():
    contract=Path(__file__).parent/'NUMERIC_TABLES.json'
    if contract.is_file():
        tables=json.loads(contract.read_text(encoding='utf-8'))
        assert tables['sigmoid_lut']==lut.tolist()
        assert tables['rejection_m_ln2_F4']==[round(16*m*math.log(2)) for m in range(25)]
    n=2048;gap=7.;tail=(n-1)*math.exp(-gap)/(1+(n-1)*math.exp(-gap))
    result=dict(kind='ANALYTIC_SMALL_NUMERIC_REVIEW_NO_LLM_OR_PPA',
        p8=dict(first_zero_address=int(np.flatnonzero(lut==0)[0]),step=1/16,
            example_gap=gap,example_candidates=n,example_discarded_ideal_mass=tail,
            example_lut_code=int(lut[round(16*gap)])),
        corrected_rejection_uniform=[uniform_rejection(n) for n in [128,512,2048]],
        assumptions='independent proposals, uniform scores, exact fair zero correction; fixed plan P8 LUT and m_ln2 table',
        interpretation='Uniform logits are a synthetic counterexample, not evidence of how often actual Qwen heads exhibit this problem.')
    if '--mc' in sys.argv:
        rng=np.random.default_rng(22031);R=64;S=128;N=2048;M=N-1
        q=np.array([lut[min(round(16*m*math.log(2)),255)] for m in range(25)])
        p=q/256.;P0=np.exp(M*np.log1p(-p));P1=M*p*np.exp((M-1)*np.log1p(-p))
        m=np.zeros(R,dtype=int);accepted=np.zeros(R,dtype=int);refs=np.zeros(R,dtype=int);trials=np.zeros(R,dtype=int)
        for step in range(250000):
            rows=np.flatnonzero(accepted<S)
            if not len(rows):break
            cur=m[rows];u=rng.random(len(rows));zero=u<P0[cur];single=(u>=P0[cur])&(u<P0[cur]+P1[cur])
            zero_accept=zero&(rng.random(len(rows))<2.**(-cur))
            accepted[rows]+=single|zero_accept;refs[rows]+=zero_accept;trials[rows]+=1
            m[rows]=np.clip(cur+(~zero&~single)-(zero&~zero_accept).astype(int),0,24)
        assert np.all(accepted==S)
        result['independent_event_MC']=dict(seed=22031,replicas=R,candidates=N,S=S,
            mean_trials=float(trials.mean()),reference_fraction=float(refs.sum()/(R*S)),
            completed_within_8192=int(np.sum(trials<=8192)),
            note='Event-class simulation of binomial cardinality law; not full literal R8 bitmaps or a Qwen run.')
    result['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['numeric_contract_sha256']=hashlib.sha256(contract.read_bytes()).hexdigest() if contract.is_file() else None
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
