"""Task-only delivery notes; preserve all unrelated memory/status entries."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'work/jieruiz/150'
OUT=ROOT/'qwen/results/static_multiscale_20261023'
SHA='49bc6bd1356413585c99dad6513d25cc34cff090'
RAW=OUT/SHA
def write(p,t):
    with p.open('w',encoding='utf-8',newline='\n') as f:f.write(t)
def save(p,v):write(p,json.dumps(v,ensure_ascii=False,indent=2)+'\n')

summary=json.loads((OUT/'SUMMARY.json').read_text(encoding='utf-8'))
assert summary['status']=='complete'
package=json.loads((WORK/'PACKAGE.json').read_text(encoding='utf-8'))
cpu=json.loads((RAW/'CPU_READY.json').read_text(encoding='utf-8'))
verified=[]
for path,entry in package['files'].items():
    payload=subprocess.check_output(['git','show',SHA+':'+path],cwd=ROOT)
    h=hashlib.sha256(payload).hexdigest()
    assert h==entry['sha256']==cpu['source'][path]
    verified.append(dict(path=path,bytes=len(payload),sha256=h))
save(WORK/'FINAL_VALIDATION.json',dict(status='passed',execution_commit=SHA,
     completed_full_results=21,selection=12,holdout=4,invalid_results=0,missing_results=0,
     source_git_blob_checks=verified,remote_hydrated_assets=2,
     tests=dict(static_core=17,stratified_core=13,multiscale_core=12),
     limitations=['two historical assets checked server-side; no duplicate local copy',
                  'Slurm sacct unavailable: accounting storage disabled',
                  'completion judged from sealed completed JSON and full coverage, not log tails']))
cmd=['ssh','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','lab-server-ai',
     '/opt/slurm/21.08.8/bin/squeue -j 2840,2841,2842 -o "%.18i %.9T %.12M %.30R"']
r=subprocess.run(cmd,text=True,capture_output=True)
save(WORK/'FINAL_QUEUE.json',dict(command=cmd,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))

text='''## 2026-10-23 Issue150：FFN固定多档完整PPL

负责人jieruiz，task/150-fixed-multiscale，PR153待审未合并；执行49bc6bd1356413585c99dad6513d25cc34cff090。Slurm2840/2841/2842已产出全部封存结果：21项完整WT2、12候选selection、4holdout，0缺失/无效，299077计分token、24层所有forward输入覆盖通过。固定W8/A8共享64随机分层、原准确attention，非物理IID或RTL性能。无需重跑。

TRAIN独立拟合/选优后冻结d2_h0：每层每64通道x/z各自固定S、S/4、S/16、S/64，无在线absmax/扩档。BF16 11.652735；W8 11.681130；固定mean 11.691441。三seed均值：动态32 11.736131、固定32 11.851810、只固定x32 11.746519、只固定z32 11.838450；动态64 11.693775、固定64 11.736412。全固定64接近原动态32；省前端但采样翻倍，尚不能称能耗更低。主要质量差距在z，未测联合随机attention/跨语料。

正式报告qwen/results/static_multiscale_20261023/REPORT_ZH.md，完整数值SUMMARY；实际表SELECTED。原件83文件9.95MB已压缩为510435B，project_archives/fixed_multiscale_20261023/SEALED_RESULTS_49bc6bd1356413585c99dad6513d25cc34cff090.tar.gz，SHA6829e50ba08f8c25d7611c5aac5eba6b96232df46ad652dc8a35fd06ed7dd13e，逐成员核验；Git只留必要摘要、固定表和RAW_INDEX。服务器ROOT /home/Hongjie_Zeng/projects/pbit-qwen-static-multiscale-20261023-issue150不改，按索引恢复。交接work/jieruiz/150/HANDOFF.md。Projects查询缺read:project待同步；sacct关闭，完成依据签名校验JSON而非sacct。无新RTL/PPA/TLM，不自动合并/关闭Issue。

'''
for p in (ROOT/'PROJECT_MEMORY_ZH.md',):
    old=p.read_bytes()
    if b'Issue150' not in old[:1000]:
        p.write_bytes(text.encode('utf-8')+old)
base=Path('C:/Users/86134/Documents/a_P_BIT')
canonical=base/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md'
mirror=base/'PROJECT_MEMORY_ZH.md'
old=canonical.read_bytes()
assert mirror.read_bytes()==old, 'Memory mirror changed; reconcile before writing'
if b'Issue150' not in old[:1000]:
    assert canonical.read_bytes()==old and mirror.read_bytes()==old
    new=text.encode('utf-8')+old
    canonical.write_bytes(new)
    mirror.write_bytes(new)

p=ROOT/'progress/jieruiz/STATUS.md'
old=p.read_text(encoding='utf-8')
end=old.index('\n# Issue55')
write(p,'''# Issue150 固定多档尺度（2026-10-23，完整评测交付）

负责人jieruiz；task/150-fixed-multiscale；base6966739；PR153待审、未合并；独立tmp/fixed-multiscale-issue150-20261023。执行49bc6bd，Slurm2840/2841/2842产出21/21完整WT2+12selection+4holdout，全部SHA/选优/24层全输入覆盖核验通过。d2_h0固定四档，固定T32 PPL11.851810、T64 11.736412，动态T32 11.736131；主要差距z侧，无attention联合替换、新TLM/RTL/PPA。正式REPORT_ZH与SUMMARY在qwen/results/static_multiscale_20261023；原件压缩单份本地归档及远端，RAW_INDEX含SHA。核心42功能测试通过。内核helper已回收，保留最小主工作树。Projects缺read:project；无需重交实验，下一步评审PR。实际推送/原字节核验以FINAL_PUBLICATION.json和REMOTE_VERIFY.json为准，PR未合并不关闭Issue。
'''+old[end:])
write(WORK/'HANDOFF.md',text+'''## 执行与恢复

1. Issue150、PR153；base pbit-tlm-attention-details-20261016@6966739a5223680888bf0315f7bb4f73423a1ae6。发布分支task/150-fixed-multiscale；GitHub核验身份jieruiz。
2. 数值执行仍是49bc6bd。后加collector/报告不进入已提交的snapshot。模型/数据/源码/配置/SHA和Slurm命令见SUBMISSION、PACKAGE及RAW_INDEX。原BF16同轮重跑后才校准。
3. 先按RAW_INDEX恢复归档到新目录；运行collect_static.py --input 恢复目录 --output 另一目录。不要修改封存JSON或把摘要目录当原件目录。全部完成，无本任务剩余GPU评测，不取消他人作业。
4. 三seed结果及方差见SUMMARY.json。只有TRAIN selection选档，holdout/test没有调参。K=T分层不是自然IID；fixed_mean不是整个随机非线性网络的数学期望。动态控制数值复现旧Issue46。
5. 硬件只明确可取消在线absmax，仍需选档/转换/恢复；2160组E8约2.11KiB元数据，不包括计数/标签，尚无功耗面积实测。不改默认TLM。
6. Helper task/150-fixed-scale-kernel已在干净状态回收；原提交7b25c20/305493f仍有Git ref，等价交付6054792/6b5cb47已纳入主分支，不删除实验历史。
7. Projects API实测INSUFFICIENT_SCOPES/read:project；Issue/PR可以更新，看板待有权限维护者同步。未合并、不关闭Issue，不创建定时。
''')
write(WORK/'PR_BODY.md', '''用TRAIN离线固定四档代替每token/64路动态absmax，检查FFN能否省去在线范围归约。选出的四档是S、S/4、S/16、S/64；S按层、信号及64通道组固定，推理不扩档。

已完成Qwen2.5-0.5B全24层FFN、原准确attention的21项完整WT2，采样各三seed：BF16 11.652735；动态32 11.736131；固定32 11.851810；固定64 11.736412。只固定x32 11.746519，主要差距在z。固定64接近动态32，但采样翻倍，不能仅据此声称能耗下降。

验证：同轮BF16和模型/语料/源码SHA门槛；12项TRAIN候选及4项独立holdout；37份评分记录原字节/配置/尺度/24层全部输入覆盖验证，0缺失0无效；17新内核+13stratified+12multiscale测试。Slurm2840/2841/2842，执行49bc6bd冻结。较大原件只在服务器/本地压缩归档，83成员SHA与恢复索引齐全，Git保留必要表/汇总。

报告qwen/results/static_multiscale_20261023/REPORT_ZH.md；任务Issue #150。无新RTL/PPA/TLM或联合随机attention验证；不自动合并。Projects缺read:project，待维护者同步看板。
''')
write(WORK/'ISSUE_UPDATE.md', '''全部评测已完成并核验，结果已整理到PR153的qwen/results/static_multiscale_20261023。21/21完整WT2＋12 TRAIN selection＋4 holdout，0缺失/无效；24层全部forward输入、原字节SHA、模型/数据/配置/尺度链通过。固定四档选择d2_h0（S,S/4,S/16,S/64），x/z按层按64通道组离线设定，不再在线absmax。

三seed均值：动态T32 11.736131，固定T32 11.851810，固定T64 11.736412；BF16 11.652735。只固定x T32 11.746519，主要质量差距z侧。固定64接近动态32，但未测实际能耗，不把多采样代价忽略。attention保持准确。

Slurm2840/2841/2842已封存结果，无需重交；执行49bc6bd不改。原件83文件SHA及单份510435B压缩归档见RAW_INDEX，核心42功能测试通过。PR待审未合并，Issue保持open；看板API缺read:project，待有权限维护者同步。
''')
print(json.dumps(dict(status='prepared',full_results=21,source_blobs_verified=len(verified),queue=r.stdout.strip())))
