"""CPU self-test and strict full-result aggregation; never fabricates PPL."""
from pathlib import Path
import argparse,ast,hashlib,json,math,statistics
from plans import full_window_plan,ids_sha256,summarize_records,plan_batches
from prepare import sha

HERE=Path(__file__).resolve().parent
def selftest():
    plan=json.loads((HERE/'PLAN.json').read_text());cases=plan['cases']
    sampled=[c for c in cases if c['mode']=='winner']
    assert len(cases)==41 and len({c['id'] for c in cases})==41
    assert {(c['k'],c['samples'],c['seed']) for c in sampled}=={(k,s,t) for k in [128,256,None] for s in [32,64,128,256] for t in [0,1,2]}
    assert all(c['overlay'] for c in sampled) and not plan['training']
    rows=full_window_plan(299078)
    assert len(rows)==292 and sum(r['scored_tokens'] for r in rows)==299077
    assert rows[0]['prefill_tokens']==0 and rows[0]['scored_tokens']==2047
    assert rows[1]['prefill_tokens']==1023 and rows[1]['first_target']==2048
    assert [i for r in rows for i in range(r['first_target'],r['end'])]==list(range(1,299078))
    for start in range(0,292,32):
        for batch in plan_batches(rows[start:start+32],32):
            assert len({(r['end']-r['begin'],r['prefill_tokens'],r['scored_tokens']) for r in batch})==1
    for file in HERE.glob('*.py'):ast.parse(file.read_text(encoding='utf-8'),filename=file.name)
    from test_hardware import cpu_gate
    hw=cpu_gate()
    # Exercise the scalar 11-bit word extension without importing CUDA dependencies.
    import numpy as np
    tree=ast.parse((HERE/'hardware_rng.py').read_text())
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('mix_cpu','initial','biv_cpu')]
    namespace=dict(np=np,MASK=(1<<64)-1)
    exec(compile(ast.Module(body=funcs,type_ignores=[]),'scalar_rng','exec'),namespace)
    _,initial=namespace['initial'](1,2048,709)
    state=initial[0].tolist();wide=[]
    for _ in range(64):
        r8,s8=namespace['biv_cpu'](state,8)
        r11,s11=namespace['biv_cpu'](state,11)
        assert r8==(r11&255) and s8==s11
        wide.append(r11);state=s11
    assert max(wide)>255 and min(wide)>=0 and max(wide)<2048
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
    return dict(passed=True,cases=41,stochastic=36,controls=5,windows=292,targets=299077,
        target_positions_sha256_le_int64=ids_sha256(range(1,299078)),hardware=hw,
        validation='CPU protocol/coverage/GF XOR-map checks only; GPU gate and full PPL pending')

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
        for s in [32,64,128,256]:
            rs=[r for r in accepted if r['mode']=='winner' and r['k']==k and r['samples']==s]
            if len(rs)==3:
                pp=[r['perplexity'] for r in rs]
                groups.append(dict(k=k,samples=s,seeds=[r['seed'] for r in rs],ppl_mean=statistics.mean(pp),ppl_sample_sd=statistics.stdev(pp)))
    return dict(complete=len(accepted)==41,accepted=accepted,pending=pending,curves=groups,identity=identity)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results');p.add_argument('--output');a=p.parse_args()
    result=collect(Path(a.results)) if a.results else selftest()
    text=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:Path(a.output).write_text(text,encoding='utf-8')
    print(text)
