"""Read-only independent reaggregation of completed official task documents."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path


def sha(raw):return hashlib.sha256(raw).hexdigest()


def canon(value):return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    index={}
    def read(p):
        raw=p.read_bytes();assert sha(raw)==p.with_suffix('.sha256').read_text().strip(),str(p)
        index[str(p.relative_to(a.root))]=dict(sha256=sha(raw),bytes=len(raw))
        return json.loads(raw)
    summary=read(a.root/'SUMMARY.json');gate=read(a.root/'gate/RESULT.json')
    assert summary['status']==gate['status']=='completed'
    assert (summary['completed_parts'],summary['completed_groups'])==(225,18)
    assert not summary['failed'] and not summary['missing']
    assert summary['provenance']==gate['provenance']
    manifest=summary['provenance']['source']
    for name,digest in manifest['files'].items():assert sha((a.root/'source'/name).read_bytes())==digest,name
    groups={};paired={};scored=0
    for group in summary['groups']:
        name=group['task'];case=group['case'];seen={};durations=0
        for item,digest in group['part_result_sha256'].items():
            p=a.root/'parts'/item/'RESULT.json';assert sha(p.read_bytes())==digest
            z=read(p);official=read(p.parent/'OFFICIAL_RESULT.json')
            assert z['status']=='completed' and z['case']==case and z['task']==name and z['seed']==101
            expected=summary['native_identity'] if case['policy']=='BF16' else summary['T64_identity']
            assert z['identity']==expected and z['provenance']==summary['provenance']
            assert sha((p.parent/'OFFICIAL_RESULT.json').read_bytes())==z['official_sha256']
            documents={int(x['doc_id']):x['sha256'] for x in z['document_identity']['documents']}
            assert set(documents)==set(range(z['doc_start'],z['doc_end']))
            audit=z['audit'];ledger=audit['input_batch_ledger']
            assert audit['layers']==36 and audit['all_prompt_and_answer_positions_covered'] and not audit['prefix_exception']
            assert len(ledger)==audit['model_calls']
            assert sum(math.prod(x['shape']) for x in ledger)==audit['input_tokens_per_layer']
            assert sha((json.dumps(ledger,separators=(',',':'))+'\n').encode())==audit['input_batch_ledger_sha256']
            key=(name,z['doc_start']);identity=(z['document_identity']['sha256'],audit['input_batch_ledger_sha256'])
            if key in paired:assert paired[key]==identity
            else:paired[key]=identity
            samples=official['samples'][name]
            assert len(samples)==z['documents']==len(documents)
            for sample in samples:
                doc_id=int(sample['doc_id']);assert doc_id not in seen and doc_id in documents
                assert sha(canon(sample['doc']))==documents[doc_id]
                values={k:float(sample[k]) for k in ['acc','acc_norm']}
                assert all(v in (0.,1.) for v in values.values())
                seen[doc_id]=values
            for key,value in z['metrics'].items():
                assert math.isclose(sum(float(s[key.split(',')[0]]) for s in samples)/len(samples),value,abs_tol=1e-14)
            durations+=z['seconds']
        assert len(seen)==group['documents'] and set(seen)==set(range(group['documents']))
        expected_count={'piqa':1838,'arc_challenge':1172}[name];assert len(seen)==expected_count
        metrics={k+',none':sum(x[k] for x in seen.values())/len(seen) for k in ['acc','acc_norm']}
        for key in metrics:assert math.isclose(metrics[key],group['metrics'][key],abs_tol=1e-14)
        assert math.isclose(durations,group['seconds'],abs_tol=1e-9)
        groups[(case['id'],name)]=dict(case=case,task=name,documents=len(seen),metrics=metrics,per_doc=seen)
        scored+=len(seen)
    rows=[]
    for (case_id,name),g in groups.items():
        c=g['case'];ref=groups[('lane_'+str(c['T_x'])+'_'+str(c['T_and']),name)] if c['policy']!='BF16' else None
        row={k:v for k,v in g.items() if k!='per_doc'}
        if ref:
            row['delta_pp_vs_matching_T64_lane']={k:100*(g['metrics'][k]-ref['metrics'][k]) for k in g['metrics']}
            row['paired_acc_changes']=dict(improved=sum(g['per_doc'][i]['acc']>ref['per_doc'][i]['acc'] for i in g['per_doc']),
                worsened=sum(g['per_doc'][i]['acc']<ref['per_doc'][i]['acc'] for i in g['per_doc']))
        rows.append(row)
    result=dict(status='verified',job=os.environ['SLURM_JOB_ID'],source_commit=manifest['git_commit'],
                verifier_sha256=sha(Path(__file__).read_bytes()),parts=225,groups=18,configuration_document_pairs=scored,
                original_documents_and_official_scores_recomputed=True,full_input_ledgers_and_model_identities_verified=True,
                rows=rows,source_artifacts=index)
    assert scored==9*(1838+1172)
    a.output.parent.mkdir(parents=True,exist_ok=True);assert not a.output.exists()
    raw=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode();a.output.write_bytes(raw)
    a.output.with_suffix('.sha256').write_bytes((sha(raw)+'\n').encode())
    print(json.dumps({k:result[k] for k in ['status','parts','groups','configuration_document_pairs']}))


if __name__=='__main__':main()
