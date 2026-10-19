"""Offline matched NLL analysis; source artifact hashes remain independently indexed."""
import argparse
import json
import math
from pathlib import Path
import statistics


def summarize(collected, phase):
    indexed = {row['path']: row for row in collected['files']}
    entries = []
    for row in collected['rows']:
        matched_control = (phase == 'fallback' and row['path'].startswith('suffix/')
                           and row['data'].get('configuration', {}).get('mode') == 'sdpa')
        if not row['path'].startswith(phase + '/') and not matched_control:
            continue
        d = row['data']; c = d['configuration']; audit = d['execution_audit']
        if not (d['status'] == 'completed' and audit['every_scored_target_executed_all_24_layers']
                and audit['every_scored_target_executed_all_24_ffns']):
            raise ValueError('Incomplete or bypassed operator path')
        if abs(math.log(d['perplexity']) - d['mean_nll']) > 1e-12:
            raise ValueError('Inconsistent PPL/NLL')
        entries.append(dict(artifact=indexed[row['path']], configuration=c,
            configuration_sha256=d['configuration_sha256'], code_commit=d['code_commit'],
            identity_sha256=d['identity_sha256'], model_revision=d['model_revision'],
            token_ids_sha256_le_int64=d['token_ids_sha256_le_int64'],
            target_positions_sha256_le_int64=d['scoring_plan']['target_positions_sha256_le_int64'],
            scored_tokens=d['scored_tokens'], perplexity=d['perplexity'], mean_nll=d['mean_nll'],
            nll_sum=d['nll_sum'], segments=[dict(segment_id=r['segment_id'],nll_sum=r['nll_sum'],
                scored_tokens=r['scored_tokens']) for r in d['examples']],
            sampling=d['sampling_summary'], execution_audit=audit,
            elapsed_seconds=d['elapsed_seconds'], decode_seconds=d['decode_seconds'],
            prefill_seconds=d['prefill_seconds'], peak_allocated_bytes=d['peak_allocated_bytes'],
            slurm_job_id=d['slurm_job_id'], environment=d['environment']))
    if not entries:
        raise ValueError('No scored results')
    signatures={(d['model_revision'],d['token_ids_sha256_le_int64'],
        d['target_positions_sha256_le_int64'],d['scored_tokens'],d['configuration']['batch']) for d in entries}
    if len(signatures) != 1:
        raise ValueError('Results do not use a matched protocol/model/target set')
    lookup={(d['configuration']['ffn'],d['configuration']['mode'],d['configuration']['samples'],
             d['configuration']['seed']):d for d in entries}
    if len(lookup)!=len(entries):
        raise ValueError('Duplicate results')
    baseline=lookup[('none','sdpa',128,0)]
    groups={}
    for entry in entries:
        c=entry['configuration'];groups.setdefault((c['ffn'],c['mode'],c['samples']),[]).append(entry)
    rows=[]
    for (ffn,mode,samples),values in sorted(groups.items()):
        values=sorted(values,key=lambda x:x['configuration']['seed'])
        seeds=[d['configuration']['seed'] for d in values]
        expected=[0] if ffn=='none' and mode=='sdpa' else [0,1,2]
        if seeds!=expected:
            raise ValueError('Incomplete seed set: '+str((ffn,mode,samples,seeds)))
        p=[d['perplexity'] for d in values];nll=[d['mean_nll'] for d in values]
        interactions=[]
        if ffn!='none' and mode!='sdpa':
            for d in values:
                seed=d['configuration']['seed']
                f=lookup[(ffn,'sdpa',128,seed)];a=lookup[('none',mode,samples,seed)]
                interactions.append(d['mean_nll']-f['mean_nll']-a['mean_nll']+baseline['mean_nll'])
        stat=[d['sampling'] for d in values if d['sampling']]
        rows.append(dict(ffn=ffn,attention=mode,samples=samples if mode!='sdpa' else None,seeds=seeds,
            ppl_mean=statistics.mean(p),ppl_population_sd=statistics.pstdev(p),
            mean_nll=statistics.mean(nll),delta_nll=statistics.mean(nll)-baseline['mean_nll'],
            geometric_ppl_ratio=math.exp(statistics.mean(nll)-baseline['mean_nll']),
            interaction_nll_mean=statistics.mean(interactions) if interactions else None,
            interaction_nll_population_sd=statistics.pstdev(interactions) if interactions else None,
            selected_fraction=statistics.mean(s['selected_fraction'] for s in stat) if stat else None,
            gqa_union_fraction=statistics.mean(s['GQA_union_fraction'] for s in stat) if stat else None,
            adjacent_repeat_fraction=statistics.mean(s['adjacent_repeat_fraction'] for s in stat) if stat else None,
            elapsed_seconds_mean=statistics.mean(d['elapsed_seconds'] for d in values)))
    return dict(phase=phase,protocol=entries[0]['configuration']['protocol'],
        scored_tokens=baseline['scored_tokens'],target_positions_sha256=baseline['target_positions_sha256_le_int64'],
        baseline_ppl=baseline['perplexity'],rows=rows,individual_results=entries,
        uncertainty='population SD across sampling seeds on fixed corpus targets; not corpus uncertainty',
        interaction='Ljoint - Lffn - Lattention + Lbaseline, per matched seed; L is mean NLL',
        ppl_aggregation='arithmetic mean of per-seed PPL; geometric ratio uses mean NLL',
        rng_pairing='same seed domains; CTMC trajectories may diverge as event counts/logits change')


def main():
    p=argparse.ArgumentParser();p.add_argument('collected');p.add_argument('output');p.add_argument('--phase',default='suffix')
    a=p.parse_args();r=summarize(json.loads(Path(a.collected).read_text(encoding='utf-8')),a.phase)
    Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in r.items() if k!='individual_results'},ensure_ascii=True))
if __name__=='__main__':main()
