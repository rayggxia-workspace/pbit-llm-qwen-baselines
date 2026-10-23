# 真实随机服务接入整机：完成结果（2026-10-22）

**40/40项完整模型事务仿真完成，93项机制/回归检查及1421项归档与模型契约核对通过。** 默认源与计算核同为100MHz；SRAM保留已校准80MHz。旧52项原件没有改写。

这些是完整24/32层、batch1 decode的**合成路由TLM情景**，不是模型推理、PPL、GPU时延、芯片实测或新的PT/DRAMSys运行。源实际产生的字和响应决定采样地址；FFN数值张量仍是宏级工作量。

## 同时钟与实际协议

- 计算核、SC消费、随机端点、种子总线、采样器：100MHz/10ns；不一致直接拒绝。SRAM80MHz/12.5ns，已有20ns CDC代理保留，未声称物理CDC已实现。
- FFN本地LFSR32，R8、共享64、B4/T32/K32。SAVE锁epoch、32拍流式生成/消费、RESTORE重放、最终RELEASE。源和SC计算重叠；孤立消费段含startup/drain是34拍，并未先生成32拍再计算32拍。
- Attention使用有限Bivium端点池；一端点20个R8/拍。筛选真实q/256判决；PV真实160bit帧取32bit偏移，未用位也收费；赢家/拒绝进入同一个持久时钟网络。
- 每100拍供应一个32bit合格种子字，启动10拍；Bivium6字＋5拍预热，LFSR1字。默认1亿拍到期换种，FFN重放锁定期间延后；跨查询/层/后续token保留源状态。种子fixture仅用于可复现仿真，非熵认证。
- 无随机流SRAM、序列FIFO或第二套概率副本；端点自身状态/checkpoint/单响应寄存器存在。Attention阈值编程/保持、LUT、FFN分层比较前端等额外PPA仍未知，不宣称其存储和成本为零。

## 新旧接口整机对照

表中旧接口是相同执行版本显式选择`local_prng_interface`，新接口是`integrated_service`。SC为固定W8、四档T32/K32。默认PV预算L/16：2K128，8K512。Qwen24层，Llama1/2均32层；Llama只测2K、单seed的形状与存储连通，不是新模型准确率。

| 模型/长度 | FFN / Attention | seed | 旧接口 ms/token | 真实源 ms/token | 增减 % |
|---|---|---:|---:|---:|---:|
| llama1 / 2048 | bf16 / exact | 0 | 3268.89527 | 3268.89527 | +0.0000% |
| llama1 / 2048 | sc / pv | 0 | 2626.08742 | 2626.22827 | +0.0054% |
| llama2 / 2048 | bf16 / exact | 0 | 3268.89527 | 3268.89527 | +0.0000% |
| llama2 / 2048 | sc / pv | 0 | 2626.08742 | 2626.22827 | +0.0054% |
| qwen / 2048 | bf16 / exact | 0 | 234.36001 | 234.36001 | +0.0000% |
| qwen / 2048 | sc / exact | 0 | 201.67681 | 201.72241 | +0.0226% |
| qwen / 2048 | sc / pv | 0 | 200.71081 | 200.75906 | +0.0240% |
| qwen / 2048 | sc / screen_exact | 0 | 198.72286 | 198.80111 | +0.0394% |
| qwen / 2048 | sc / screen_pv | 0 | 197.93816 | 198.00316 | +0.0328% |
| qwen / 2048 | sc / screen_pv | 1 | 197.94421 | 198.03811 | +0.0474% |
| qwen / 2048 | sc / screen_pv | 2 | 197.95691 | 197.99076 | +0.0171% |
| qwen / 8192 | bf16 / exact | 0 | 260.45281 | 260.45281 | +0.0000% |
| qwen / 8192 | sc / pv | 0 | 223.73941 | 223.78996 | +0.0226% |
| qwen / 8192 | sc / screen_pv | 0 | 202.80766 | 202.83611 | +0.0140% |

BF16准确对照的时间、DRAM/SRAM流量和阶段时长逐项一致。新源改变随机地址，差值包含候选并集、V读取和响应量化变化，不能全部解释为协议成本，也不能依据更快的个别采样结果声称同质量加速。

## 赢家/拒绝的完整模型连通诊断

以下S8、赢家倍率1，专门检查完整模型调用链、实际源、回压与收费。**不是默认S128/赢家8倍预算的完整模型结果**；没有宣称S8质量可接受。原104项扫描在0完成、0失败时主动取消，取消计划和原因完整保留于v2；本表没有填入未完成的全预算案例。

| 方法 | seed | 旧接口 ms/token | 真实源 ms/token | 增减 % |
|---|---:|---:|---:|---:|
| screen_rejection S8 | 0 | 203.34976 | 201.38461 | -0.9664% |
| screen_rejection S8 | 1 | 203.11126 | 201.31136 | -0.8862% |
| screen_rejection S8 | 2 | 203.15916 | 201.35851 | -0.8863% |
| screen_winner S8 | 0 | 197.53006 | 197.42351 | -0.0539% |
| screen_winner S8 | 1 | 197.53771 | 197.41111 | -0.0641% |
| screen_winner S8 | 2 | 197.55016 | 197.41281 | -0.0695% |

## 周期、字数和功耗边界

| 真实源案例，seed0 | 100MHz总周期 | FFN真实R8字 | SAVE / RESTORE / RELEASE | 源端点条件能量 mJ | 源端点面积 mm² |
|---|---:|---:|---|---:|---:|
| qwen / 2048 / screen_pv | 19800316 | 321024 | 2160 / 7872 / 2160 | 1.372797 | 0.254466 |
| qwen / 8192 / screen_pv | 20283611 | 321024 | 2160 / 7872 / 2160 | 4.914648 | 0.892410 |
| llama2 / 2048 / pv | 262622827 | 4227072 | 7552 / 124544 / 7552 | 1.690170 | 0.022486 |

源端点价格绑定任务38322118、100MHz、55nm SS1.08V125°C报告及SHA；证据索引在[中央数字仿真记录PR111](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/111)。该PR尚未自动合入本分支，所用数值与出处已独立固定在`configs/rng_ppa100.json`。按真实active/idle周期做有条件插值，原PWR-981/库外推、无CTS/SPEF/SDF限制保留；FFN只采用原生LFSR端点成本，未再叠加边界不同的FFN共享顶层价格。

上表只包含已实例化原生端点。完整随机模块和整机能量/面积仍为null：全局种子材料/总线/仲裁、LUT/阈值编程、FFN共享比较/分层/广播、互连/时钟及大量SC与普通算子PPA未齐。`priced_subtotal`不是总能量，禁止据此宣称整体能效倍率。512MAC/周期、64向量路、16非线性路以及配置/恢复/编码吞吐仍是显式假设。

SRAM/DRAM按真实地址范围、容量、bank资源、物理突发和有限请求窗口执行；没有把K/V逻辑保留率直接当物理读取率。默认外存是Link情景，未在本次调用DRAMSys；已有桥接入口保留。

## 可复核证据

- 执行源：`31aa4fa31fbfb7d74629b54811936ac30a41c250`。`results/integrated_rng_20261022_v3/EXECUTION.json`固定代码、配置、模型形状、校准和随机后端依赖的Git字节SHA。
- `PLAN.json`40项；`SUMMARY.json`全部complete且0失败；`ARTIFACT_MANIFEST.json`逐文件字节SHA；40个DONE及逐case JSON分别封存。
- `work/jieruiz/96/integrated/AUDIT.json`：1421核对，含全24/32层覆盖、输入配置SHA、种子字/加载记录、网络时钟、实际帧产生/消费、FFN波次重放公式和互斥收费。
- 93项机制/回归检查：11新增接入、21旧整机、11旧薄接口、19原源、18v5、10v4、3补充；日志在同一work目录。`check_extra.py`提供后3项的可复现源，重放日志独立保存，不重复计数。
- v1完整Qwen pilot独立封存、v2取消计划、初始失败与修正记录完整保留，不计入40项。Issue95原模型/RTL未改。
- Bivium CPU块求值器与1000随机状态的逐位参考一致；稳定idle跳事件与原逐拍协议/状态/计数/种子记录一致。CPU运行耗时不是芯片时间。

当前q/256 sigmoid网格0.125改变数值响应，尤其极小拒绝概率；不能继承旧理想源PPL。旧串行Ising oracle没有本后端实现，显式拒绝该组合。旧架构检查台/52项快照未自动刷新为本版，查看本报告及新结果目录。

```sh
python -m unittest architecture_tlm.unified_v6.test_rng_integrated -v
python work/jieruiz/96/integrated/check_extra.py
python -m architecture_tlm.unified_v6.run --model qwen --context 2048 --ffn sc --attention screen_pv --output NEW_DIRECTORY
python work/jieruiz/96/integrated/audit.py
```

重跑整机先提交执行源码并使用新目录；审计脚本审计已封存v3且不覆盖既有AUDIT，重放时调整输出路径或在临时checkout运行。此次无GPU/Slurm/训练/PPL/RTL/DC/PT，也没有改动其他成员执行快照。
