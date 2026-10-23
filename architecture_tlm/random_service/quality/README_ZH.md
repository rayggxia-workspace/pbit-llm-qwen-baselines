# 随机源质量随层级变化：可执行首轮诊断

2026-10-23采样间隔纠正：[旧比较器慢速采种复核](results/sampling_review_20261023/REPORT_ZH.txt)。原0.72～0.74只对应0.5us；同一波形10us固定lag为0.027～0.052。旧主链覆盖不足，不能据此否定慢速采种；换种周期不等于物理bit间隔。新增72条后处理记录，原189案例/报告原字节保持。

结果入口：[离线图文报告](results/20261023/REPORT.html)，[逐案例摘要](results/20261023/SUMMARY.json)，[逐层测量](results/20261023/STAGES.json)，[原始结果索引](results/20261023/ARCHIVE_INDEX.json)。用户副本为 `C:/Users/86134/Documents/a_P_BIT/远端上传/rng_quality_20261023.html`。

执行冻结源码本地Git为 `8a862a38cf6e4e46f50e719f8b2b3877db745c75`，上游基线 `6966739a5223680888bf0315f7bb4f73423a1ae6`。SOURCE_MANIFEST.json绑定8个准确执行文件，审阅/报告脚本在执行之后加入，不冒称属于原执行快照。Python3.12.14/NumPy2.3.5执行模型，Python3.8/NumPy1.24.4/matplotlib3.7.5仅生成图文。首次Python3.8后处理的SUMMARY/ARCHIVE_INDEX含CRLF，已签SHA原件按-text保留，不为排版重写；后续构建脚本明确写UTF-8/LF，复跑须使用新输出目录。

## 这次实际做了什么

复用Spectre任务38237164的9条长轨迹：裸源理想0.6V判决、旧比较器A(buffers_x2)、旧比较器B(b1_p2_b2_n2)，各噪声seed401/503/607，TT25°C，保留2ms～20ms。原归档224,767,631字节及9个波形成员逐SHA核对后在内存解析，仅保存紧凑比特缓存；没有新跑Spectre或公开PDK。bare基准20ns，比较器100ns；分别按100ns、0.5µs、1µs、2µs抽样得到36项诊断。比较器是旧10nA版本，不是待评估的新高速共享比较器。

主链用0.5µs物理抽样，另加IID合成和P1=0.6/保持概率0.9的Markov合成输入，三seed；直通/Von Neumann两种候选处理；三种现有后端；仅启动与1024拍换种；两个端点同步请求各4096帧，共180个案例。额外9个重复种子负对照，总189项全部生成完成。完整模型类Endpoint、SeedIngress、RandomNetwork及generate复用原实现，未改动源码和默认参数。

统计只计成功生成帧，不把等待、反压保持或预热当作独立样本。两个端点请求原子同步，跨端点比较同时对齐时钟沿和样本序号。下游ready恒真，本轮不是随机回压覆盖。种子来自预采集记录，回放设置1个32bit字/数字拍；这是隔离质量的条件，不证明物理源有该吞吐。0/1024是启动/加速换种对照，未实际执行1亿拍或长时间漂移。

## 结果及其适用范围

- 0.5µs时，裸源相邻相关系数约0.0007～0.0053；旧比较器约0.7176～0.7412。来自不同电路的独立仿真，不能称严格配对因果差值，也没有同时测量多源空间相关。
- 旧比较器经VN后P1约0.4905～0.5074，但有效输出序列的rho1约−0.3228～−0.2473；保留率约6.33%～7.27%。去偏没有等同于去相关。VN是实验候选，不是本架构已存在的调理RTL，也没有通过NIST认证。
- GF64：q=128输出满足 `b0 XOR b1 XOR b2 XOR b3 = 0`，所有63个GF案例均逐帧满足；64路帧异或差分秩不超过32。现有两两秩检查不保证四路联合独立，重播种不能解除固定映射关系。测试并未在其他全部阈值证明同一关系。
- 重复种子对照：三后端所有9例，两个端点输出完全相同。边缘P1接近0.5不能检出这种分发错误；“新取得”也不保证两个种子数值永不碰巧相同。
- AND探针目标0.25×0.75=0.1875；共用同一个随机字会变成0.25。合法FFN共享与非法乘法共享分开。K32共享输入64维W8玩具点积和候选帧仅作局部诊断；本轮未运行完整FFN、Attention采样器或模型PPL，不继承旧模型质量。

测量包括P1、8个时延的相关系数、T32/T128非重叠块方差、8bit直方图/CDF、13个q阈值响应、端点间及同帧跨路相关、零种子拒绝和重复状态。大数量的最大相关/误差存在多重比较效应，不直接设通过阈值或用它排名不同宽度后端。各记录及窗口可能仍相关，三个seed的范围不是置信区间。边缘 `-log2(max(P1,1-P1))` 明确不是熵率；PRNG不产生新的物理熵。

## 复现命令

需要Python>=3.10、NumPy运行模型（原backends使用int.bit_count）；绘图另需matplotlib。以下命令在仓库根运行，输出目录必须尚不存在：

```powershell
python -m unittest architecture_tlm.random_service.quality.test_quality -v
python -m architecture_tlm.random_service.quality.prepare_physical --archive <原始tar.gz> --audit <archive_audit.json> --out <新的物理缓存目录>
python -m architecture_tlm.random_service.quality.run --physical <物理缓存目录> --out <新的结果目录> --raw-out <新的NPZ目录> --frames 4096
python -m architecture_tlm.random_service.quality.audit_results --results <结果目录>
python -m architecture_tlm.random_service.quality.report --results <结果目录> --delivery <新HTML路径> --archive <新原件归档目录>
```

原波形归档及物理比特缓存路径/SHA见PHYSICAL_INPUT.json；189个数字数组的路径/字节/SHA见SUMMARY.json。原始完整JSON保存在稳定project_archives目录，Git只保存摘要和索引；不把结果目录中的ignored大JSON当成唯一原件。配置、端点阈值和种子可由CONFIG及固定脚本恢复；模型、tokenizer、语料SHA不适用，因为没有运行LLM。9项机制测试和1269项逐原件/算术/结构核对通过；不是1269个独立随机性测试。

后续可调 `--frames` 观察样本长度。增加采样间隔/调理/换种矩阵时应另存配置与结果，不覆盖本批。下一阶段需要同一多路阵列同时采样、公共Vref/供电/列共享影响、PVT与重启序列、合格熵率评估；更长PRNG输出、更多epoch和完整计算消费者分别增加。没有这些证据前，不能认证独立位率或用本轮选定最终换种周期。

参考：[NIST SP800-90B](https://csrc.nist.gov/pubs/sp/800/90/b/final)区分熵源与调理验证；[NIST SP800-22](https://csrc.nist.gov/pubs/sp/800/22/r1/upd1/final)指出统计测试不能单独认证发生器。本轮仅借用这些证据边界，没有声称执行其标准测试套件。
