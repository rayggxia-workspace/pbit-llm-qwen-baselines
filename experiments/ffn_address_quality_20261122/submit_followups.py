"""Slurm-only continuation: gate -> three screens -> qualified full WT2.

Stored separately from immutable GPU snapshots. No model/data loading here.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import shlex
import statistics
import subprocess

SBATCH = '/opt/slurm/21.08.8/bin/sbatch'
PYTHON = '/home/Hongjie_Zeng/projects/pbit-qwen3-baseline-20261023-issue136/venv/bin/python'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False)+'\n').encode())
    path.with_suffix('.sha256').write_bytes((sha(path)+'\n').encode())


def completed(path):
    path = Path(path)
    assert path.with_suffix('.sha256').read_text().strip() == sha(path), str(path)
    value = json.loads(path.read_bytes())
    assert value['status'] == 'completed', str(path)
    return value


def submit(command, source):
    result = subprocess.run([SBATCH, '--parsable']+command, cwd=source,
                            check=True, text=True, capture_output=True)
    return result.stdout.strip().split(';')[0]


def gpu_command(source, root, phase, seed, output, gate, case='', seconds=3600):
    wrap = shlex.join(['bash', str(source/'run_job.sh'), phase, str(seed), str(output), str(gate), case])
    minutes = max(60, math.ceil(seconds/60))
    return ['--partition=gpu5090', '--gres=gpu:1', '--cpus-per-task=4', '--mem=48G',
            '--time='+str(minutes), '--job-name=guaddr261-'+phase,
            '--chdir='+str(source), '--output='+str(root/'logs'/('%s-%s-%s-%%j.log'%(phase,case or 'all',seed))),
            '--wrap', wrap]


def select(rows, settings):
    chosen = []
    # A normalized comparator and a categorical sampler belong to the same
    # normalized family for this first capped promotion (still reported apart).
    for family in ['pot', 'normalized']:
        eligible = [r for r in rows if r['status']=='completed' and r['case']!='original_strat64'
                    and (r['family']=='pot' if family=='pot' else r['family'] in ['categorical','normalized_bernoulli'])
                    and r['ppl_ratio'] <= settings['absolute_max_ppl_ratio']
                    and r['relative_address_reduction'] >= settings['minimum_relative_unique_address_reduction']]
        preferred = [r for r in eligible if r['ppl_ratio'] <= settings['preferred_max_ppl_ratio']]
        if preferred:
            chosen.append(min(preferred, key=lambda r:(r['unique_address_ratio'],r['ppl_ratio'])))
        elif eligible:
            chosen.append(min(eligible, key=lambda r:(r['ppl_ratio'],r['unique_address_ratio'])))
    return chosen[:settings['max_full_candidates']]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--phase',choices=['after_gate','promote'],required=True)
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--gate',type=Path,required=True)
    ap.add_argument('--root',type=Path,required=True)
    ap.add_argument('--restore-proof',type=Path,required=True)
    a=ap.parse_args()
    expected=Path('/home/Hongjie_Zeng/projects/ffn-address-quality-issue261-20261122')
    assert a.root.resolve()==expected and a.source.resolve().parent==expected
    tag=a.gate.parent.name
    receipt=a.root/('FOLLOWUP_'+tag+'.json')
    if a.phase=='after_gate' and receipt.exists():
        print('already processed',receipt)
        return
    try:
        gate=completed(a.gate)
        proof=completed(a.restore_proof)
        assert proof['tests']==9 and proof['source_manifest_sha256']==gate['inputs']['source']['manifest_sha256']
        assert gate['phase']=='gate' and gate['full2048_original_logits_bitwise'] and gate['weights_unchanged']
        manifest=json.loads((a.source/'EXECUTION_MANIFEST.json').read_bytes())
        assert sha(a.source/'EXECUTION_MANIFEST.json')==gate['inputs']['source']['manifest_sha256']
        for name,digest in manifest['files'].items():assert sha(a.source/name)==digest
    except Exception as e:
        save(receipt,dict(status='blocked_gate',error=type(e).__name__+':'+str(e),gate=str(a.gate),no_screen_submitted=True))
        raise
    plan=json.loads((a.source/'PLAN.json').read_bytes())
    screen=a.root/('screen-'+tag)
    if a.phase=='after_gate':
        seconds=sum(p['result']['seconds'] for p in gate['pilots'])*len(plan['screen_window_indices'])*1.5+600
        jobs=[]
        for seed in plan['deployment_seeds']:
            output=screen/('seed'+str(seed))
            command=gpu_command(a.source,a.root,'screen',seed,output,a.gate,seconds=seconds)
            job=submit(command,a.source)
            jobs.append(dict(job=job,seed=seed,output=str(output),command=command))
            save(receipt,dict(status='submitting',screen_jobs=jobs,source=str(a.source),gate=str(a.gate)))
        command=['--partition=gpu5090','--cpus-per-task=1','--mem=4G','--time=00:15:00',
                 '--dependency=afterany:'+':'.join(j['job'] for j in jobs),
                 '--job-name=guaddr261-select','--output='+str(a.root/'logs/select-%j.log'),
                 '--wrap',shlex.join([PYTHON,str(Path(__file__).resolve()),'--phase','promote',
                                     '--source',str(a.source),'--gate',str(a.gate),'--root',str(a.root),
                                     '--restore-proof',str(a.restore_proof)])]
        selection_job=submit(command,a.source)
        value=dict(status='submitted',screen_jobs=jobs,selection_job=selection_job,
                   selection_command=command,source=str(a.source),gate=str(a.gate),
                   controller_sha256=sha(__file__),observed_gate_pilots_seconds=sum(p['result']['seconds'] for p in gate['pilots']),
                   restore_proof_sha256=sha(a.restore_proof),
                   requested_seconds_per_screen=seconds,full_submission='conditional_on_three_seed_quality_and_read_reduction')
        save(receipt,value);print(json.dumps(value));return

    rows=[]
    baseline=[]
    case_values={}
    for case in plan['cases']:
        items=[];errors=[]
        for seed in plan['deployment_seeds']:
            p=screen/('seed'+str(seed))/case['id']/'RESULT.json'
            try:
                item=completed(p)
                assert item['phase']=='screen' and not item['full_corpus'] and item['seed']==seed
                assert item['identity']==gate['identity'] and item['inputs']==gate['inputs'] and item['protocol']==gate['protocol']
                assert item['result']['windows']==8 and [w['window_index'] for w in item['result']['window_ledger']]==plan['screen_window_indices']
                assert item['result']['ppl'] is not None
                items.append(item)
            except Exception as e:
                errors.append(dict(seed=seed,path=str(p),error=type(e).__name__+':'+str(e)))
        if errors:
            rows.append(dict(case=case['id'],family=case['family'],status='not_completed',errors=errors));continue
        ledgers=[[{k:w[k] for k in ['window_index','start','end','first_target','targets','target_token_sha256']}
                  for w in i['result']['window_ledger']] for i in items]
        assert ledgers[0]==ledgers[1]==ledgers[2]
        if case['kind']=='original':baseline=items
        case_values[case['id']]=items
        ppls=[i['result']['ppl'] for i in items]
        row=dict(case=case['id'],family=case['family'],status='completed',seeds=plan['deployment_seeds'],
                 ppl_mean=statistics.mean(ppls),ppl_sd=statistics.stdev(ppls),
                 mean_nll=statistics.mean(i['result']['mean_nll'] for i in items),
                 unique_address_ratio=statistics.mean(i['result']['addresses']['unique_address_ratio'] for i in items))
        rows.append(row)
    assert len(baseline)==3,'missing matched original P-FFN reference; no full promotion'
    baseline_ledger=[{k:w[k] for k in ['window_index','start','end','first_target','targets','target_token_sha256']}
                     for w in baseline[0]['result']['window_ledger']]
    b=next(r for r in rows if r['case']=='original_strat64')
    for row in rows:
        if row['status']=='completed':
            for value in case_values[row['case']]:
                assert [{k:w[k] for k in ['window_index','start','end','first_target','targets','target_token_sha256']} for w in value['result']['window_ledger']]==baseline_ledger
            row['ppl_ratio']=math.exp(row['mean_nll']-b['mean_nll'])
            row['relative_address_reduction']=1-row['unique_address_ratio']/b['unique_address_ratio']
    selected=select(rows,plan['promotion'])
    summary=dict(status='completed',scope='8window_screen_not_full_WT2',rows=rows,
                 selected_full_cases=[r['case'] for r in selected],settings=plan['promotion'],
                 gate=str(a.gate),source_manifest_sha256=sha(a.source/'EXECUTION_MANIFEST.json'),
                 controller_sha256=sha(__file__))
    save(a.root/('SCREEN_SUMMARY_'+tag+'.json'),summary)
    jobs=[]
    if selected:
        # Same-seed current sparse-backend controls accompany promoted cases.
        # No healthy run is cancelled or modified; these are new scoped jobs.
        for case_id in ['original_strat64']+[r['case'] for r in selected]:
            pilot=next(p for p in gate['pilots'] if p['case']['id']==case_id)
            seconds=pilot['result']['seconds']*292*1.5+600
            for seed in plan['deployment_seeds']:
                output=a.root/('full-'+tag)/case_id/('seed'+str(seed))
                command=gpu_command(a.source,a.root,'full',seed,output,a.gate,case_id,seconds)
                job=submit(command,a.source)
                jobs.append(dict(job=job,case=case_id,seed=seed,output=str(output),command=command))
                save(a.root/('FULL_SUBMISSION_'+tag+'.json'),dict(status='submitting',jobs=jobs))
    result=dict(status='submitted' if jobs else 'completed_no_qualified_candidate',jobs=jobs,
                selected_cases=summary['selected_full_cases'],summary_sha256=sha(a.root/('SCREEN_SUMMARY_'+tag+'.json')),
                controller_sha256=sha(__file__))
    save(a.root/('FULL_SUBMISSION_'+tag+'.json'),result)
    print(json.dumps(result))


if __name__=='__main__':main()
