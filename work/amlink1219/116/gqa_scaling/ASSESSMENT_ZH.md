# 完整2K候选/7query exact GQA：静态规模与有界小probe

结论：本轮不启动2K实跑。当前Kernel的pending/scoreboard全表扫描表现出接近二次增长，不能可靠满足20分钟CPU预算。没有捕获2K私有fixture，也没有发起2K服务器作业。

小probe是7head、D64/Dv64、全部候选、exact模式、event-only；K/V/operand slot默认各2，memory window4。每个子进程限30秒，N64/N128都正常完成，未触发timeout。所有K/Q为0，V为确定性有限值，目的是同形状图规模计时，不能解释为真实模型质量。

| context | 操作数 | 访问事件沿 | 建图秒 | 事件执行秒 |
|---|---:|---:|---:|---:|
| 64 | 2116 | 2925 | 0.0713 | 4.9668 |
| 128 | 4164 | 5752 | 0.1337 | 21.7764 |

context翻倍，事件执行时间约4.38倍。队友在服务器的真实context64同构图为2116操作、2925事件沿、event 5.096秒，量级与此本机小probe一致；该服务器数字由队友提供，正式证据以其Slurm2782公开回执为准。

2K×7head exact预计 `32×2048+68=65,604` 个操作。K阶段读取/释放各2048次、cache读取/QK各14,336次，V阶段同样规模，另加head与union控制。初始pending约32.8K；每事件遍历pending，memory hazard还需扫描历史操作。这是性能限制，不是数学结果不支持。

按N128的执行时间做平方风险外推，`21.7764×(2048/128)^2≈5575秒`，约93分钟。此数不是2K测量、不是完成时间承诺，也不是硬件时延。即便绝对系数有变化，已不足以支持20分钟预算内的可靠执行判断；因此没有做更大的探测或重复超时。

静态容量边界也必须显式调整：candidate capacity从默认512改为至少2048；exact单head local state需33,344B，默认32,768B会拒绝，可配65,536B。7head score预算为458,752B，低于group默认1MiB。K/V目录metadata为 `2×2048×(12+ceil(7/8))+7×16=53,360B`，低于默认64KiB。上述是完整2K候选的资源要求，不能缩成64ctx再按倍数声称完成。

已增加 `run_gqa --event-only` 显式入口，实际独立小例核实报告为 `mode_equivalence.checked=false`、`equal=null`。将来大例即使event-only成功，也不能继承64ctx的双模式已测结论。后续先以保持完整trace等价为门改进pending/依赖/地址区间索引，再在新提交重新测扩展规模。

规模优化已有PR125的独立工作在接续；本任务不读取复制其未发布实现，也不另做重复优化。待其公开固定版本后再验证共享后端兼容性及2K规模。

复现小probe：`PYTHONPATH=<repository> python -X utf8 -P work/amlink1219/116/gqa_scaling/probe_scale.py --out /new/probe`。源码/未提交补丁散列在RESULTS.json中明确记录；当时仅runner的event-only入口与说明有未提交改动，所测GQA/Kernel字节仍为f94c9db。stdout保留原始小probe计数。
