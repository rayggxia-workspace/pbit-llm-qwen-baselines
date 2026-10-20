"""Reproducible document/plan and conditional-expectation checks, CPU stdlib only.

This does not evaluate a model, train, initialize CUDA or estimate physical PPA.
Run from the repository root: python -B work/amlink1219/61/validate_research.py
"""
from pathlib import Path
import datetime, hashlib, json, math, re

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
REPORT=ROOT/'architecture_tlm/HARDWARE_AWARE_TRAINING_PLAN_ZH_20261019.md'
PLAN=ROOT/'architecture_tlm/hardware_training_plan_20261019.json'

def main():
    doc=REPORT.read_text(encoding='utf-8')
    plan=json.loads(PLAN.read_text(encoding='utf-8'))
    assert plan['status']=='proposed_not_executed'
    assert not plan['coordination']['submitted_jobs']
    assert not plan['coordination']['new_trained_checkpoints']
    assert plan['acceptance']['user_quality_threshold'] is None
    assert plan['data']['test_for_training'] is False
    assert set(plan['sample_symbols'])=={'T','K','N','S'}
    for path in [REPORT,PLAN]:
        assert b'\r' not in path.read_bytes(),str(path)
    links=[]
    for target in re.findall(r'\]\(([^)]+)\)',doc):
        if '://' not in target:
            resolved=(REPORT.parent/target.split('#')[0]).resolve()
            assert resolved.is_relative_to(ROOT.resolve()) and resolved.is_file(),target
            links.append(target)
    ref=json.loads((ROOT/'architecture_tlm/ffn_stratified_reference/reference.json').read_text(encoding='utf-8'))
    source_hashes=[]
    for item in ref['implementation']['files']:
        raw=(ROOT/item['path']).read_bytes()
        normalized=raw.replace(b'\r\n',b'\n')
        sha=hashlib.sha256(normalized).hexdigest()
        assert sha==item['lf_text_sha256']
        source_hashes.append({'path':item['path'],'lf_sha256':sha})
    # Exact binomial enumeration verifies conditional mean/variance, not model unbiasedness.
    identity_error=mean_error=variance_error=0.0
    count=0
    for g in [-12.,-4.,-1.,0.,1.,4.,12.]:
        p=1/(1+math.exp(-g))
        identity_error=max(identity_error,abs(g*p-g*(1+math.tanh(g/2))/2))
        for u in [-1.25,0.75]:
            target=u*g*p
            for n in [1,4,16,64]:
                probs=[math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)]
                mean=sum(q*u*g*k/n for k,q in enumerate(probs))
                var=sum(q*(u*g*k/n-target)**2 for k,q in enumerate(probs))
                mean_error=max(mean_error,abs(mean-target))
                variance_error=max(variance_error,abs(var-(u*g)**2*p*(1-p)/n))
                assert abs(sum(probs)-1)<1e-11
                count+=1
    assert identity_error<1e-11 and mean_error<1e-10 and variance_error<1e-10
    # A nonlinear random local field cannot be replaced by its mean.
    mean_of_tanh=(math.tanh(0)+math.tanh(2))/2
    tanh_of_mean=math.tanh(1)
    assert abs(mean_of_tanh-tanh_of_mean)>0.25
    d,m=896,4864
    mt=3*m//2
    assert mt%64==0 and 3*d*m==2*d*mt==13074432
    result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'passed',
            'scope':'CPU analytical sanity, links, plan and existing source hashes; no new PPL/training/GPU/PPA',
            'local_links':links,'source_hashes':source_hashes,'binomial_cases':count,
            'max_errors':{'silu_tanh_identity':identity_error,'conditional_mean':mean_error,'conditional_variance':variance_error},
            'nonlinear_counterexample':{'E_tanh_H':mean_of_tanh,'tanh_E_H':tanh_of_mean},
            'matched_FFN':{'d':d,'glu_m':m,'tanh_m':mt,'matrix_parameters':3*d*m},
            'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'plan_sha256':hashlib.sha256(PLAN.read_bytes()).hexdigest()}
    (HERE/'VALIDATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
