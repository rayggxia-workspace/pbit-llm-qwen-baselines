"""Publish and verify the remote-agent handoff; no training or PR merge."""
import base64, concurrent.futures, hashlib, json, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from publish import api, PREFIX, ROOT, BRANCH
OUT=Path(__file__).resolve().parent
assert api('GET','/user')['login']=='jieruiz'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert api('GET',PREFIX+'/git/ref/heads/'+BRANCH)['object']['sha']==head
paths=subprocess.check_output(['git','diff','--name-only','fbc35f45be65fcb96fd495572f2d5b79fa8b161c',head],cwd=ROOT,text=True).splitlines()
def verify(path):
    blob=subprocess.check_output(['git','rev-parse',head+':'+path],cwd=ROOT,text=True).strip()
    expected=subprocess.check_output(['git','show',head+':'+path],cwd=ROOT)
    data=base64.b64decode(api('GET',PREFIX+'/git/blobs/'+blob)['content'])
    assert data==expected
    return dict(path=path,git_blob=blob,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:verified=list(pool.map(verify,paths))
pr=api('PATCH',PREFIX+'/pulls/161',dict(title='Qwen3-4B非Base：W4/W6/W8随机FFN训练与远程Agent执行交接',body=(ROOT/'work/jieruiz/159/PR_BODY.md').read_text(encoding='utf-8')))
assert pr['head']['sha']==head and not pr['merged']
issue=api('GET',PREFIX+'/issues/159')
update='''## 当前范围更新：远程Agent执行交接＋INT4/INT6/INT8

用户要求把方案写给远程执行Agent，并增加INT4/INT6，其余设置保持、工作3倍。每个位宽19项（16随机＋3控制），共57项；B/C/D也在每个位宽执行原预算。每项实验36层所有gate/up/down统一位宽，A8/共享64保持；三份BF16控制是配对重复，不是三种位宽结构。

入口qwen3/training/sc_qat_20261023/REMOTE_AGENT_START_HERE_ZH.md；附环境/逐seed结果模板。PR160已锁非Baserevision 1cfa9a7208912126459214e8b04321603b3df60c，执行前读其最新交接/队列并核验模型artifact，避免重复。

57项清单、三位宽其他设置一致、模板JSON/语法、启动拒绝守卫及独立审阅通过。仍是训练设计交付，本Issue未实现训练器或提交GPU作业；实现方应按交接认领独立执行任务。PR161待审，不自动合并或关闭。

以下保留最初W8设计范围的历史记录：

'''
body=issue['body'] if issue['body'].startswith('## 当前范围更新：远程Agent执行交接') else update+issue['body']
api('PATCH',PREFIX+'/issues/159',dict(title='Qwen3-4B非Base：W4/W6/W8随机FFN训练方案与远程执行交接',body=body))
comment=api('POST',PREFIX+'/issues/159/comments',dict(body='远程Agent执行版已更新PR161，科学提交 `'+head+'`。57项=48随机+9控制；输入仍A8、所有非权重设置跨位宽一致。19个改动文件远端原字节核验通过。入口 `qwen3/training/sc_qat_20261023/REMOTE_AGENT_START_HERE_ZH.md`，含PR160复用、五块待实现代码、120步先导、Slurm和逐seed回传。没有本任务新训练/作业/PPL。Projects仍待权限同步，PR待审未合并。'))
receipt=dict(head=head,pr=pr['html_url'],state=pr['state'],merged=False,
             issue_comment=comment['html_url'],verified_files=verified,
             training_jobs_submitted=0,projects_board='not_updated_existing_permission_gap')
(OUT/'PUBLICATION.json').write_bytes((json.dumps(receipt,ensure_ascii=False,indent=2)+'\n').encode())
entry='''## Issue159 v2已发布（2026-10-23）

远程执行交接与INT4/6/8三套扫描已通过同PR161发布，科学提交12137b19ae6a3e7d862e5785676c200ab6d910fd；19改动文件GitHub原字节回读通过，Issue159范围/进度已同步。PR待审未合并；57项仍是计划，无本任务训练器或GPU结果。完整回执work/jieruiz/159/remote_agent_v2/PUBLICATION.json。入口REMOTE_AGENT_START_HERE_ZH.md可直接交给远程Agent；实现认领与PR160模型/基线复用按该交接执行。其他任务记录保留。

'''
for p in [ROOT/'PROJECT_MEMORY_ZH.md',ROOT/'progress/jieruiz/STATUS.md',ROOT/'work/jieruiz/159/HANDOFF.md']:
    old=p.read_bytes()
    if 'Issue159 v2已发布'.encode() not in old:p.write_bytes(entry.encode()+old)
workspace=ROOT.parents[1];canonical=workspace/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=workspace/'PROJECT_MEMORY_ZH.md'
old=canonical.read_bytes();assert old==mirror.read_bytes()
if 'Issue159 v2已发布'.encode() not in old:
    canonical.write_bytes(entry.encode()+old);mirror.write_bytes(canonical.read_bytes())
print(json.dumps(dict(head=head,verified=len(verified),pr=161,issue_comment=comment['html_url'])))
