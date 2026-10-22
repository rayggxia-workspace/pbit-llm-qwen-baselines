# 直接质量目标训练：49参数p-bit筛选网的独立留出结果

Issue [#92](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/92)，负责人amlink1219，2026-10-22，接续PR94。原[首轮负结果](../pbit_gate_pilot_20261022/README_ZH.md)完整保留。

**优化有效：三层均优于原max4温度1；强对照下存在分层权衡。** 本轮先完成TRAIN/VAL迭代，再冻结全部90配置并执行一次48篇新文章的独立盲评，没有根据blind重新训练、调偏置或选模型。下面是冻结盲集上的局部点估计，不是完整模型PPL。

## 训练目标如何改

每块输入仍是四个16-token子块摘要QK分数。每层4→8→1网络含49个浮点可训练参数、8个条件独立隐藏Bernoulli p-bit和一个输出bit。给定实际选块概率q_eff及完整准确Attention教师的块概率质量m，主目标改成：

`min L = mean_query(1 − Σ_block q_eff · m)`，约束 `mean_TRAIN Σ_block q_eff = 8`。

这直接优化真实随机mask遗漏概率质量的准确期望。先用max4概率warmup150epoch，再切换直接目标；实际输出bias每步只在TRAIN求根，反传包含隐式约束梯度 `Lθ − (Lb/Fb) Fθ`，不是靠软预算罚项或事后在验证集调预算。256隐藏态精确边缘只用于软件训练，评估实际抽取隐藏和输出bit。

同时修正四输入缺少query参照的问题：新增 `(x−mean_free(max4))/max(std_free(max4),0.01)` 的query-relative输入，clip到±12；保留旧global标准化作为对照。它需要query级归约和clip，不能称为纯局部门控或忽略硬件成本。数据量、输入和目标跨轮同时改变，不能将总收益独立归因给其中某一个改动。

## 实际迭代与防止挑选

原48篇文章的正文/全文/截断token SHA全部排除。新192 TRAIN／48 VAL／48 BLIND文章，context2048，层0/12/23、head0/6/13、位置1023/1535/2047，共7776完整query/head组。TRAIN/VAL物理分片6480组，blind独立分片1296组。均来自WikiText-2 **train**语料，未接触WT2 test；每层只有这三个head和三个位置，不代表完整24层的模型接入。

第一轮扫3模型类型×2输入方式×3seed×3层=54个训练候选，warmup150/direct300。p-bit的最优epoch都在末端，所以追加9个p-bit/query-relative候选到direct6000，仍只用TRAIN/VAL。网络与5参数线性p-bit、49参数tanh确定隐藏＋随机输出对照一并保存。确定性控制只训练到300、p-bit长训到6000，预算未对齐，不能据此宣称隐藏随机性独有优势。

max4对照覆盖8个温度（0.015625/0.03125/0.0625/0.125/0.25/0.5/1/2）及TRAIN全局硬阈值，共27项。硬阈值是逐块标量比较，仅相等项按TRAIN拟合概率取舍，**不是逐query top-k**。所有bias/阈值只在TRAIN拟合平均8块；VAL只选epoch/候选，初筛允许平均块数比T1高至2%，该研究门禁不代表严格同预算或用户已接受的PPL误差标准。blind真实预算漂移照实保留。

最终90配置（63训练候选＋27max4控制）的参数、来源、验证资格、选择和SHA在CPU2750中冻结；冻结SHA为`6ca6e2ce829909a7dd993b8d1a507c55701a135dcc724b02144c737b80a67090`。CPU2749的45项检查全部通过，含约束梯度有限差分、原kind回归、真实硬阈值dispatch和先冻结后读blind；GPU2751全部90项COMPLETED/0:0，评估58.06秒。搜索GPU2744和长训2746均已成功完成，没有本任务运行中作业。

## 留出集结果

遗漏的是完整教师的Attention概率质量，越低越好。小网列平均全部三个长训练seed；强max4每层只按VAL选择，依次为硬阈值、T0.03125、硬阈值，没有按blind挑赢家。

| 层（从0计） | 原max4 T1 | 训练p-bit网（三seed均值） | 验证预选的强max4 |
|---|---:|---:|---:|
| 0 | 4.253% | 1.978% | 2.069% |
| 12 | 3.550% | 2.021% | 2.163% |
| 23 | 31.365% | 24.845% | 24.723% |

相对原T1，小网遗漏分别降低约53.50%／43.07%／20.79%。强max4本身也大幅改善，不能把这部分手工调温/阈值收益归于小网。

| 层 | 小网／强max4平均候选块 | 小网／强max4候选PV NMSE |
|---|---:|---:|
| 0 | 7.9425／8.0347 | 0.0002875／0.0003383 |
| 12 | 8.0321／7.9919 | 0.0011617／0.0013713 |
| 23 | 8.0763／8.1690 | 0.0419235／0.0430774 |

- 层0：小网比强max4遗漏低4.40%，平均候选块少1.15%，候选PV误差低15.03%。这是候选量与局部质量的平均改善，新增49参数门控的总计算/PPA尚未计入。
- 层12：遗漏低6.57%、PV误差低15.29%，但平均候选块多0.50%，不能称严格等成本优势。
- 层23：遗漏高0.49%，候选块少1.13%，PV误差低2.68%，属于质量/候选量权衡，不能称全面胜出。

以上为48篇文章的点估计，未声称统计显著。不同长度桶并非全部改善；全部桶、3训练seed原值及标准差见[RESULTS.json](RESULTS.json)和[90项完整紧凑评估](compacts/BLIND_COMPACT.json)。均使用真实两级抽样，3个评估seed各32次；各桶抽样是独立重跑。PV由选中子集上的准确教师分数重归一化，与有限Ising、V采样误差分开，不能将它称为学生PPL。

## 硬件与部署边界

本轮没有更新LLM/FFN/Ising权重，没有改正式Attention默认。权重/特征仍为软件浮点参考，未验证W8量化、物理p-bit响应、共享随机源相关性、完整24层PPL或推理延迟/能量/面积。不能用GPU训练时长替代硬件推理收益，也不能按平均选块数直接推断GQA物理KV字节。

小网约33%／39%／39%的mask超过512 token，P95仍为704–768或更高的桶峰值；不能直接接现有固定512容量宏。全部90项PV分母clamp为0，但这只是局部数值有效性。后续若继续，应先冻结新的容量/工作点和完整层接入协议，再验证PPL与包含门控成本的完整Attention；已看过的blind不能继续当独立测试来调参。

## 复现与成果位置

代码与协议：[实验目录](../../../experiments/pbit_gate_pilot_20261022/README_ZH.md)、[冻结优化协议](../../../experiments/pbit_gate_pilot_20261022/OPTIMIZATION_PROTOCOL_ZH.md)。原始训练源码为`cfa1962202e364a18562eea7d182ab7a0d947f6e`／`cfad390297d9b9d05f85305a3bcafc2aac9e102d`，控制源码`6241ab7f682cfb57403c579427e9c85314f50399`，冻结/盲评源码`f66b65ac76d4481d8ce0c1399590dc3fc4e62a53`。后续发布只补报告/包装元数据。

模型权重SHA `88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342`；训练文本SHA `6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57`。TRAIN/VAL NPZ SHA `d80319da15c29b6b105157d2abce7ce3f11de510f8ffe25c20c18e2ceb24642e`；BLIND NPZ SHA `9ee16da484f00fcfa9a29c30251e376112b7ad4c98d2f3d5caa0249ccf01aec7`。

原始NPZ、长训练日志、32MB完整冻结单和全部逐文档记录保留本人服务器 `/home/Weican_Chen/projects/pbit-gate-pilot-issue92`。Git发布紧凑全90结果、90份小网/控制参数、预声明逐文档原件、完整索引与SHA，见[ARTIFACT_INDEX.json](ARTIFACT_INDEX.json)、[PACKAGE_MANIFEST.json](PACKAGE_MANIFEST.json)及[任务交接](../../../work/amlink1219/92/HANDOFF.md)。评估新版本只在optimize.py新增硬阈值dispatch；训练源码SHA与评估源码SHA分别记录，network.py/train.py保持一致，旧kind回归通过。
