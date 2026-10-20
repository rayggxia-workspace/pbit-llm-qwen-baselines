"""Join only compatible Ising-count cases and published original-FFN controls."""
import argparse,hashlib,json,math,statistics
from pathlib import Path

SAMPLES=(32,64,128,256,512,1024)


def load_own(collected,origin):
    artifacts={v['path']:v for v in collected['files']};rows=[]
    for r in collected['rows']:
        if not r['path'].startswith(('suffix/','reference/')):continue
        d=r['data'];c=d.get('configuration',{})
        if c.get('ffn')=='none' and c.get('mode')=='sdpa':pass
        elif c.get('ffn')!='b4_t32':continue
        if c.get('mode') not in ('sdpa','screen_ising','screen_exact'):continue
        a=d['execution_audit']
        if not a['every_scored_target_executed_all_24_layers'] or not a['every_scored_target_executed_all_24_ffns']:
            raise ValueError('Bypassed joint path')
        if d['scored_tokens']!=4096 or c['batch']!=8 or c['protocol']!='suffix':
            raise ValueError('Not matched suffix scoring')
        if not math.isclose(math.log(d['perplexity']),d['mean_nll'],abs_tol=1e-12):
            raise ValueError('Inconsistent PPL/NLL')
        rows.append(dict(origin=origin,artifact=artifacts[r['path']],config=c,
            config_sha256=d['configuration_sha256'],code_commit=d['code_commit'],identity_sha256=d['identity_sha256'],
            model_revision=d['model_revision'],tokens_sha256=d['token_ids_sha256_le_int64'],
            targets_sha256=d['scoring_plan']['target_positions_sha256_le_int64'],
            scored_tokens=d['scored_tokens'],ppl=d['perplexity'],mean_nll=d['mean_nll'],
            segments=[dict(segment_id=s['segment_id'],scored_tokens=s['scored_tokens'],nll_sum=s['nll_sum']) for s in d['examples']],
            sampling=d.get('sampling_summary'),execution_audit=a,environment=d['environment'],slurm_job_id=d['slurm_job_id']))
    return rows


def summarize(new,old,upstream):
    fresh=load_own(new,'sample_sweep_c0fd');previous=load_own(old,'joint_suffix_d61')
    # The old none reference is superseded by a freshly rerun identical BF16.
    before=next(r for r in previous if r['config']['ffn']=='none')
    baseline=next(r for r in fresh if r['config']['ffn']=='none')
    if baseline['ppl']!=before['ppl']:raise ValueError('BF16 rerun mismatch')
    entries=[r for r in previous if r['config']['ffn']=='b4_t32']+fresh
    signatures={(r['model_revision'],r['tokens_sha256'],r['targets_sha256']) for r in entries}
    if len(signatures)!=1:raise ValueError('Model or targets differ')
    if upstream['token_sha256']!=baseline['tokens_sha256'] or upstream['target_positions_sha256']!=baseline['targets_sha256']:
        raise ValueError('Published original-FFN tokens/targets differ')
    if upstream['model_revision']!=baseline['model_revision']:
        raise ValueError('Published original-FFN revision differs')
    params=upstream['protocol_parameters']
    if any(params[k]!=v for k,v in dict(context=2048,decode=128,examples=32,batch=8,burn=16.,spacing=4.,budget_blocks=8).items()):
        raise ValueError('Published reference protocol differs')
    lookup={}
    for r in entries:
        c=r['config'];key=(c['ffn'],c['mode'],c['samples'],c['seed'])
        if key in lookup:raise ValueError('Duplicate cell')
        lookup[key]=r
    if len(entries)!=25:raise ValueError('Need15new+9oldFFNcells+freshBF16')
    original={g['samples']:g for g in upstream['groups'] if g['mode']=='screen_ising' and g['selection']=='fixed'}
    original_exact=next(g for g in upstream['groups'] if g['mode']=='screen_exact' and g['selection']=='fixed')
    original_bf16=next(g for g in upstream['groups'] if g['mode']=='sdpa')
    if original_bf16['ppl_mean']!=baseline['ppl']:raise ValueError('Published BF16 baseline differs')
    def aggregate(mode,count):
        values=[lookup[('b4_t32',mode,count,s)] for s in (0,1,2)]
        p=[v['ppl'] for v in values];n=[v['mean_nll'] for v in values]
        return dict(mode=mode,samples=count if mode=='screen_ising' else None,seeds=[0,1,2],
            ppl_mean=statistics.mean(p),ppl_population_sd=statistics.pstdev(p),mean_nll=statistics.mean(n),
            ppl_vs_original_bf16_percent=(math.exp(statistics.mean(n)-baseline['mean_nll'])-1)*100,
            individual_ppl=p)
    curve=[]
    for count in SAMPLES:
        r=aggregate('screen_ising',count);g=original[count]
        r.update(original_ffn_ppl_mean=g['ppl_mean'],original_ffn_ppl_population_sd=g['ppl_seed_population_sd'],
            original_ffn_mean_nll=g['mean_nll'],original_ffn_evidence='PR49 published summary, not rerun in this sweep')
        curve.append(r)
    # The existing128/512 attention-only results are exactly the published rows.
    for count in (128,512):
        oldnone=[r['data'] for r in old['rows'] if r['path'].startswith('suffix/')
                 and r['data'].get('configuration',{}).get('ffn')=='none'
                 and r['data']['configuration'].get('mode')=='screen_ising'
                 and r['data']['configuration']['samples']==count]
        if len(oldnone)!=3 or statistics.mean(d['perplexity'] for d in oldnone)!=original[count]['ppl_mean']:
            raise ValueError('Published reference overlap differs')
    return dict(protocol='suffix',scored_tokens_per_seed=4096,model_revision=baseline['model_revision'],
        token_sha256=baseline['tokens_sha256'],target_positions_sha256=baseline['targets_sha256'],
        fixed_ffn='all24 B4/T32/K32, bothprefill/decode, fixedW8/A8shared64',
        fixed_attention='all24 scoreddecode, fixed8blocks, burn16 spacing4; prefillSDPA',
        baseline_bf16_ppl=baseline['ppl'],ffn_only=aggregate('sdpa',128),curve=curve,
        candidate_exact_reference=dict(joint=aggregate('screen_exact',128),original_ffn_ppl_mean=original_exact['ppl_mean'],
            original_ffn_ppl_population_sd=original_exact['ppl_seed_population_sd'],
            meaning='candidate-exact Softmax/PV reference, not a mathematical PPL bound'),
        source_original_ffn=dict(publication='8dd1b06aa465b3bdaaed60ae321c5362983ae169',execution=upstream['source_commit']),
        individual_results=entries,statistics='arithmetic mean per-seedPPL; populationSD from3seeds, not corpusCI',
        sample_semantics='retained CTMC observations/head/query at16+4*k, not ESS or hardwarecycles',
        scope='onlyPPL; no task benchmarks, training, physicalPPA or newTLM')


def main():
    p=argparse.ArgumentParser();p.add_argument('--new',required=True);p.add_argument('--old',required=True)
    p.add_argument('--upstream',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    values=[json.loads(Path(x).read_text(encoding='utf-8')) for x in (a.new,a.old,a.upstream)]
    r=summarize(*values)
    Path(a.output).write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in r.items() if k!='individual_results'},ensure_ascii=True))
if __name__=='__main__':main()
