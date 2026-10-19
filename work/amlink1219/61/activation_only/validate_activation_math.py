"""CPU analytical checks for the activation-only proposal; no model evaluation.

Run from repository root: python -B work/amlink1219/61/activation_only/validate_activation_math.py
"""
from pathlib import Path
import datetime, hashlib, json, math, re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
REPORT=ROOT/'architecture_tlm/activation_only_feasibility_20261019/README_ZH.md'
PLAN=REPORT.with_name('PLAN.json')

def probability(g):return 1/(1+math.exp(-g))

def enumerated_loss(g,u,target,n):
    p=probability(g)
    return sum(math.comb(n,k)*p**k*(1-p)**(n-k)*(u*g*k/n-target)**2 for k in range(n+1))

def main():
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    assert plan['status']=='proposed_not_executed'
    assert plan['submitted_jobs']==[] and plan['new_PPL_results']==[]
    assert plan['first_stage']['value_branch']=='continuous; not separately sampled'
    assert plan['quality_acceptance_threshold'] is None
    result={'cases':0,'max_mean_error':0.,'max_variance_error':0.,'max_gradient_error':0.,'max_mean_loss_gradient_gap':0.}
    for g in [-6.,-4.,-2.,-1.,-.25,.25,.5,1.,2.,4.]:
        p=probability(g)
        for u,target in [(0.75,.3),(-1.25,.7)]:
            for n in [1,4,16,64]:
                probs=[math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)]
                mean=sum(q*u*g*k/n for k,q in enumerate(probs))
                var=sum(q*(u*g*k/n-u*g*p)**2 for k,q in enumerate(probs))
                direct=score=0.
                for k,q in enumerate(probs):
                    z=u*g*k/n;loss=(z-target)**2
                    direct+=q*2*(z-target)*u*k/n
                    score+=q*loss*(k-n*p)
                exact_gradient=direct+score
                eps=1e-5
                numerical=(enumerated_loss(g+eps,u,target,n)-enumerated_loss(g-eps,u,target,n))/(2*eps)
                gradient_of_mean_loss=2*(u*g*p-target)*(u*p+u*g*p*(1-p))
                result['max_mean_error']=max(result['max_mean_error'],abs(mean-u*g*p))
                result['max_variance_error']=max(result['max_variance_error'],abs(var-(u*g)**2*p*(1-p)/n))
                result['max_gradient_error']=max(result['max_gradient_error'],abs(exact_gradient-numerical))
                result['max_mean_loss_gradient_gap']=max(result['max_mean_loss_gradient_gap'],abs(exact_gradient-gradient_of_mean_loss))
                result['cases']+=1
    assert result['max_mean_error']<1e-11
    assert result['max_variance_error']<1e-11
    assert result['max_gradient_error']<1e-7
    assert result['max_mean_loss_gradient_gap']>.1
    p,q=.2,.8
    joint_shared=min(p,q)
    assert joint_shared!=p*q
    links=[]
    for target in re.findall(r'\]\(([^)]+)\)',REPORT.read_text(encoding='utf-8')):
        if '://' not in target:
            actual=(REPORT.parent/target.split('#')[0]).resolve()
            assert actual.is_relative_to(ROOT.resolve()) and actual.is_file(),target
            links.append(target)
    for f in [REPORT,PLAN]:
        f.read_text(encoding='utf-8');assert b'\r' not in f.read_bytes()
    result.update(status='passed',scope='80 exact-binomial conditional moment/gradient cases, shared-threshold counterexample and document links; no model PPL, training, CUDA or PPA',
                  checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  shared_threshold_example={'p':p,'q':q,'independent_AND':p*q,'shared_AND':joint_shared,'covariance':joint_shared-p*q},
                  local_links=links,report_sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest(),plan_sha256=hashlib.sha256(PLAN.read_bytes()).hexdigest())
    (HERE/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
