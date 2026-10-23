"""Publish an archived Issue157 checkpoint; importing performs no API calls."""
import json, sys
from pathlib import Path
from archive_checkpoint import (ROOT,TREE,REPO,load,digest,valid_label,
    progress_text,scheduler_state,scheduler_text,benchmark_text,gate_text)


def descriptions(report,state,label,repo=REPO):
    key=report['identity']['source_commit'][:12]
    link=f'https://github.com/{repo}/blob/task/157-sparq-qwen3/qwen3/sparq/results/{key}/reviews/{label}/REVIEW_ZH.md'
    progress,conclusion=progress_text(report); schedule=scheduler_text(state)
    body=f'''后训练 **Qwen/Qwen3-4B** 的匹配 BF16 与 SparQ 基线，替换本任务入口的 max4/小网络筛选；原 FFN 和准确候选 softmax/PV 保留。关联 #157，依赖 #147@357db588；本 helper 不合并或更改 PR 状态。

主配置 GQA probability-sum、r32/k_total128/local_total32；论文 v6 与固定官方源码差异单独记录。所有计分目标走缓存单 query 路径，36 层 QK-Norm/RoPE/GQA 均审计。

当前交付：[{label} 独立结果复核]({link})，状态 **{report['status']}**。原执行提交 `{report['identity']['source_commit']}`；完成分片的 envelope/TRANSFER 和固定源码 SHA 均复核，旧检查点保持不变。

{progress}

{conclusion}

{benchmark_text(report)}

{schedule}

{gate_text(report)}

硬件账本含双 K 布局、追加写和选择器；[EDA 交接](https://github.com/{repo}/blob/task/157-sparq-qwen3/architecture_tlm/sparq_baseline/EDA_HANDOFF_ZH.md)已通知 jieruiz。完整 SparQ RTL 顶层/STA 尚未实现，物理 ASIC 面积、功率、真实延迟仍为 null。Issue116/123 继续暂停；恢复入口 `work/amlink1219/157/HANDOFF.md`。
'''
    marker='<!-- sparq-157-current-results -->'
    stage=f'''{marker}
阶段结果：[{label} 独立复核]({link})，状态 `{report['status']}`，固定执行 `{key}`。

{schedule}

{progress}

{conclusion}

{benchmark_text(report)}

{gate_text(report)}

物理 ASIC PPA 仍为 null；原始分片与固定源 SHA 随 PR163 提供，未自动合并。
'''
    return dict(link=link,pr_body=body,issue_marker=marker,issue_stage=stage)


def checked_report(label,root=ROOT,tree=TREE):
    valid_label(label); review=Path(root)/('review_'+label)
    hashes=load(review/'CHECKPOINT_REPORTS.json')
    if set(hashes)!={'REVIEW.json','REVIEW_ZH.md'}: raise ValueError('invalid immutable report hashes')
    for name,checksum in hashes.items():
        if digest(review/name)!=checksum: raise ValueError('review changed after archival: '+name)
    report=load(review/'REVIEW.json'); key=report['identity']['source_commit'][:12]
    target=Path(tree)/'qwen3/sparq/results'/key/'reviews'/label
    for name in ('REVIEW.json','REVIEW_ZH.md','CHECKPOINT_INPUTS.json','CHECKPOINT_REPORTS.json'):
        if (target/name).read_bytes()!=(review/name).read_bytes(): raise ValueError('report not identically archived: '+name)
    if report['identity']['source_commit']!=load(Path(root)/'FULL_V2_EXECUTION.json')['commit']:
        raise ValueError('report belongs to another execution')
    return report


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv==['--self-test']: return self_test()
    if len(argv)!=1: raise SystemExit('usage: publish_checkpoint_stage.py LABEL | --self-test')
    label=valid_label(argv[0]); report=checked_report(label)
    state=scheduler_state(ROOT,load(ROOT/'GPU_FULL_V2_JOB.json')['job'])
    text=descriptions(report,state,label)
    # Authentication and network mutation only happen after explicit invocation.
    import control
    if control.REPO!=REPO: raise ValueError('publication target is not canonical workspace')
    client=control.client(); base='https://api.github.com/repos/'+REPO+'/'
    def get(path):
        response=client.get(base+path,timeout=45); response.raise_for_status(); return response.json()
    publication=load(ROOT/'PUBLICATION.json'); pr=get('pulls/163')
    if pr['head']['sha']!=publication['head'] or pr['state']!='open' or pr.get('merged'):
        raise ValueError('PR changed/closed/merged; inspect before updating')
    # Verify uploaded immutable report bytes at the recorded head, not just a link.
    import base64
    key=report['identity']['source_commit'][:12]
    for name in ('REVIEW.json','REVIEW_ZH.md','CHECKPOINT_INPUTS.json','CHECKPOINT_REPORTS.json'):
        path=f'qwen3/sparq/results/{key}/reviews/{label}/{name}'
        item=get('contents/'+path+'?ref='+publication['head'])
        if item.get('encoding')!='base64' or base64.b64decode(item['content'])!=(ROOT/('review_'+label)/name).read_bytes():
            raise ValueError('published checkpoint bytes differ: '+name)
    body=text['pr_body']
    control.save('PR_CHECKPOINT_'+label+'_INTENT.json',dict(number=163,body=body,scheduler=state))
    if pr.get('body')!=body:
        response=client.patch(base+'pulls/163',json={'body':body},timeout=45); response.raise_for_status()
    if get('pulls/163')['body']!=body: raise ValueError('PR body readback differs; inspect intent before retry')
    issue=get('issues/157'); old=issue.get('body') or ''
    if text['issue_marker'] in old: old=old.split(text['issue_marker'])[0].rstrip()
    new=old+'\n\n'+text['issue_stage']
    control.save('ISSUE_CHECKPOINT_'+label+'_INTENT.json',dict(number=157,body=new,scheduler=state))
    if issue.get('body')!=new:
        response=client.patch(base+'issues/157',json={'body':new},timeout=45); response.raise_for_status()
    if get('issues/157')['body']!=new: raise ValueError('Issue body readback differs; inspect intent before retry')
    result=dict(head=publication['head'],pr=publication['pr'],report=text['link'],review_status=report['status'],scheduler=state)
    control.save('CHECKPOINT_'+label+'_PUBLICATION.json',result)
    print(json.dumps(result,ensure_ascii=False))


def self_test():
    import copy, unittest
    def fixture(complete):
        ppl=dict(verified_windows=292 if complete else 192,expected_windows=292,scored_tokens=299077 if complete else 197631,
                 perplexity=7.,verified_complete=complete)
        task=dict(verified_documents=1838 if complete else 256,expected_documents=1838,verified_complete=complete,
                  metrics_from_official_rows=dict(acc=.7,acc_norm=.71))
        return dict(identity=dict(source_commit='8d60abe4e7c5'+'a'*28),complete=complete,
            status='complete_verified' if complete else 'partial_verified',final_SUMMARY_present=complete,formal_task_document_batch=1,
            ppl=dict(modes={m:copy.deepcopy(ppl) for m in ('dense','sparq')}),
            vectorized_anchor=dict(verified_windows=292,expected_windows=292,perplexity=11.5,verified_complete=True),
            tasks=dict(piqa=dict(modes={m:copy.deepcopy(task) for m in ('dense','sparq')})),
            benchmark=dict(present=False,verified_complete=complete),
            gates=dict(preflight=dict(passed=True),document_batch_gate=dict(present=True,passed=False,
                reported_failures=[dict(task='arc_easy',mode='dense',maximum=.413,threshold=.02)])))
    class Tests(unittest.TestCase):
        def test_partial_running_dynamic_and_failure_preserved(self):
            value=descriptions(fixture(False),dict(job='2878',state='RUNNING',exit_code='0:0'),'p192')
            for body in (value['pr_body'],value['issue_stage']):
                self.assertIn('192/292',body); self.assertIn('256/1838',body); self.assertIn('不是全 WT2',body)
                self.assertIn('passed=False',body); self.assertIn('0.413',body); self.assertNotIn('64窗',body)
        def test_complete_has_no_stale_running_claim(self):
            value=descriptions(fixture(True),dict(job='2878',state='COMPLETED',exit_code='0:0'),'done')
            for body in (value['pr_body'],value['issue_stage']):
                self.assertIn('全部请求的质量部件和正式门禁已核验',body); self.assertIn('COMPLETED',body)
                self.assertNotIn('仍在运行',body); self.assertNotIn('三任务未全部完成',body)
                self.assertIn('物理 ASIC',body); self.assertIn('passed=False',body)
        def test_failed_partial_stays_partial(self):
            value=descriptions(fixture(False),dict(job='2878',state='TIMEOUT',exit_code='0:0'),'timeout')
            self.assertIn('TIMEOUT',value['pr_body']); self.assertIn('尚未完整核验',value['pr_body'])
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful(): raise SystemExit(1)


if __name__=='__main__': main()
