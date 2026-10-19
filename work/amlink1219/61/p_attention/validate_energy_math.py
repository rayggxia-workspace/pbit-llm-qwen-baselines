"""Small exact diagnostics; no model, accelerator, training or PPA claims."""
from pathlib import Path
import itertools, json, math, hashlib

ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
def sigmoid(x):
    return 1/(1+math.exp(-x))
def softmax(z):
    v=[math.exp(x-max(z)) for x in z];return [x/sum(v) for x in v]
def star(z):
    n=len(z);r=max(range(n),key=z.__getitem__);q=[[0.]*n for _ in z]
    for i in range(n):
        if i!=r:
            p=sigmoid(z[i]-z[r]);q[r][i]=p;q[i][r]=1-p
    for i in range(n):q[i][i]=-sum(q[i])
    return q,r
def finite(z,t,initial):
    q,r=star(z);nu=max(-q[i][i] for i in range(len(z)))
    trans=[[float(i==j)+q[i][j]/nu for j in range(len(z))] for i in range(len(z))]
    v=[float(i==initial) for i in range(len(z))];weight=math.exp(-nu*t)
    out=[weight*x for x in v]
    for k in range(1,1500):
        v=[sum(v[i]*trans[i][j] for i in range(len(z))) for j in range(len(z))]
        weight*=nu*t/k
        out=[a+weight*b for a,b in zip(out,v)]
        if k>nu*t and weight<1e-17:break
    assert abs(sum(out)-1)<1e-12
    return out

max_balance=0.;cases=0
for z in [[0.,0.],[0.,1.,-1.],[4.,0.,-4.],[.7,-1.2,2.1,0.]]:
    p=softmax(z);q,r=star(z)
    for i,j in itertools.product(range(len(z)),repeat=2):
        err=abs(p[i]*q[i][j]-p[j]*q[j][i]);max_balance=max(max_balance,err)
        assert err<1e-14;cases+=1
    assert max(abs(sum(p[i]*q[i][j] for i in range(len(z)))) for j in range(len(z)))<1e-14
    assert max(abs(a-b) for a,b in zip(p,softmax([x+13 for x in z])))<1e-14

z=[3.,0.,-2.];p=softmax(z)
curves={str(init):{str(t):sum(abs(a-b) for a,b in zip(finite(z,t,init),p))/2 for t in [0.,1.,4.,16.]} for init in [0,2]}
assert curves['2']['1.0']>1e-3 and curves['2']['16.0']<curves['2']['1.0']

# Pairwise Barker accepts only after correcting a non-symmetric proposal ratio.
proposal=[[.8,.2],[.6,.4]];p=softmax([0.,1.]);naive=[];correct=[]
for i,j in [(0,1),(1,0)]:
    naive.append(p[i]*proposal[i][j]*sigmoid(math.log(p[j]/p[i])))
    correct.append(p[i]*proposal[i][j]*sigmoid(math.log(p[j]*proposal[j][i]/(p[i]*proposal[i][j]))))
assert abs(naive[0]-naive[1])>1e-3 and abs(correct[0]-correct[1])<1e-14

# Pair terms in 0/1 strict one-hot encoding vanish; multi-on states differ.
for b in itertools.product([0,1],repeat=4):
    if sum(b)==1:
        assert sum((i+j+1)*b[i]*b[j] for i in range(4) for j in range(i+1,4))==0
binary={'classes':512,'bits':9,'quadratic_coefficients_including_constant':1+9+9*8//2,'distribution_degrees_of_freedom':511}
assert binary['quadratic_coefficients_including_constant']<binary['distribution_degrees_of_freedom']

# E[ratio] differs from ratio of marginal sums; empty masks explicitly output 0.
ps=[.2,.8];values=[2.,7.];mask_mean=0.;ratio_mean=0.
for b in itertools.product([0,1],repeat=2):
    prob=math.prod(ps[i] if b[i] else 1-ps[i] for i in range(2))
    numerator=sum(b[i]*values[i] for i in range(2))
    mask_mean+=prob*numerator;ratio_mean+=prob*(numerator/sum(b) if sum(b) else 0.)
assert abs(mask_mean-sum(a*b for a,b in zip(ps,values)))<1e-14
ratio_of_marginals=sum(a*b for a,b in zip(ps,values))/sum(ps)
assert abs(ratio_mean-ratio_of_marginals)>1e-3
empty=(512/513)**512
assert .36<empty<.38
report=ROOT/'architecture_tlm/p_attention_feasibility_20261019/README_ZH.md'
plan=ROOT/'architecture_tlm/p_attention_feasibility_20261019/PLAN.json'
data=json.loads(plan.read_text(encoding='utf-8'));assert data['status']=='proposed_not_executed'
assert data['model_runs']==[] and data['PPL_tolerance'] is None
result={'status':'passed','scope':'exact finite-state mathematics only; no model PPL/training/CUDA/PPA','detailed_balance_pairs':cases,'max_balance_error':max_balance,'finite_time_total_variation':curves,'binary_encoding':binary,'asymmetric_proposal_naive_flux_gap':abs(naive[0]-naive[1]),'corrected_flux_gap':abs(correct[0]-correct[1]),'sigmoid_mask':{'expected_sum':mask_mean,'expected_random_ratio_empty_zero':ratio_mean,'ratio_of_marginals':ratio_of_marginals,'uniform_512_empty_probability':empty},'report_sha256':hashlib.sha256(report.read_bytes()).hexdigest(),'plan_sha256':hashlib.sha256(plan.read_bytes()).hexdigest()}
(OUT/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result,ensure_ascii=False))
