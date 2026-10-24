# 第十轮 PR 审核：后训练模型方案与硬件恢复证据

负责人 jieruiz；Issue55；2026-10-24。正式仓库 rayggxia-workspace/pbit-llm-qwen-baselines；登录身份已核验。独立稀疏目录 tmp/pr55-review-round10-20261024，分支 review/55-pr-round10，基线 e1b23d7766303a502934d8b6eb45b9209bbb58b9。
本文件冻结于本地审核完成、准备发布时；实际合并以 GitHub PR/Issue55 最终回执为准。目标 pbit-tlm-attention-details-20261016；main 保持 fae12982e0a92dea1f81648a5eeee148974c4a87，不宣称全部 TLM 已在 main。

## 决定与范围

| PR / 精确 head | 决定 | 已经完成及限制 |
|---|---|---|
|161 / ae83c08ff1d754d27359a2aaade0b09561615988|接受设计交付|Qwen/Qwen3-4B 后训练模型，全36层 FFN、W4/6/8、A8、共享64与分层采样的训练方案/远程交接。57项是计划（48随机+9控制，114亿计划有效token），非57项训练结果。无训练器、GPU训练或新PPL。|
|164 / 1fa4c7954ab82a0a205c1eaab6742381106d324b|接受流程与带限制结果|包含前轮后新增的完整 ppa8 脚本、活动修复与原始结果索引，不只是最新回执。KIND21 SS/TT三seed、18窗口已有PT，100%标注仍有库表外推/check_power告警，必须为provisional。38353729与38353735同输入的PT重算不算两个独立实验。余14项提交快照中首项失败、其余未形成可验收完整结果。|
|165 / bc4ee645c311c42b62a41b3fc54859713b65f13d|接受流程与带限制结果|修复PT时间单位和X/Z分类，冻结原DC/VCS输出恢复PT。A/B×SS/TT M1、seed17、8窗口；有INCOMPLETE_ACTIVITY/外推/check_power，不作最终PPA。无M64完整工艺、多seed结果；回收时才补的映射/VCD哈希不能追溯宣称为最初提交时封存。|
|166 / 4c20182825b85cb2b64b541ad2ea49a34ac46db8|接受恢复修复与正负结果|层次VCD、常量证明、翻转率交叉检查修复；M1组合gate/Qprobe四项、8窗口有PT。含随机源/完整前端四项因threshold[0]的PT/VCD翻转率不符失败，禁止沿用功耗。Qprobe为固定权重Q，动态功耗为0仅说明本激励，不是SRAM读写能耗。|

模型要求按用户2026-10-23确认：后续用Instruct/后训练版，Base是模型版本，不是Git基线。Qwen3-4B名字不含Instruct，但官方模型卡标记Post-training；固定配置revision 1cfa9a7208912126459214e8b04321603b3df60c。新训练仍需绑定实际权重/tokenizer/文本哈希，并建立匹配的未改动参考。

#161源码/文档已核对：三位宽对称量化范围、x/z独立随机与gate/up共享x、各层全路径、TRAIN-only尺度校准、PoT-STE有偏性质、冻结期、DDP有效token归一化、checkpoint随机重放、teacher蒸馏、G2独立课程、部署packing与thinking计分口径均有明确约束。三个BF16控制是配对重复，不应叫三训练seed。launch_ready=false正确拒绝未准备启动。

## 留待完成

| PR | 原因与下一步 |
|---|---|
|160 / 989546376f2295990b7712ea553615f0b8d88cb4|仍draft、head未变，缺独立后训练完整参考及概率评测回执。旧任务队列快照不能当作实时队列；先核实现有作业，避免重复启动。|
|163 / ca3da3a5308cdd820d1d9554b2866b9eb098d5a4|仍draft。冻结结果有完整WT2：cached dense PPL11.5381534、SparQ10.7979258；vectorized dense11.5371605单列。PIQA/ARC完成、HellaSwag未完成、最终SUMMARY缺失。短任务多数dense fallback，稀疏占比PIQA1.4378%、ARC0.207649%，不能据接近准确率推断广泛稀疏稳健性。2048/128时Python参考SparQ约14.33tok/s，对照约47.84，不能宣称GPU加速。原执行UUID不匹配无有效功耗；当前head已修复UUID规范化及NVML复核，但需要新冻结测量，不能补写旧结果。|
|137/143/147/149/153/155|六个head与第九轮一致，继续保留Base迁移门禁；历史证据保留，不重标为Instruct，不纳入此次集成。详见第九轮报告。|

## 实际验证

- 60项本地单测通过，0跳过：ppa8 14、counter 27、CIM 11、registry 8。EDA流程测试含mock，不是本机执行DC/VCS/PT。
- #161清单生成通过：57/48/9；未就绪启动按预期返回1，JSON模板可解析。
- 50个下载原件SHA/大小一致；三个新结果record的30个artifact验证；2,087个唯一归档成员SHA/大小一致，失败原件也保留。
- 34个功耗窗口与归档SUMMARY/原始power.rpt核对，单位、E=P×duration、分量与零分母null规则通过。
- 三个运行包322个manifest成员一致，106个直接源码与checkout相同；ppa8另23个RTL/转换/参考依赖与当前Git blob相同。未生成新EDA结果或改写归档。
- 80个来源科学源码/record Git blob（6+34+27+13）与四个已审head一致，四head均为集成祖先；8个搁置head均未被集成。
- 台账check/render：56 records、1298 case_rows、193 archive_candidates，索引合并保留并行新增记录。修正覆盖说明中“尚待提交”的旧描述，并在146交接开头标明最新恢复结果。

执行命令、返回码、原始核验JSON见evidence/。本轮仅CPU检查与已有报告复核，没有新GPU训练、完整PPL、RTL/DC/VCS/PT/Spectre作业；未取消任何健康任务。

## 与主线的关系及后续

161把随机FFN训练主线迁移到后训练Qwen3-4B，但下一步仍是实现训练器并通过G0/G1/G2门禁，不能直接启动57项全量扫描。164/165/166把包准备推进到真实工艺报告和可重现恢复链，但还不是完整芯片或完整FFN收益：数字余14项需结果闭环、counter需活动覆盖与M64、CIM需修复随机源翻转率映射。163对注意力稀疏主线相关，但质量/速度/能耗三条证据应分开。

来源Issue107/133/146/159仍有后续工作，不因合并阶段交付自动宣布整个研究完成。Issue55保持开放。Projects写权限未在本轮证实，未宣称已同步看板。主checkout和其他成员STATUS未改；审阅副本交付后按恢复索引清理，原始科学归档保留。

一手依据：[Qwen3-4B官方模型卡](https://huggingface.co/Qwen/Qwen3-4B)、[固定revision配置](https://huggingface.co/Qwen/Qwen3-4B/blob/1cfa9a7208912126459214e8b04321603b3df60c/config.json)。本地证据归档 project_archives/pr_review_issue55_round10_20261024/。
