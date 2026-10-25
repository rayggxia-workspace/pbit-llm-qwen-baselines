"""Record confirmed PR180 merge; does not change the runtime or results."""
from pathlib import Path
import hashlib,json
import github as g

r=json.loads((g.OUT/'MERGE_VERIFIED.json').read_text(encoding='utf-8'))
assert r['same_tree'] and r['merge_sha']=='5273e5d9fdae811a714f1a278fee6e776c5675af'
note=f'''## Issue179 / PR180 已实际合入 main（2026-10-24）

PR180于{r['merged_at']}合并，main提交`{r['merge_sha']}`，交付head`{r['head']}`；GitHub父节点/文件树及109个变更blob核验通过。Issue179本轮统一TLM交付完成，后续研究缺口不冒充已验证。

统一入口`python -m architecture_tlm`；流程/宏/数制见`architecture_tlm/unified_v6/FFN_CURRENT_ZH.md`，结果见`RESULTS_CURRENT_ZH.md`。74检查、7组完整36层、8组单FFN敏感性、15组三seed夹具、12封存SHA均通过。实际校正拒绝1152行/147456输出/441346 proposals（平均2.993次），无运行中本任务作业。2K准确Attention/筛选PV/筛选拒绝整机条件时间分别1412.979/1366.264/1585.054 ms/token。

保留未知边界：GU定点编译/舍入、NL独立随机源映射、权重保持宏和代表性STA/PPA；完整面积/能耗null，DRAM本轮link非DRAMSys，不继承PPL。Projects缺read:project，待维护者同步。工作副本回收时以project_archives/latest_ffn_tlm_issue179_20261024/RECOVERY.json恢复；本轮不创建全量副本。其他训练/算法PR未被本任务合并。

'''
workspace=Path('C:/Users/86134/Documents/a_P_BIT')
canonical=workspace/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
root=workspace/'PROJECT_MEMORY_ZH.md'
original=canonical.read_bytes();assert original==root.read_bytes()
if not original.startswith(note.encode()):original=note.encode()+original
for p in (canonical,root,g.ROOT/'PROJECT_MEMORY_ZH.md'):p.write_bytes(original)
status=g.ROOT/'progress/jieruiz/STATUS.md'
status.write_bytes(('已合并：PR180 → main，2026-10-24T14:41:06Z，提交5273e5d9fdae811a714f1a278fee6e776c5675af。全部验证与远端blob核验完成，无本任务运行中作业；Projects待权限。准确回执见work/jieruiz/179/MERGE_VERIFIED.json。\n\n').encode()+status.read_bytes())
handoff=g.OUT/'HANDOFF.md'
handoff.write_bytes(('实际交付完成：PR180已合入main，merge5273e5d9fdae811a714f1a278fee6e776c5675af；head0d97e2b5a2c01270568835964b2f4d581133a197。无运行中本任务进程；以下合并前条件文字由本行及MERGE_VERIFIED回执更新。\n\n').encode()+handoff.read_bytes())
issue=g.api('GET',g.PREFIX+'/issues/179')
body=issue['body'].replace('- [ ]','- [x]')
body+='\n\n最终验收：PR180已合并至main `'+r['merge_sha']+'`。74检查、7完整模型、8单FFN敏感性、15三seed夹具、12封存SHA与109远端blob核验通过；不是PPL或RTL/PPA验收。Projects缺read:project，待维护者同步。'
updated=g.api('PATCH',g.PREFIX+'/issues/179',dict(body=body,state='closed',state_reason='completed'))
comments=g.api('GET',g.PREFIX+'/issues/179/comments')
tag='<!-- issue179-final-merge -->'
comment=next((c for c in comments if tag in c['body']),None)
comment_body=tag+'\n'+note+'\n完整报告：[RESULTS_CURRENT_ZH.md](https://github.com/'+g.REPO+'/blob/main/architecture_tlm/unified_v6/RESULTS_CURRENT_ZH.md)。'
if comment:comment=g.api('PATCH',g.PREFIX+'/issues/comments/'+str(comment['id']),dict(body=comment_body))
else:comment=g.api('POST',g.PREFIX+'/issues/179/comments',dict(body=comment_body))
g.save('ISSUE_FINAL.json',dict(issue=updated['html_url'],state=updated['state'],comment=comment['html_url'],merge=r['merge_sha']))
g.save('MEMORY_SYNC.json',dict(sha256=hashlib.sha256(original).hexdigest(),bytes=len(original),canonical=str(canonical),root=str(root)))
print('Issue closed, merge verified, canonical/root/task memory identical')
