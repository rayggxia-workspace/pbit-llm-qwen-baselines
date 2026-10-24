"""Verify published design bytes and synchronize Issue159; no training or merge."""
import base64, concurrent.futures, hashlib, json, subprocess
from pathlib import Path
from publish import api, PREFIX, ROOT, OUT, BASE, BRANCH, save

assert api('GET','/user')['login']=='jieruiz'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert api('GET',PREFIX+'/git/ref/heads/'+BRANCH)['object']['sha']==head
paths=subprocess.check_output(['git','diff','--name-only',BASE,head],cwd=ROOT,text=True).splitlines()
def verify(path):
    expected=subprocess.check_output(['git','show',head+':'+path],cwd=ROOT)
    sha=subprocess.check_output(['git','rev-parse',head+':'+path],cwd=ROOT,text=True).strip()
    data=api('GET',PREFIX+'/git/blobs/'+sha)
    actual=base64.b64decode(data['content'])
    assert actual==expected
    return dict(path=path,git_blob=sha,sha256=hashlib.sha256(actual).hexdigest(),bytes=len(actual))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    files=list(pool.map(verify,paths))
p=api('GET',PREFIX+'/pulls/161')
assert p['head']['sha']==head and not p['merged']
receipt=dict(head=head,pr=p['html_url'],pr_state=p['state'],merged=False,
             remote_bytes_verified=files,training_jobs_submitted=0,
             projects_board='not_updated_existing_read_project_permission_gap')
save('REMOTE_VERIFY.json',receipt)
body='''方案已通过PR161交付，待审未合并：
https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/161

- 目标明确为Qwen/Qwen3-4B，教师/学生均非Base；PR147仅历史算子依据。
- 已完成全模型W8/真实共享采样训练契约、D/F/L/H×T8/16/32/64共16方案＋3控制、后续B/d/IID扫描、非Base能力保持与验收设计。
- scan.py清单/语法、未就绪启动拒绝守卫及独立审阅通过；远端发布文件逐blob原字节回读通过。
- 目前是设计交付，没有训练器实现、权重下载、H200/Slurm作业或新PPL。revision/权重与模板SHA、许可训练数据、H200环境在执行前补齐；不会使用Base结果充当新基线。
- 正式文档qwen3/training/sc_qat_20261023/TRAINING_PLAN_ZH.md；配置SCAN_MANIFEST.json；work/jieruiz/159/HANDOFF.md为恢复入口。
- 看板未同步（既有read:project权限限制），Issue与PR已同步；不自动合并/关闭。
'''
comment=api('POST',PREFIX+'/issues/159/comments',dict(body=body))
receipt['issue_comment']=comment['html_url']
save('FINAL_RECEIPT.json',receipt)
entry='''## Issue159 实际发布：2026-10-23

Qwen/Qwen3-4B非Base训练设计已推送PR161，科学提交6991c97f9d54c1d9ea17ee2ce87f44d08b6677f4；远端设计文件原字节核验通过，Issue159已同步。PR待审未合并，无GPU训练/新PPL；后续执行需模型revision/数据/训练器/H200环境。19项是计划配置，不是已运行结果。work/jieruiz/159/FINAL_RECEIPT.json为回执；Projects待权限同步。

'''
for path in [ROOT/'PROJECT_MEMORY_ZH.md',ROOT/'progress/jieruiz/STATUS.md',OUT/'HANDOFF.md']:
    old=path.read_bytes()
    if 'Issue159 实际发布'.encode() not in old: path.write_bytes(entry.encode()+old)
workspace=ROOT.parents[1]
canonical=workspace/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=workspace/'PROJECT_MEMORY_ZH.md'
assert canonical.read_bytes()==mirror.read_bytes()
old=canonical.read_bytes()
if 'Issue159 实际发布'.encode() not in old:
    canonical.write_bytes(entry.encode()+old);mirror.write_bytes(canonical.read_bytes())
print(json.dumps(dict(head=head,verified_files=len(files),pr=161,comment=comment['html_url'])))
