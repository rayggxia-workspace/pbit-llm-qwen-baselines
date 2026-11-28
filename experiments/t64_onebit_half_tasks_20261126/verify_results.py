"""Read-only independent S2/S4 per-document and input-ledger audit."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canon(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))+'\n').encode()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('s2', type=Path)
    ap.add_argument('s4', type=Path)
    ap.add_argument('output', type=Path)
    a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    artifacts={}
    def read(root, label, path):
        p=root/path
        raw=p.read_bytes()
        assert sha(raw)==p.with_suffix('.sha256').read_text().strip(), str(p)
        artifacts[label+'/'+path]=dict(sha256=sha(raw), bytes=len(raw))
        return json.loads(raw)
    def audit(root, label, expected_parts, expected_groups):
        s=read(root,label,'SUMMARY.json')
        g=read(root,label,'gate/RESULT.json')
        assert s['status']==g['status']=='completed'
        assert (s['completed_parts'],s['expected_parts'],s['completed_groups'],s['expected_groups'])==(expected_parts,expected_parts,expected_groups,expected_groups)
        assert not s['missing'] and not s['failed'] and s['provenance']==g['provenance']
        for name,digest in s['provenance']['source']['files'].items():
            assert sha((root/'source'/name).read_bytes())==digest, name
        groups={};ledgers={};scored=0
        for group in s['groups']:
            task=group['task'];case=group['case'];seen={};seconds=0.
            for item,digest in group['part_result_sha256'].items():
                path='parts/'+item+'/RESULT.json'
                z=read(root,label,path)
                assert artifacts[label+'/'+path]['sha256']==digest
                assert z['status']=='completed' and z['seed']==101 and z['case']==case and z['task']==task
                assert z['provenance']==s['provenance']
                identity=s['native_identity'] if case['policy']=='BF16' else s['T64_identity']
                assert z['identity']==identity
                official=read(root,label,'parts/'+item+'/OFFICIAL_RESULT.json')
                assert artifacts[label+'/parts/'+item+'/OFFICIAL_RESULT.json']['sha256']==z['official_sha256']
                docs={int(x['doc_id']):x['sha256'] for x in z['document_identity']['documents']}
                assert set(docs)==set(range(z['doc_start'],z['doc_end']))
                assert sha((json.dumps(z['document_identity']['documents'],separators=(',',':'))+'\n').encode())==z['document_identity']['sha256']
                audit=z['audit'];ledger=audit['input_batch_ledger']
                assert audit['layers']==36 and audit['all_prompt_and_answer_positions_covered'] and not audit['prefix_exception']
                assert len(ledger)==audit['model_calls']
                assert sum(math.prod(x['shape']) for x in ledger)==audit['input_tokens_per_layer']
                assert sha((json.dumps(ledger,separators=(',',':'))+'\n').encode())==audit['input_batch_ledger_sha256']
                key=(task,z['doc_start'])
                pair=(z['document_identity']['sha256'],audit['input_batch_ledger_sha256'])
                if key in ledgers: assert ledgers[key]==pair
                else: ledgers[key]=pair
                samples=official['samples'][task]
                assert len(samples)==z['documents']==len(docs)
                for sample in samples:
                    i=int(sample['doc_id'])
                    assert i in docs and i not in seen and sha(canon(sample['doc']))==docs[i]
                    metrics={k:float(sample[k]) for k in ['acc','acc_norm']}
                    assert all(v in (0.,1.) for v in metrics.values())
                    seen[i]=metrics
                for k,v in z['metrics'].items():
                    assert math.isclose(sum(x[k.split(',')[0]] for x in samples)/len(samples),v,abs_tol=1e-14)
                seconds+=z['seconds']
            count={'piqa':1838,'arc_challenge':1172}[task]
            assert len(seen)==count==group['documents'] and set(seen)==set(range(count))
            metrics={k+',none':sum(x[k] for x in seen.values())/count for k in ['acc','acc_norm']}
            for k in metrics: assert math.isclose(metrics[k],group['metrics'][k],abs_tol=1e-14)
            assert math.isclose(seconds,group['seconds'],abs_tol=1e-9)
            groups[(case['id'],task)]=dict(case=case,task=task,documents=count,metrics=metrics,per_doc=seen)
            scored+=count
        return s,g,groups,ledgers,scored
    s2,g2,r2,l2,n2=audit(a.s2,'S2',100,8)
    s4,g4,r4,l4,n4=audit(a.s4,'S4',225,18)
    assert l2==l4 and s2['T64_identity']==s4['T64_identity'] and s2['native_identity']==s4['native_identity']
    for k in ['protocol','task_identity','harness']: assert s2['provenance'][k]==s4['provenance'][k],k
    rows=[]
    for (case_id,task),v in r2.items():
        assert case_id.startswith('S2_')
        ref=r4[(case_id[3:],task)]
        assert dict(v['case'],id=case_id[3:])==ref['case']
        changes={}
        for k in ['acc','acc_norm']:
            improved=sum(v['per_doc'][i][k]>ref['per_doc'][i][k] for i in v['per_doc'])
            worsened=sum(v['per_doc'][i][k]<ref['per_doc'][i][k] for i in v['per_doc'])
            assert math.isclose((improved-worsened)/v['documents'],v['metrics'][k+',none']-ref['metrics'][k+',none'],abs_tol=1e-14)
            changes[k]=dict(improved=improved,worsened=worsened)
        rows.append(dict(case=v['case'],task=task,documents=v['documents'],S4=ref['metrics'],S2=v['metrics'],
                         delta_pp={k:100*(v['metrics'][k]-ref['metrics'][k]) for k in v['metrics']},paired_changes=changes))
    assert (n2,n4)==(12040,27090)
    result=dict(status='verified',job=os.environ['SLURM_JOB_ID'],verifier_sha256=sha(Path(__file__).read_bytes()),
                S2_parts=100,S2_groups=8,S4_control_parts=225,S4_control_groups=18,
                S2_scored_pairs=n2,S4_scored_pairs=n4,paired_document_and_input_ledgers_equal=True,
                source_and_model_identities_verified=True,original_document_scores_recomputed=True,
                S2_source_commit=s2['provenance']['source']['git_commit'],S4_source_commit=s4['provenance']['source']['git_commit'],
                rows=rows,source_artifacts=artifacts)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    assert not a.output.exists()
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode()
    a.output.write_bytes(raw)
    a.output.with_suffix('.sha256').write_bytes((sha(raw)+'\n').encode())
    print(json.dumps({k:result[k] for k in ['status','S2_parts','S2_groups','S2_scored_pairs','S4_scored_pairs']}))

if __name__=='__main__':
    main()
