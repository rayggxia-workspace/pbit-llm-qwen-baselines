"""Verify sealed official per-document scores before aggregating full tasks."""
import argparse
import hashlib
import json
from pathlib import Path
from runner import OWN,work_items,cases


def sealed(p):
    raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==p.with_suffix('.sha256').read_text().strip(),str(p)
    return json.loads(raw)


def save(p,v):
    raw=(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
    p.write_bytes(raw);p.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest()+'\n').encode())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);a=ap.parse_args();r=a.root
    plan=json.loads((OWN/'PLAN.json').read_bytes());jobs=work_items(plan)
    gate=r/'gate/RESULT.json'
    if not gate.exists():
        save(r/'SUMMARY.json',dict(status='blocked',reason='gate_not_completed',expected_parts=len(jobs)))
        return
    g=sealed(gate);assert g['status']=='completed'
    parts=[];missing=[];failed=[]
    ledgers={}
    for item in jobs:
        p=r/'parts'/item['id']/'RESULT.json'
        if not p.exists():
            (failed if (r/'claims'/item['id']/'FAILED.json').exists() else missing).append(item['id']);continue
        z=sealed(p);assert z['status']=='completed' and z['provenance']==g['provenance']
        assert z['case']==item['case'] and z['seed']==plan['seed']
        expected_identity=g['native_identity'] if item['case']['policy']=='BF16' else g['identity']
        assert z['identity']==expected_identity
        official=sealed(p.parent/'OFFICIAL_RESULT.json')
        assert hashlib.sha256((p.parent/'OFFICIAL_RESULT.json').read_bytes()).hexdigest()==z['official_sha256']
        samples=official['samples'][item['task']]
        assert len(samples)==item['end']-item['start']==z['documents']
        assert {int(s['doc_id']) for s in samples}==set(range(item['start'],item['end']))
        assert z['audit']['layers']==36 and z['audit']['all_prompt_and_answer_positions_covered'] is True
        assert z['audit']['prefix_exception'] is False
        for key,value in z['metrics'].items():
            assert abs(sum(s[key.split(',')[0]] for s in samples)/len(samples)-value)<1e-12
        key=(item['task'],item['start'])
        pair=(z['document_identity']['sha256'],z['audit']['input_batch_ledger_sha256'])
        if key in ledgers:assert ledgers[key]==pair,'paired data/model-call mismatch'
        else:ledgers[key]=pair
        parts.append(dict(item=item,value=z,samples=samples))
    groups=[]
    for c in cases(plan):
        for name,t in plan['tasks'].items():
            expected=[j for j in jobs if j['case']['id']==c['id'] and j['task']==name]
            found=[x for x in parts if x['item'] in expected]
            if len(found)!=len(expected):continue
            samples=[s for x in found for s in x['samples']]
            assert len(samples)==t['count'] and {int(s['doc_id']) for s in samples}==set(range(t['count']))
            metrics={k:sum(s[k.split(',')[0]] for s in samples)/len(samples) for k in found[0]['value']['metrics']}
            groups.append(dict(case=c,task=name,documents=len(samples),metrics=metrics,
                seconds=sum(x['value']['seconds'] for x in found),
                part_result_sha256={x['item']['id']:hashlib.sha256((r/'parts'/x['item']['id']/'RESULT.json').read_bytes()).hexdigest() for x in found}))
    result=dict(status='completed' if len(parts)==len(jobs) else 'incomplete',seed=plan['seed'],
                expected_parts=len(jobs),completed_parts=len(parts),expected_groups=len(cases(plan))*len(plan['tasks']),
                completed_groups=len(groups),missing=missing,failed=failed,groups=groups,
                provenance=g['provenance'],native_identity=g['native_identity'],T64_identity=g['identity'],
                coverage='all prompt and answer positions;36layers;no prefix exemption',
                paired_input_batch_and_document_ledgers_identical=True)
    save(r/'SUMMARY.json',result)
    lines=['# T64共享尺度任务准确率','',f'状态：{result["status"]}；完整配置{len(groups)}/18，封存分片{len(parts)}/{len(jobs)}。单seed101。',
           '','|配置|PIQA acc / acc_norm|ARC-C acc / acc_norm|','|---|---:|---:|']
    for c in cases(plan):
        cells=[]
        for name in plan['tasks']:
            z=next((x for x in groups if x['case']['id']==c['id'] and x['task']==name),None)
            cells.append('未完整' if z is None else ' / '.join(f'{100*z["metrics"][k]:.3f}%' for k in ['acc,none','acc_norm,none']))
        lines.append('|'+c['id']+'|'+'|'.join(cells)+'|')
    lines += ['','T64/W8、准确SDPA Attention。主尺度效果比较与相同预算lane原四档对照；BF16原预训练仅作参考。三候选×两预算、PIQA1838及ARC-C1172完整集，无训练、不加聊天模板、不截断。进行中／失败不作为完整成绩。']
    (r/'REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','completed_parts','expected_parts','completed_groups','expected_groups']}))


if __name__=='__main__':main()
