# Issue55第三轮：7项PR已审核并合并

2026-10-20；实际账号jieruiz，正式仓库rayggxia-workspace/pbit-llm-qwen-baselines。用户明确授权正确且仍有价值的PR合并，本轮7项全部通过；最终科学集成`18b887bd2d0cd6c06d070d8dafaf8b979742fdcf`。没有新GPU实验、训练或PPA。

|PR|本轮结论|实际merge|
|---|---|---|
|49|六档后缀保留；补同源S128三seed代表性完整确认，base改当前集成|18b887bd2d0cd6c06d070d8dafaf8b979742fdcf|
|52|发现服务器25项已齐，回收核验后补发布并纠正旧运行状态|3b74375b07d16a2cb3e5d5b8ae7ceb825031472c|
|62|39项逐题/seed/配对重算通过，先入52任务分支，再随52进入集成|992c693df8da221293751f60b8b0e53c05052039（子PR）|
|67|Apple两套原始FP32模型六任务与完整WT2基线通过|e96e54da2f16d3792dcb7ce266a2ba715e1e63d6|
|69|59已回收副本的恢复依据、440独有文件、12增量bundle及模型SHA通过|bc9f96d73726a858f9bf9eb494c14b46c24f4279|
|71|ReMix v1原文/数学与8个稳定blob通过|b5e04f8775f6f4fde5bf7fdc6df7a4ba5783b224|
|72|39项最终结果备忘录通过，保留原清理增量及历史进度|650c6b2dccd27d7a6013e4632441ec502978b9b9|

## 完整结果与核验

此前“完整WT2尚未收齐”是旧发布状态，并不代表服务器仍缺结果。只读回收2430的19项、2461的6项，共25份完整结果；原B4T16联合三项由用户授权在pending时取消，不误写成完成。25配置SHA、7300段NLL、299077目标各一次、24层计分调用及源/输入/门禁核验通过。完整结果独立目录`qwen/results/joint_full_wt2_20261020/`，旧4096目标后缀报告原字节保留。

matched cached BF16完整PPL为11.652118；B4T32-only 11.732192；联合S128/256/512为12.423820/12.274153/12.207062（各三seed）。S512的mean-NLL几何PPL比仍约+4.763%，不以自定5%阈值宣布等价。S256/512缺原FFN完整同预算控制，interaction留空。PR49仅原FFN S128有完整三seed确认12.318676±0.005035，不能泛化至S512或六档完整曲线；full无IID控制，不作全部误差归因。

PR62：126件原件SHA、16发布blob、73公开源码通过；独立重算67782条逐题/223301候选、135564指标、78配对统计与15组seed；30项CPU测试通过。HellaSwag是固定1000题子集；短题K/GQA候选率100%，不能证明长上下文筛选。Git/服务器报告字节一致，Windows重放SUMMARY只在81个artifact路径分隔符不同，规范此唯一OS差异后精确一致；MD三方原字节一致。

PR52：65项现有核心CPU通过；独立24层dense-causal oracle与cached计分差≤1.43e-6。完整计划独立覆盖292窗/299077目标且各一次；另4项纯计划重放与其中检查有重叠，不累加独立数量。94 joint/30底层源blob、35锁定门禁依赖以及最终49项发布包Git blob通过；两执行数值核不变。模型配置仅681B LF/709B CRLF的28个CR差异，解析JSON相同，元数据差异照实披露。私有校准只按冻结manifest核，本轮未重哈希大权重。

PR67：16正式JSON/9核心源锁定、六任务每模型19965题、同模板与seed，raw均值63.692864%/64.823195%；两模型317546目标WT2 PPL5.911825/5.886073。独立重算310窗NLL和汇总、轻量评分接口检查通过。权重/native NPZ/逐题大文件以服务器回执为证据，未独立完整GPU复现。BF16移植失败保留，FP32配对不是同权重Softmax替换，也不是p-bit/PPA结果。

PR71：固定v1 PDF22页/699040B/SHA一致，8稳定blob；作者24例与独立24例数学核验、306个top-k网格/2820次交换通过。未重新读取私有Zotero库现态，原回执与公开原文对应，不声称训练或PPA复现。

PR69：独立核10本地制品索引、17+42恢复引用、13+14zip、第二轮440独有文件/12增量bundle及Qwen保留权重；逻辑10.510GiB一致。清理脚本只审阅未重跑删除。历史磁盘空闲快照不可回放，462大文件原记录仅存在/大小检查，不夸为全部逐SHA。

## 集成与状态

每次合并使用精确head/base、实际jieruiz权限、CI/status、未决review/thread与原生merge门禁；事后核两个parent及merge tree。无保护绕过或force push；四项PR刷新只解文档/规则/进度冲突，科学blob不变。amlink1219 STATUS保持当前集成原字节；本人STATUS两边历史顺序保留。预发布检查拦截并修复一个未推送的STATUS合并脚本吞尾问题，最终独立树复核通过，未丢发布历史。带SHA原始JSON/终态日志的CRLF/尾空白按原件保留；仅新元数据范围diff-check作为格式门禁，不改原件消警。

Issue48/50/59/65/68/70均按各自范围验收关闭，Issue28持续维护。看板GraphQL本轮实测仍缺read:project，仓库账号admin/push和7项合并全部成功，这两者不得混淆。旧scontrol记录已过期、sacct storage disabled，25完整结果以封存completed原件/输入源SHA/逐目标审计为完成依据，不伪造调度会计终态。

## 恢复与本地副本

当前分支review/55-pr-round3，唯一稀疏目录tmp/pr55-review-20261020；子审阅仅git对象与最小导出，未建额外全量checkout。根阅读副本与canonical同字节，原12行待提交清理增量已逐字节/patch备份且完整保留；canonical Git HEAD不reset，工作文件与本次发布文档一致，详见MEMORY_LOCAL_SYNC.json。

原件tar、独立脚本/图片和所有本轮临时状态在project_archives/pr_review_issue55_20261020逐SHA归档，正式提交/ref保留；本轮helper交付后回收，实际回收回执另在Issue55最终消息及本地恢复索引，不把待执行回收写成已执行。既有长期/其他成员工作目录、共享Git对象与模型未清理。恢复先读本报告、receipts和evidence，不重复已验收矩阵。
