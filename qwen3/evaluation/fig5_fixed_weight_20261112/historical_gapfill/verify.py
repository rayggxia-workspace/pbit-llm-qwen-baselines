"""CPU self-test and strict full-result aggregation; never fabricates PPL."""
from pathlib import Path
import argparse,ast,hashlib,json,math,statistics
from plans import full_window_plan,ids_sha256,summarize_records,plan_batches
from prepare import sha

HERE=Path(__file__).resolve().parent
def selftest():
    plan=json.loads((HERE/'PLAN.json').read_text());cases=plan['cases']
    sampled=[c for c in cases if c['mode']=='winner']
    missing={(256,16),(None,16),(None,32),(128,256),(256,256)}
    assert len(cases)==16 and len({c['id'] for c in cases})==16
    assert {(c['k'],c['samples'],c['seed']) for c in sampled}=={(k,s,t) for k,s in missing for t in [0,1,2]}
    assert all(not c['overlay'] for c in cases) and not plan['training']
    reused=json.loads((HERE/'EXISTING_RESULTS.json').read_text())
    have={(None if r['case']['k']==2048 else r['case']['k'],r['case']['samples']) for r in reused['records'] if r['case']['samples']}
    assert len(have)==10 and not (have & missing)
    assert have | missing == {(k,s) for k in [128,256,None] for s in [16,32,64,128,256]}
    rows=full_window_plan(299078)
    assert len(rows)==292 and sum(r['scored_tokens'] for r in rows)==299077
    assert rows[0]['prefill_tokens']==0 and rows[0]['scored_tokens']==2047
    assert rows[1]['prefill_tokens']==1023 and rows[1]['first_target']==2048
    assert [i for r in rows for i in range(r['first_target'],r['end'])]==list(range(1,299078))
    for start in range(0,292,32):
        for batch in plan_batches(rows[start:start+32],32):
            assert len({(r['end']-r['begin'],r['prefill_tokens'],r['scored_tokens']) for r in batch})==1
    for file in HERE.glob('*.py'):ast.parse(file.read_text(encoding='utf-8'),filename=file.name)
    hw=dict(reference='historical Philox kernel copied; GPU replay gate pending')
    # Separate scalar reasoning checks for cold/all-zero/hold/select behavior.
    def step(w,b,rank):
        active=[i for i,x in enumerate(b) if x]
        return w if b[w] or not active else active[rank]
    assert step(0,[0,0,0],0)==0
    assert step(1,[1,1,1],2)==1
    assert step(0,[0,1,1],1)==2
    assert step(0,[0,1,1],0)==1
    assert [math.floor(256/(1+math.exp(a/16))) for a in [0,16,255]]==[128,68,0]
    assert round((1000-999.96875)*16)==0  # RNE half tie; absolute S12 clipping would differ elsewhere.
    assert round((1000-999.90625)*16)==2
    return dict(passed=True,cases=16,stochastic=15,controls=1,reused_sampling_configurations=10,windows=292,targets=299077,
        target_positions_sha256_le_int64=ids_sha256(range(1,299078)),hardware=hw,
        validation='CPU gap coverage/protocol checks only; no new GPU/PPL run')

def collect(root):
    plan=json.loads((HERE/'PLAN.json').read_text());expected=full_window_plan(299078)
    accepted=[];pending=[];identity=None
    for case in plan['cases']:
        path=root/case['id']/'RESULT.json'
        if not path.exists():pending.append(case['id']);continue
        r=json.loads(path.read_text());assert r['complete'] and r['case']==case
        if identity is None:identity=r['identity']
        assert r['identity']==identity
        assert r['original_ffn'] and not r['training'] and r['tokens_per_layer']==[299077]*36
        allrows=[]
        for part in r['parts']:
            p=path.parent/part['file'];assert sha(p)==part['sha256']
            item=json.loads(p.read_text());assert item['identity']==identity and item['case']==case
            assert item['tokens_per_layer']==[item['scored_tokens']]*36
            if case['mode']=='winner':
                assert all(layer['sampled_head_rows']==32*item['scored_tokens'] for layer in item['audit']['layers'].values())
            allrows.extend(item['records'])
        assert allrows==r['records']
        assert [{k:v for k,v in x.items() if k!='nll_sum'} for x in allrows]==expected
        total=summarize_records(allrows)
        assert total['scored_tokens']==299077
        assert math.isclose(total['nll_sum'],r['nll_sum'],rel_tol=0,abs_tol=1e-8)
        assert math.isclose(total['perplexity'],r['perplexity'],rel_tol=1e-12)
        accepted.append(dict(**case,**total,result_sha256=sha(path)))
    groups=[]
    for k in [128,256,None]:
        for s in [16,32,64,128,256]:
            rs=[r for r in accepted if r['mode']=='winner' and r['k']==k and r['samples']==s]
            if len(rs)==3:
                pp=[r['perplexity'] for r in rs]
                groups.append(dict(k=k,samples=s,seeds=[r['seed'] for r in rs],ppl_mean=statistics.mean(pp),ppl_sample_sd=statistics.stdev(pp)))
    return dict(reused=json.loads((HERE/'EXISTING_RESULTS.json').read_text()),complete=len(accepted)==16,accepted=accepted,pending=pending,curves=groups,identity=identity)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results');p.add_argument('--output');a=p.parse_args()
    result=collect(Path(a.results)) if a.results else selftest()
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:Path(a.output).write_text(text,encoding='utf-8')
    print(text)
