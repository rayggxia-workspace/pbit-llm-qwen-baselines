"""Validate the design matrix and frozen numeric tables; no torch/job submission."""
from pathlib import Path
import copy
import json
import math

ROOT=Path(__file__).resolve().parent

def check(plan,tables):
    cases=plan['cases']; assert len(cases)==11
    assert len({c['id'] for c in cases})==11
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
    assert set(byid)=={prefix+'_'+suffix for prefix in ('N','K') for suffix in expected}|{'K_WH32'}
    extra=byid['K_WH32']
    assert (extra['screen'],extra['sampler'],extra['samples'])==('sparq','winner_hold',32)
    assert extra['family_baseline']=='K_WH128' and extra['paired_screen_case'] is None
    assert extra['changed_factor_within_family']=='samples'
    assert 'N_WH32' not in byid
    assert len([c for c in cases if c['screen']=='none'])==5
    assert len([c for c in cases if c['screen']=='sparq'])==6
    assert len(cases)+len(plan['controls'])==13
    cr=plan['samplers']['corrected_rejection']
    assert cr['execution_mode']=='strict_bounded_pure_CR'
    assert cr['max_trials_per_sample']==64 and cr['initial_m']==0 and cr['max_m']==24
    assert cr['row_trial_cap']=='S*64; stop and report failure, no silent fallback'
    assert cr['on_row_cap_failure']=='fail_current_case_and_archive_input'
    assert cr['partial_output_allowed'] is False and cr['fallback_sampler'] is None
    assert cr['drop_failed_rows'] is False and cr['continue_other_cases'] is True
    assert cr['preflight_optimizer_updates']==2
    assert plan['common']['no_second_pv_sampling']
    assert not plan['executable']
    assert plan['common']['shared_trained_prefix'] is False
    assert plan['common']['freeze_other_parameters']
    m=plan['model']; d=m['hidden_size'];q=m['query_heads']*m['head_dim'];kv=m['kv_heads']*m['head_dim']
    assert m['layers']*(2*d*q+2*d*kv)==943718400==plan['common']['expected_trainable_weights']
    assert {x['screen'] for x in plan['controls']}=={'none','sparq'}
    assert len(plan['controls'])==2
    assert plan['screening']['total_candidate_budget']==256
    assert plan['screening']['feature_budget']==32
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
    for n in [2,256,2048]:
        M=n-1
        assert (32+128)*M>0
    assert (32+128)*2047==327520 and (32+128)*255==40800
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
        ('old_candidate128',lambda p:p['screening'].update(total_candidate_budget=128)),
        ('recent_window64',lambda p:p['screening'].update(recent_candidate_budget=64)),
        ('replace_original_S256',lambda p:p['cases'][7].update(samples=32)),
        ('wrong_S32_sampler',lambda p:p['cases'][-1].update(sampler='corrected_rejection')),
        ('invent_N_S32_pair',lambda p:p['cases'][-1].update(paired_screen_case='N_WH32')),
        ('unbounded_CR_cap',lambda p:p['samplers']['corrected_rejection'].update(max_trials_per_sample=0)),
        ('hidden_CR_fallback',lambda p:p['samplers']['corrected_rejection'].update(fallback_sampler='winner_hold')),
        ('drop_failed_CR_rows',lambda p:p['samplers']['corrected_rejection'].update(drop_failed_rows=True)),
        ('partial_CR_output',lambda p:p['samplers']['corrected_rejection'].update(partial_output_allowed=True)),
    ]:
        p=copy.deepcopy(plan);mutate(p)
        try:check(p,tables)
        except (AssertionError,KeyError):rejected.append(label)
        else:raise AssertionError('invalid plan accepted: '+label)
    print(json.dumps(dict(status='passed',cases=11,controls=2,total_training_cases=13,rejected_negative_cases=rejected,
        numeric_table_entries=256,scope='design/numeric-contract validation only; no sampler/LLM training/PPA'),ensure_ascii=False))

if __name__=='__main__':main()
