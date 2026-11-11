"""Preserve and collect the sidechat supplement after an independent CPU replay."""
from pathlib import Path
import hashlib,json,shutil,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
REL=Path('architecture_tlm/module_handoff/attention_score_front_compare_20261108')
DEST=ROOT/REL;SOURCE=PROJECT/REL
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
review=json.loads((HERE/'ADAPTER_REVIEW.json').read_bytes());assert review['status']=='PASS_ISOLATED_CPU_REPLAY_IDENTICAL_RECEIPT'
public=json.loads((HERE/'LATEST_PUBLIC_FILES.json').read_bytes())
parent=DEST/'HANDOFF_ZH.md';old=parent.read_bytes()
expected=next(x['sha256'] for x in public if x['path']==(REL/'HANDOFF_ZH.md').as_posix())
assert sha(old)==expected,'Preserve and reconcile new local work'
incoming=(SOURCE/'HANDOFF_ZH.md').read_bytes()
assert incoming.endswith(old.split(b'\n\n',1)[1]),'Inspect sidechat parent changes before importing'
dest=DEST/'local_integration_A';assert not dest.exists();dest.mkdir()
originals={}
for name in ('adapter.py','verify.py','VALIDATION.json','HANDOFF_ZH.md'):
 b=(SOURCE/'local_integration_A'/name).read_bytes();(dest/name).write_bytes(b)
 originals[name]=dict(path=str(SOURCE/'local_integration_A'/name),bytes=len(b),sha256=sha(b))
assert originals['VALIDATION.json']['sha256']==review['provided_result_sha256']
save(dest/'INTAKE_VALIDATION.json',dict(review,provided_supplement_files=originals,
 root_original_validation_unchanged=True,not_an_RTL_or_GF64_equivalence_test=True))
(dest/'REVIEW_225_ZH.md').write_bytes('''# 主流程消费复核

2026-11-08，Issue225 / PR249，关联Issue198。已找到并收录侧对话local_integration_A补充；原adapter/verify/VALIDATION/HANDOFF字节保留。

## 复核结论

- 在约0.5MB独立只读输入快照中复跑原verify.py，25个来源SHA一致；192查询/24576分数、27组全有效旧S12接入、6912个固定激励递推输出通过。新VALIDATION与提供回执逐字节一致，原输入/回执未改。
- 显式A调用和P8 LUT边界已说明，接线不需要把A主线改成B。6912项只证明同阈值／同固定Python随机激励下的递推一致，不是GF64质量、RTL周期、回压或新完整PPL结果。
- 旧sampler.sv确实硬接candidate_mask全1、initial_index0；适配器拒绝非128全有效／非有限输入是正确约束。当前固定2K/K128且候选全部有效时不新增阻塞；短上下文、padding或通用mask另列后续接口范围，不要求本轮重做整个采样核。

## 现在能接什么、还缺什么

数值接口与计费合同可以作为后续接入依据；完整链价格仍保持null。优先复用旧S12 scores/max/gap/LUT，仅加四路FP32→S12转换及握手增量；或选择A＋去重gap后端，两条选一条，不重复做。

此次补充没有新增上述转换／握手增量的DC/PT，也没有完整连接后的准备/采样/等待分窗和握手时序。因此不能把独立A的面积、能量、65/67拍再整块加到旧sampler，不能把integrated_sampler_replacement_ready改true；也不能从旧核直接减完整A。下一步缺的是这个小边界的实际价卡／时序，不是重新证明S12数制或重新训练。

28nm仍需同工艺A或转换增量，不使用55nm乘频率/面积比例代替。侧对话提到的28nm准备脚本不作为实时队列证据，本次未提交或取消EDA任务。

本次只收录适配器、检查脚本、哈希与验证回执，没有携带私有前端包/大原始产物；异机复现须按VALIDATION.sources准备对应文件。本次未修改当前TLM源码/默认/冻结任务，未生成新整机PPA或新电路run。公开源和回读以work/rayggxia/225/score_front_audit_20261108/LOCAL_ADAPTER_PUBLICATION.json为准；PR249不合并，Projects待同步。
'''.encode())
note='> 2026-11-08主流程已消费复核侧对话补充：[复核结论与剩余边界](local_integration_A/REVIEW_225_ZH.md)。隔离CPU复跑与原回执逐字节一致；数值接口可用，转换/握手增量及集成PPA仍待。原文“尚未发布”为侧对话创建时状态，当前发布回执见LOCAL_ADAPTER_PUBLICATION。\n\n'
parent.write_bytes(note.encode()+incoming)
facts=json.loads((DEST/'AUDIT_FACTS.json').read_bytes());facts['local_adapter_intake']=dict(
 numerical_adapter_ready=True,frontend_kind='s12_max_gap',queries=192,legacy_all_valid_queries=27,
 fixed_stimulus_recurrence_outputs=6912,general_mask_supported_by_old_backend=False,
 converter_handshake_increment_PPA=None,integrated_sampler_replacement_ready=False,
 runtime_default_changed=False,provided_sha256=review['provided_result_sha256'])
save(DEST/'AUDIT_FACTS.json',facts)
index=json.loads((DEST/'SOURCE_INDEX.json').read_bytes())
for n,x in originals.items():index['sources']['local_adapter_original_'+n]=dict(x)
save(DEST/'SOURCE_INDEX.json',index)
v=json.loads((DEST/'VALIDATION.json').read_bytes());v['local_adapter_review']=dict(
 status='PASS_ISOLATED_CPU_REPLAY_IDENTICAL_RECEIPT',source_checks=25,
 result_sha256=review['replayed_result_sha256'],original_preserved=True,
 scope='numerical/accounting only;not RTL/GF64/fullPPL/PPA')
save(DEST/'VALIDATION.json',v)
# Update only this task's reading copies; compare original before writing.
assert (SOURCE/'HANDOFF_ZH.md').read_bytes()==incoming
for name in ('HANDOFF_ZH.md','AUDIT_FACTS.json','SOURCE_INDEX.json','VALIDATION.json'):
 (SOURCE/name).write_bytes((DEST/name).read_bytes())
for name in ('INTAKE_VALIDATION.json','REVIEW_225_ZH.md'):
 p=SOURCE/'local_integration_A'/name;assert not p.exists();p.write_bytes((dest/name).read_bytes())
status=ROOT/'progress/rayggxia/STATUS.md';status.write_bytes(('''## 2026-11-08 Issue225：侧对话A适配补充已隔离复核

已找到根交接local_integration_A，保留原字节并收录。25来源SHA/192查询24576分数、27组旧S12/P8及6912固定激励递推回归通过，新VALIDATION与原回执字节相同；不是RTL/GF64/PPL/PPA。旧后端仅128全有效，当前固定2K/K128适用；通用mask另列，不重做整核。

数值接口/计费合同已明确，但未补四路FP32→S12转换＋握手增量PPA或匹配去重gap后端、集成握手/分窗，全链仍null/ready=false。未改运行源码/默认/冻结任务，不交新EDA/GPU；发布看LOCAL_ADAPTER_PUBLICATION，PR249不合并，Projects待同步。

''').encode()+status.read_bytes())
handoff=HERE/'HANDOFF.md';handoff.write_bytes(('''## 本地A适配器消费（2026-11-08）

补充源来自根local_integration_A，已25输入SHA核验并在adapter_review_runtime隔离复跑，VALIDATION与提供方字节一致。正式原4文件及复核REVIEW/INTAKE已收录，父交接保留侧对话新增入口。数值ready，全链PPA仍false；不改默认/冻结任务，不重复GPU/EDA。发布看LOCAL_ADAPTER_PUBLICATION；新CPU日志及ADAPTER_REVIEW保留，本机root/任务目录更新同字节。

''').encode()+handoff.read_bytes())
canonical=PROJECT/'tmp/project-memory-issue28-20261018/PROJECT_MEMORY_ZH.md';mirror=PROJECT/'PROJECT_MEMORY_ZH.md'
raw=canonical.read_bytes();assert raw==mirror.read_bytes()
memo='''## 2026-11-08：侧对话A接入补充已消费复核

用户称已补交接，实际位于root module_handoff/attention_score_front_compare_20261108/local_integration_A（原未发布、只改root）。消费Issue225/PR249已保留原adapter/verify/VALIDATION/HANDOFF字节，独立约.5MB快照复跑：25输入SHA、192query/24576分数、27全有效旧S12/P8、6912固定Python激励递推PASS；重放VALIDATION SHA f863f8903b29769beb0a61338fe1c442cfcc56a8545c1c3ce088ab7aebdba110，与原回执字节相同。非RTL/GF64/PPL/PPA，不重跑昂贵任务。

旧sampler真实candidate_mask硬接全1、initial0；legacy_payload拒绝非128全有效/非有限符合边界。当前固定2K/K128全有效适用，通用mask/短上下文需另接，不作当前整核重做前置。软件数值/计费合同可用，但四路FP32/S12转换+握手增量PPA（或匹配去重gap后端）及连接后握手/分窗仍未补；完整链null/ready=false不改变。未改runtime/default/冻结源、无新EDA/GPU。正式REVIEW_225及INTAKE索引，发布看score_front_audit_20261108/LOCAL_ADAPTER_PUBLICATION.json；PR249不合并，Projects待同步。

---

'''.encode();assert canonical.read_bytes()==raw and mirror.read_bytes()==raw
canonical.write_bytes(memo+raw);mirror.write_bytes(memo+raw)
paths=[DEST/n for n in ('HANDOFF_ZH.md','AUDIT_FACTS.json','SOURCE_INDEX.json','VALIDATION.json')]
paths+=list(dest.iterdir())+[status,handoff,HERE/'review_local_adapter.py',HERE/'intake_local_adapter.py',HERE/'ADAPTER_REVIEW.json']
files=[dict(path=p.relative_to(ROOT).as_posix(),content=p.read_bytes().decode(),sha256=sha(p.read_bytes())) for p in paths]
save(HERE/'LOCAL_ADAPTER_FILES.json',files)
subprocess.run(['git','-c','core.autocrlf=false','add','--sparse','--']+[x['path'] for x in files],cwd=ROOT,check=True)
for x in files:assert sha(subprocess.check_output(['git','show',':'+x['path']],cwd=ROOT))==x['sha256']
subprocess.run(['git','-c','core.whitespace=cr-at-eol,-blank-at-eof','diff','--cached','--check'],cwd=ROOT,check=True)
print(json.dumps(dict(files=len(files),numerical_adapter_ready=True,integrated_PPA_ready=False,sources_verified=25)))
