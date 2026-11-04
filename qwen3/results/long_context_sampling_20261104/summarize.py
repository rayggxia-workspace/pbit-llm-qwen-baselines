"""Independently verify sealed completed pilot outputs before summarizing."""
import argparse,hashlib,json,math,statistics
from pathlib import Path


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    assert sha(p)==p.with_suffix('.json.sha256').read_text().strip(),str(p)
    return json.loads(p.read_bytes())


def summarize(root):
    rows=[];target_sha=None;identities=set()
    for complete in sorted(root.glob('N*/seed*/COMPLETE.json')):
        manifest=read(complete);assert manifest['status']=='completed'
        for name,digest in manifest['files_sha256'].items():assert sha(complete.parent/name)==digest
        provenance=read(complete.parent/'PROVENANCE.json')
        identities.add((provenance['source_manifest_sha256'],provenance['runtime_sha256'],
                        provenance['prepared_sha256'],provenance['token_ids_sha256']))
        count=0
        for p in sorted(complete.parent.glob('*.json')):
            if p.name in ('PROVENANCE.json','COMPLETE.json'):continue
            v=read(p);assert v['status']=='completed' and v['scored_tokens']==128
            assert v['tokens_per_layer']==[128]*36
            assert v['provenance_sha256']==sha(complete.parent/'PROVENANCE.json')
            plan_sha=v['plan']['target_positions_sha256_le_int64']
            if target_sha is None:target_sha=plan_sha
            assert target_sha==plan_sha,'target sets differ'
            nll=math.fsum(r['nll_sum'] for r in v['records'])
            ppl=math.exp(nll/128)
            assert math.isclose(nll,v['nll_sum'],rel_tol=1e-12)
            assert math.isclose(ppl,v['perplexity'],rel_tol=1e-12)
            sample=v['case']['s']
            if sample:
                assert v['numeric']['probability_calls']==36*128
                for layer in v['audit']['layers'].values():
                    assert layer['decode_queries']==128 and layer['sampled_head_rows']==128*32
                    assert layer['_activity'][0]==sample*128*32
                    assert layer['_activity'][1]==sample*128*32
                    assert layer['zero_fallback']==0
            rows.append(dict(context=v['context_start'],seed=v['seed'],case=v['case']['name'],
                             perplexity=ppl,nll_sum=nll,scored_tokens=128,sha256=sha(p),
                             numeric=v['numeric'],seconds=v['seconds']))
            count+=1
        assert count==manifest['cases']
    assert len(identities)<=1,'mixed source/runtime/model/data'
    grouped={}
    for row in rows:grouped.setdefault((row['context'],row['case']),[]).append(row)
    summary=[]
    for (context,case),items in sorted(grouped.items()):
        values=[x['perplexity'] for x in items]
        summary.append(dict(context=context,case=case,seeds=[x['seed'] for x in items],
                            mean_ppl=statistics.mean(values),
                            deployment_sd=statistics.stdev(values) if len(values)>1 else None))
    return dict(status='completed' if len(rows)==40 else 'partial',results=len(rows),expected=40,
                completed_tasks=len(list(root.glob('N*/seed*/COMPLETE.json'))),expected_tasks=6,
                target_positions_sha256=target_sha,summary=summary,rows=rows,
                scope='128-target matched suffix PPL; not full WT2, not PPA; accurate FFN/prefill')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();v=summarize(a.root);text=json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n'
    if a.output:a.output.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({k:v[k] for k in ('status','results','expected','completed_tasks','summary')},ensure_ascii=False))
