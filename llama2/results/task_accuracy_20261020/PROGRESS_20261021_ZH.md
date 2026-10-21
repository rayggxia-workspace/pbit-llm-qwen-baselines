# Llama 2 7B任务评测进度：18/26已封存核验

2026-10-21 10:11:23 UTC（北京时间18:11）；Issue73；负责人jieruiz。

**本轮新增2项完整ARC-E FFN-only结果；当前18项completed、2项running、6项pending，0项缺失或无效。26项尚未齐，不能作最终联合S512结论。** 原PR75已实际合并3fe790ecc2d4849662b60216922fd45dc4300848，仅代表代码/提交/恢复阶段交付；本次同Issue后续独立分支task/73-results-followup，不修改或重跑健康推理。

## 已完成且三seed齐全的阶段表

PIQA1838题、ARC-E2376题；下表是逐题已存acc/acc_norm重聚合。概率组为三seed均值；单seed及总体标准差见检查点。独立官方process_results复算尚待最终收齐，本表不冒充最终独立验收。

| 任务 | 配置 | 完成数 | acc | acc_norm | 相对BF16，百分点 acc / acc_norm |
|---|---|---:|---:|---:|---:|
| piqa | 原BF16 | 1/1 | 77.8564% | 78.9989% | 0 / 0 |
| piqa | 仅FFN B4/T32/K32 | 3/3 | 77.8020% | 78.9989% | -0.0544 / +0.0000 |
| piqa | 仅Attention S128 | 3/3 | 77.1853% | 77.4392% | -0.6710 / -1.5597 |
| piqa | 联合S128 | 3/3 | 77.2942% | 77.8745% | -0.5622 / -1.1244 |
| piqa | 联合S512 | 2/3 | 待齐 | 待齐 | 不计算 |
| arc_easy | 原BF16 | 1/1 | 76.3047% | 74.6633% | 0 / 0 |
| arc_easy | 仅FFN B4/T32/K32 | 2/3 | 待齐 | 待齐 | 不计算 |
| arc_easy | 仅Attention S128 | 3/3 | 75.4068% | 73.8356% | -0.8979 / -0.8277 |
| arc_easy | 联合S128 | 0/3 | 待齐 | 待齐 | 不计算 |
| arc_easy | 联合S512 | 0/3 | 待齐 | 待齐 | 不计算 |

仅FFN的PIQA三seed均值接近同轮BF16；不能据此推及未齐的ARC-E或联合S512。旧3个OOM及15个取消项作为恢复历史保留，不计入26个唯一配置。

## 已有Apple FP32基线单列

| 原始模型 | PIQA acc / acc_norm | ARC-E acc / acc_norm |
|---|---:|---:|
| Apple Softmax 7B | 75.5713% / 77.0403% | 72.1801% / 68.7710% |
| Apple Sigmoid 7B | 76.4962% / 77.4211% | 73.2323% / 69.6970% |

以上复用APPLE_BASELINE.json和既有PR67，非新推理；独立预训练FP32模型仅作跨模型参考。

## 剩余作业与时间估计

- 2585_12：PIQA联合S512 seed2运行；2585_16：ARC-E FFN-only seed2运行。
- 2585_20～25：ARC-E联合S128/S512各三seed等待数组两卡并发名额。
- 按已完成PIQA测得的每decode调用时间、ARC-E的21776次调用估算，六项待运行任务合计约7.98 GPU小时。现有两卡继续可用时，含两项在运行任务尾部与争用余量，预计还需约4～6小时；若退回单卡约8～11小时。不是Slurm资源或结束时间保证。
- 保留原2572八项和修复2585十八项；未提交新GPU推理、未取消/修改数组，原snapshot不变。CPU核验2632已完成。

## 本次核验与限制

- 7项本地/远端CPU合同通过，覆盖篡改/重复逐题、24层误接、非completed及聚合不一致等拒绝路径；独立只读审阅未发现本次partial范围的阻断问题。
- 检查READY→TASK_DATA/identity/suite的SHA；冻结源实际字节、parquet、task YAML、Harness源和tokenized请求SHA；旧/新请求相同，模型revision及32层配置与已验身份清单绑定。未重复散列14GB权重，原预检证明保留。
- 18份完整JSON均为status=completed；逐题原件的SHA、大小、LF、全量唯一docid及所有候选token计数通过；聚合acc/acc_norm与逐题均值一致。
- 核对32层Attention/FFN的prefill/decode调用以及active/dummy行数，所有计分target覆盖；不足三seed不生成组均值。进度文件绝不计入completed。
- 本次没有独立执行官方process_results；最终收齐后须加载已锁定parquet/YAML，逐题重算官方指标与同轮BF16配对变化，再验收26项。检查点的complete只指封存合同齐全，不能替代最终质量验收。
- 注意力仍是unscreened有限CTMC：全部32层计分decode替换，multi-token前缀准确；短题all-K，不验证长上下文筛选。FFN在prefill/decode替换；没有8位p-bit驱动的新PPL/准确率或PPA。

原始检查点、SHA、测试日志及ETA：checkpoints/20261021T101123Z/；执行源86ccedc1f14432fc993b4032a9af7873bbf579c6；CPU Slurm2632，COMPLETED/exit0。大逐题原件仍在个人服务器，按检查点document_artifact索引恢复；不复制模型或数据。
