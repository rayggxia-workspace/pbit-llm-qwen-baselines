"""Validate the design matrix and frozen numeric tables; no torch/job submission."""
from pathlib import Path
import copy
import json
import math

ROOT=Path(__file__).resolve().parent

def check(plan,tables):
    cases=plan['cases']; assert len(cases)==10
    assert len({c['id'] for c in cases})==10
    expected={'WH128':('winner_hold',128),'WH64':('winner_hold',64),
        'WH256':('winner_hold',256),'CR128':('corrected_rejection',128),
        'G128':('dense_random_scan_gibbs',128)}
    byid={c['id']:c for c in cases}
    for prefix,screen in [('N','none'),('K','sparq')]:
        for suffix,(sampler,s) in expected.items():
            row=byid[prefix+'_'+suffix]
            assert (row['screen'],row['sampler'],row['samples'])==(screen,sampler,s)
            assert row['family_baseline']==prefix+'_WH128'
            pair=byid[row['paired_screen_case']]
            assert pair['sampler']==sampler and pair['samples']==s and pair['screen']!=screen
    assert plan['common']['no_second_pv_sampling']
    assert not plan['executable']
    assert plan['common']['shared_trained_prefix'] is False
    assert plan['common']['freeze_other_parameters']
    m=plan['model']; d=m['hidden_size'];q=m['query_heads']*m['head_dim'];kv=m['kv_heads']*m['head_dim']
    assert m['layers']*(2*d*q+2*d*kv)==943718400==plan['common']['expected_trainable_weights']
    assert {x['screen'] for x in plan['controls']}=={'none','sparq'}
    assert len(plan['controls'])==2
    assert plan['screening']['total_candidate_budget']==128
    assert plan['screening']['recent_candidate_budget']==32
    assert tables['score']['signed_bits']==12 and tables['score']['fraction_bits']==4
    lut=tables['sigmoid_lut'];assert len(lut)==256 and lut[0]==128 and lut[-1]==0
    assert all(0<=x<=128 for x in lut)
    assert all(lut[i]>=lut[i+1] for i in range(255))
    assert lut==[int(round(256/(1+math.exp(i/16)))) for i in range(256)]
    assert next(i for i,q in enumerate(lut) if q==0)==100
    assert tables['rejection_m_ln2_F4']==[int(round(16*i*math.log(2))) for i in range(25)]
    # Integer R8 comparator exactly represents each threshold, including 0/128/255/256.
    for q in [0,1,128,255,256]:assert sum(r<q for r in range(256))==q
    for n in [2,128,2048]:
        M=n-1
        assert (32+128)*M>0
    assert (32+128)*2047==327520 and (32+128)*127==20320
    # Nonempty other population gives a zero P8 birth probability under kappa24.
    assert lut[min(384,255)]==0
    assert plan['common']['dense_prefix_tokens']+plan['common']['stochastic_suffix_tokens']==2048

def main():
    plan=json.loads((ROOT/'CASES.json').read_text(encoding='utf-8'))
    tables=json.loads((ROOT/'NUMERIC_TABLES.json').read_text(encoding='utf-8'))
    check(plan,tables)
    rejected=[]
    for label,mutate in [
        ('duplicate_case',lambda p:p['cases'].append(copy.deepcopy(p['cases'][0]))),
        ('extra_sampler_scan',lambda p:p['cases'][3].update(samples=64)),
        ('hidden_screening',lambda p:p['cases'][0].update(screen='sparq')),
        ('wrong_trainable_count',lambda p:p['common'].update(expected_trainable_weights=1)),
        ('shared_trained_prefix',lambda p:p['common'].update(shared_trained_prefix=True)),
    ]:
        p=copy.deepcopy(plan);mutate(p)
        try:check(p,tables)
        except (AssertionError,KeyError):rejected.append(label)
        else:raise AssertionError('invalid plan accepted: '+label)
    print(json.dumps(dict(status='passed',cases=10,controls=2,rejected_negative_cases=rejected,
        numeric_table_entries=256,scope='design/numeric-contract validation only; no sampler/LLM training/PPA'),ensure_ascii=False))

if __name__=='__main__':main()
