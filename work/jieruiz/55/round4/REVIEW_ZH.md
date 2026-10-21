# Issue55第四轮独立PR审核与实际合并（2026-10-21）

用户要求正确且仍有增量价值的PR审核后合并。本轮初始75/77/79，加收尾新提交80，共4项均通过并按实际head/base原生合并；报告PR另计。正式目标为`pbit-tlm-attention-details-20261016`，GitHub身份jieruiz/admin/push均已核验。

| PR | 审核head | 实际merge | 范围 |
|---|---|---|---|
| [#77](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/77) | `a5908e555210bcc756a85a74a9c114585bea015f` | `bd09a4af8cf9719e49182537ff7254528e19fb31` | 四条训练讨论计划，无训练执行 |
| [#79](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/79) | `310feeaf531fa1c0e771d1bcf06294c7a72b7ffd` | `a7a2c5b3cbc16390e30061329adfbebc835dc8b3` | 广播/硬抑制/正确拒绝采样，18项128目标后缀 |
| [#75](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/75) | `f92f3faf0ba8de5b8eabfb67294253d4e06a230f` | `3fe790ecc2d4849662b60216922fd45dc4300848` | 实现与远端评测阶段，最终26项待齐 |
| [#80](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/80) | `0d7367122d178402e6f80edac3f12fa3e492c41d` | `e24414b8f0ba47e8df46ba64475dbbf45568e2f4` | 偏移144条理想重放与score接口审计 |

最终科学集成`e24414b8f0ba47e8df46ba64475dbbf45568e2f4`。每项回读两父必须精确等于[base,head]，tree等于已审head tree，并验证祖先链；无force/bypass。GitHub原生checks/status没有失败、最新review无changes_requested、未解决线程0（本轮回执中CI/check列表为空，不称有CI跑过）。75/79/80从draft转ready是在源码/证据核验与明确阶段边界后。

## PR75：实现与提交阶段可合并，最终评测继续

独立审核严格Llama32层守卫、MHA/RoPE/cache及Qwen守卫隔离；cached多选首token、原候选顺序、KV与随机状态回滚、精确前缀/计分decode边界正确。PIQA validation1838、ARC-E test2376，zero-shot Harness0.4.8，无额外BOS。短题all-K不能证明长上下文筛选；Apple FP32独立预训练只是参照，不是同权重因果消融。

修复仅W8存储INT16→INT8，恢复FP32/算术/RNG不改，省4,328,521,728B；旧OOM/撤回记录保留。两个冻结源档案各88成员核验，新75源+job.sh共76运行文件匹配；旧CRLF换行等价有映射，签名原件未重写。8旧+18修复配置无重叠、恰好0..25。

本地使用小型随机32层HF Llama（Torch2.4.1 CPU、Transformers4.45.2）跑7原测试，另4独立检查：两模式打包/未打包32层前向与最终RNG逐位一致、原生BF16 SDPA包装一致、原生全因果多选参考4候选最大logprob误差4.768e-7。临时HF依赖已分类回收，不安装模型权重。

只读服务器门禁/封存原件：原2571完整WT2 BF16为4.979502845218782、335686目标；修复2584已READY、8个真实7B pilot通过。2026-10-21 08:39:24Z为16/26正式完成，2运行8排队。完成项JSON/doc实际SHA、行数、配置/源、32层与计分覆盖核验，不声称本次逐题独立重算全部官方指标。新增REVIEW_STAGE/REVIEW_CHECKPOINT两文件纠正旧GPU未验证描述。

Issue73验收明确允许远端提交且如实pending，因此本次阶段合并合理；26最终质量结论仍未验收，Issue73与既有回查继续。未来结果用同Issue后续PR，不重交健康数组或改冻结022/309快照。

## PR77：四条训练讨论稿

7/7制品blob/大小/SHA一致；Word与MD121文本块（59段+62表格单元）、4表/9链接一致。按普通讨论稿原范围未做页面渲染，不宣称版面视觉验收。五个完整WT2引用均回放到6位小数。

随机筛选网络256态精确边缘化，4例/196方向梯度有限差分最大6.024e-11；实际CTMC前向/有偏QK surrogate和真实V/O梯度区分正确。variable筛选与fixed8历史控制分开；平均预算不是硬配额，强制短前缀块不进BCE，512槽溢出不能静默裁剪。W8短流、三投影tanh、四输入随机筛选及有限链训练均是方案，未实现/执行训练，不代表质量或器件收益。Issue76已按用户补充明确授权更新关闭；amlink1219 STATUS保持当前集成原字节。

## PR79：科学结论通过，修复一处派生索引

19当前CPU合同通过，历史11与其重叠不相加。5冻结源94项blob、29只读原件（含26项PPL索引及私有capture）核验；168拒绝枚举、896拒绝历史递推、30单点稳态、642排除自身广播检查通过（最大约4.44e-16），另15同步非Gibbs反例。真实硬抑制15组和拒绝采样18组重放，除elapsed/capture路径外统计/源指纹一致。

18项CPU固定128目标后缀、144 NLL段、每配置3seed、24层，非完整WT2。BF16 20.212326；CTMC S64 23.159115±0.418371；同步κ12 104.556286±23.733673；块16κ12 22.621586±0.407899。不把短测块16较低外推为普遍优越；实际PPL候选最多512，2K为分布压力。

κ无穷排除自身，any/multi广播不修复同步转移偏差。正确新拒绝规则qi=sigmoid(delta_i−m ln2)，单1接受、多1拒绝、全0以2^-m接受参考；每轮接受权重为共同因子×[1,exp(delta)]，拒绝历史自适应m保留目标。独立提议/响应精度是前提；这是新直接类别采样，不是同步Gibbs改名，2.223/3.384/1提议轮不是芯片时钟。

发现P2：DIAGNOSTIC_MANIFEST中的派生文档DIAGNOSTICS_ZH.md仍写3123B/旧SHA，实际5787B/SHA9a25cc69…。只改该索引，原文/科学JSON/封存原件未动。完整修复后manifest三项逐字节匹配。

## PR80：公共偏移与分数接口（收尾追加）

PR79合并后作者单独发布OFFSET与score接口，故纳入本轮，未覆盖其进行中目录。冻结820ad7e归档13个Git blob与19合同通过；144条理想分布重放保留cap失败，实际统计/失败/复用状态完全一致。196个fixed_theoretical_log_expected_trials_per_row元素因NumPy FP32诊断舍入有至多1.1920929e-7差别，elapsed也不同，不能称原件逐字节复现。2K平坦S64自适应3.384轮/地址，预设11继续自适应3.227，固定11为2.663（理论期望约2.717）；真实512首地址3.770→2.833，整S64均值无改善。复用只重复同logits，不是下一token。不能将部分固定值失败推广到全部偏移无用。

当前Q/K、KV BF16，候选QK显式float后bmm/缩放FP32；诊断转FP64。8位驱动/电压码不等于R8均匀概率门限，约1/2K尾概率不能直接归零。温度/scale、m ln2与零态校正、mask独立门控、DAC/保持/归约反馈成本均需实现和标定。先score局部场、后独立INT8QK/INT32累加是建议，无新量化模型PPL或PPA验收。

## 发布、记忆与回收

旧科学文件逐blob保留，冲突仅本人STATUS/备忘录按历史增量合并；其他成员STATUS无覆盖。报告提交仅本轮文档、本人STATUS/HANDOFF和记忆；不会夹带私有NPZ/tar、模型/数据或凭据。摘要哈希验证表明原件一致，不代表独立重跑历史GPU全量评测。

Issue73/78继续开放，76用户额外授权后关闭，28维护继续。曾被自动审查拒绝关闭他人Issue76，已停下并获得人类明确补充授权后成功执行；没有绕过拒绝。可选code-review服务两次无法连接GitHub，使用原生API逐项门禁，仓库合并权限真实成功；Projects沿历史read:project限制待同步，本轮未重测。

canonical记忆原有未提交研究/清理/OFFSET文本先逐SHA备份并完整保留有序行，HEAD不reset；本次工作文件/root/报告blob同字节。恢复与源SHA见evidence/MEMORY_SYNC_PROOF.json。仅一个稀疏review WT，agent用Git对象/最小导出。报告实际合并后先逐SHA归档本轮scratch/ignored，再回收两个本人目录；实际执行看Issue55最终回执与本地project_archives/pr_review_issue55_20261021/RECOVERY_INDEX.json/CLEANUP_RECEIPT.json，本报告不提前声称清理已执行。

无新GPU/Slurm提交或取消、无修改冻结执行快照、无新训练/完整模型PPL/许可PT。该审计不替代Issue73最终26项或Issue78有限精度/新采样器模型/物理硬件验收。
