"""Read completed sealed suffix cases; do not treat these as full WT2."""
import hashlib,json,math,statistics,sys
from pathlib import Path

def collect(folder):
    folder=Path(folder);rows=[];identities=set();targets=set()
    for p in sorted(folder.glob('*.json')):
        b=p.read_bytes();sha=hashlib.sha256(b).hexdigest()
        assert sha==p.with_suffix('.json.sha256').read_text().strip()
        r=json.loads(b);c=r['configuration'];audit=r['execution_audit']
        assert r['status']=='completed' and r['protocol']=='suffix'
        assert r['scored_tokens']==4096 and r['code_commit']=='7a286ec140de6846006c96456275377fd22b4943'
        assert audit['every_scored_target_executed_all_24_layers'] and audit['every_scored_target_executed_all_24_ffns']
        assert audit['ffn_decode_tokens_per_layer']==[4096]*24
        assert len(audit['decode_calls_per_layer'])==24 and len(set(audit['decode_calls_per_layer']))==1
        assert math.isclose(r['perplexity'],math.exp(r['nll_sum']/r['scored_tokens']),rel_tol=1e-12)
        assert hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()==r['configuration_sha256']
        identities.add(r['identity_sha256']);targets.add(r['token_ids_sha256_le_int64'])
        rows.append(dict(name=c['name'],seed=c['seed'],method=c['name'].rsplit('_s',1)[0],
            ppl=r['perplexity'],nll_sum=r['nll_sum'],seconds=r['elapsed_seconds'],
            sha256=sha,path=str(p),configuration_sha256=r['configuration_sha256']))
    assert len(rows)==len({r['name'] for r in rows})==16 and len(identities)==len(targets)==1
    summaries={}
    for name in ('bf16','ffn_only','screen_exact','ctmc128','rejection128','winner1024'):
        group=[r for r in rows if r['method']==name]
        assert sorted(r['seed'] for r in group)==([0] if name=='bf16' else [0,1,2])
        vals=[r['ppl'] for r in group]
        summaries[name]=dict(mean_ppl=statistics.mean(vals),population_sd=statistics.pstdev(vals),
            seeds=len(vals),mean_seconds=statistics.mean(r['seconds'] for r in group))
    return dict(status='verified_completed_suffix_only',protocol='32 segments x 128 targets, context2048 batch8',
        targets=4096,identity_sha256=next(iter(identities)),token_sha256=next(iter(targets)),rows=rows,summary=summaries,
        caveats=['not full WT2','winner uses 1024 correlated updates versus 128 accepted/observed samples',
        'ideal FP32 independent proposals, no physical RNG/q256','three seed SD is not dataset uncertainty'])

if __name__=='__main__':
    result=collect(sys.argv[1]);out=Path(sys.argv[2])
    if out.exists():raise FileExistsError(out)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result['summary'],indent=2))
