"""Read-only status and sealed-result audit for the full pruning evaluation."""
from pathlib import Path
import argparse
import hashlib
import json
import math


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def read(path):
    if not path.exists():return None
    assert path.with_suffix('.sha256').read_text().strip()==sha(path),str(path)
    d=json.loads(path.read_bytes());assert d['status']=='completed',str(path)
    return d


def inspect(ppl_root,task_root):
    ppl=[];tasks=[];pending=[];raw=[];ledgers={}
    for name in ['bf16','original_strat64','input_p20','potnorm_p20']:
        path=ppl_root/name/'RESULT.json';d=read(path)
        if d is None:
            progress=path.parent/'PROGRESS.json'
            p=json.loads(progress.read_bytes()) if progress.exists() else None
            pending.append({'phase':'PPL','case':name,'windows':len(p['windows']) if p else 0,
                            'elapsed_seconds':p['elapsed_seconds'] if p else None})
            continue
        r=d['result'];assert d['full_corpus'] and d['phase']=='full_WT2' and d['seed']==101
        assert r['windows']==292 and r['targets']==299077 and d['first_window_same_seed_NLL_bitwise']
        assert math.isclose(r['ppl'],math.exp(r['nll']/299077),rel_tol=1e-12)
        ledger=[{k:w[k] for k in ['window_index','start','end','first_target','targets','target_token_sha256']} for w in r['window_ledger']]
        if 'PPL' in ledgers:assert ledger==ledgers['PPL']
        ledgers['PPL']=ledger
        if name!='bf16':
            assert r['addresses']['original_wd_calls']==36*292
            assert set(r['addresses']['per_layer'])=={str(i) for i in range(36)}
            assert all(v['calls']==292 for v in r['addresses']['per_layer'].values())
        row={'case':name,'ppl':r['ppl'],'result_sha256':sha(path),'seconds':d['seconds']}
        if r['addresses'] is not None:row['unique_GU_address_fraction']=r['addresses']['unique_address_ratio']
        ppl.append(row);raw.append({'phase':'PPL','case':name,'file':'RESULT.json','sha256':sha(path),'bytes':path.stat().st_size})
    counts={'piqa':1838,'arc_challenge':1172,'winogrande':1267}
    for case in ['bf16','original_strat64','input_p20']:
        for task,count in counts.items():
            path=task_root/case/task/'RESULT.json';d=read(path)
            if d is None:
                p=path.parent/'PROGRESS.json'
                pending.append({'phase':'tasks','case':case,'task':task,'progress':json.loads(p.read_bytes()) if p.exists() else None})
                continue
            assert d['phase']=='full_downstream_task' and d['full_split'] and d['seed']==101
            assert d['documents']==count and d['task']==task and d['case']['id']==case
            official_path=path.parent/'OFFICIAL_RESULT.json';official=json.loads(official_path.read_bytes())
            assert sha(official_path)==d['official_result_sha256']
            samples=official['samples'][task];assert len(samples)==count
            assert len({s['doc_id'] for s in samples})==count
            audit=d['audit'];assert audit['layers']==36 and audit['all_prompt_and_answer_positions_covered'] and not audit['prefix_exception']
            batch_sha=audit['input_batch_ledger_sha256']
            if task in ledgers:assert batch_sha==ledgers[task],'paired task requests/forward batching differ'
            ledgers[task]=batch_sha
            if case!='bf16':assert d['addresses']['original_wd_calls']==36*audit['model_calls']
            for key,value in d['metrics'].items():
                metric=key.split(',')[0]
                assert math.isclose(sum(float(s[metric]) for s in samples)/count,value,rel_tol=1e-12)
            tasks.append({'case':case,'task':task,'documents':count,'metrics':d['metrics'],'seconds':d['seconds'],
                          'result_sha256':sha(path),'official_result_sha256':sha(official_path),'batch_ledger_sha256':batch_sha})
            raw.append({'phase':'tasks','case':case,'task':task,'file':'RESULT.json','sha256':sha(path),'bytes':path.stat().st_size})
    return {'status':'completed' if not pending else 'partial','ppl_completed':len(ppl),'tasks_completed':len(tasks),
            'expected_unique_results':13,'ppl':ppl,'tasks':tasks,'pending':pending,'raw_index':raw,
            'completion_basis':'sealed completed JSON, actual positions/documents/layers; no inference from queue disappearance'}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--ppl-root',type=Path,required=True)
    ap.add_argument('--task-root',type=Path,required=True);ap.add_argument('--output',type=Path)
    a=ap.parse_args();d=inspect(a.ppl_root,a.task_root)
    text=json.dumps(d,indent=2)+'\n'
    if a.output:
        a.output.write_bytes(text.encode());a.output.with_suffix('.sha256').write_bytes((sha(a.output)+'\n').encode())
    print(text)
