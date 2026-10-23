# 编码/恢复接合包（Issue121）

本包推进清单 T02/T04：复用 Issue107 的原算术核，在独立目录补充显式计数表示、有限结果槽 RTL，以及调用 Issue116 `Resource/Operation` 的逐输出调度适配器。历史 v6、原 RTL 和 Issue116 默认 FFN 均未改动。T02 的 STA/每操作能量与 T04 的完整 FFN 接合仍未完成。

## 已实现的边界

`arithmetic.py` 的编码入口接受完整 64 值 BF16/FP32 有限字，输出 B4、q/256、true-one 和原输入符号。NaN/Inf 编码明确拒绝；零、次正规数和最大有限数保留精确字级语义。恢复复用原整数/dyadic oracle：每 bin 的整数转 FP32（此处含除 T）、乘 W8 scale、按 bin0→3 顺序相加；跨 k 加法单独执行，不融合。

两类计数必须显式标识：

| 表示 | rail 的含义 | 位7权重 | 原恢复 RTL 可直接输入 |
|---|---|---:|---|
| `input_sign_twos_complement` | 输入符号 | −128 | 是，须满足宽度/格式 |
| `product_sign_magnitude` | 输入×W 的乘积符号 | +128 | 否 |

例如 W=−128、正输入的一次有效样本，幅度表示在负 rail 的 bit7 加1；若直接当原总线，会从 −128 错成 +128。软件 `normalize_counts` 将带标签计数归约为每 bin signed integer，不伪造转换后的原计数总线，也不声称已经实现这层转换电路。

极小数反例已固定：bins=(3,0,0,0)、top_exp=−145、T32、weight_scale=1.5，原 FUSED=0 得 FP32 字 `0x00000003`；旧周期表达式 `fp32(fp32(3*2^-145)*1.5/32)` 得 `0x00000002`。必须明确舍入顺序，不能据普通随机向量通过就默认两个模型完全等价。

## 完整操作与有限容量

`adapter.py` 每个编码组登记1次 `complete_encode_group64`，每个输出登记1次 `complete_restore_output_b4`，另登记1次 `cross_k_fp32_add`。64输出是64个完整恢复，不能作为一个标量核调用，也不乘旧72-op费用。

`Profile` 明确 latency、II、lane、每 lane depth、下游加法器资源。每个恢复在接受时预留结果槽，直到对应跨 k 加法完成才归还；这比出队就释放槽更保守。按注册顺序串联组释放和每 lane 的消费，防止名称排序或阻塞改变结果顺序。当前明确只支持一个活动编码组（`encoded_groups=1`）；多组流水属于后续 T06，不能把此限制隐藏为免费并行。

调用者传入 Issue116 的 API 和自己持有的 Kernel。`backend.py` 载入明确选择的 checkout，四个后端文件联合 hash 决定模块缓存身份。该包不携带另一任务尚未发布的周期核源码。当前重放冻结了本地已提交的 `cd27d980d9cfb68d7ed9761aba70d2faec4d4937` 中四个核心文件，精确 hash 见 `work/amlink1219/121/BACKEND_SOURCE.json`；首次冻结时远端尚无116 PR。发布后需在其最终公开 commit 再做兼容性回归，不能把本次作为116全部验收。

## RTL 协议包装

`rtl/` 复用 `nr_pot_encoder` 与默认 `nr_bin_restore(FUSED=0)`。每次输入握手预留一个完整结果槽；未完成和已完成未消费结果共享容量上限；下游停顿时数据/tag 保持稳定。同步复位清空在途操作和队列。原裸核的数值语义保持，恢复包装仅接受原输入符号/二补码总线。

| 包装 | 接受沿 k 后首次可见 | 最早输出握手 | 无停顿 II=1 所需最少槽 |
|---|---|---|---:|
| BF16/FP32 encoder | k+2 post-edge | k+3 pre-edge | 3 |
| literal restore | k+1 post-edge | k+2 pre-edge | 2 |

这些是功能 RTL 边沿，不是 STA 频率。周期适配 `Profile` 是条件调度参数，当前并非逐沿复制这两个包装；其信用释放、组串行和消费完成语义更保守。原有采样/存储/CDC 的全链逐沿对齐仍须与116正式整合。

## 本轮证据

入口 `results/cycle_20261023/SUMMARY.json`、`results/rtl_2773/VALIDATION.json` 和任务 `VALIDATION.json`。CPU重放覆盖 T16/T32/T64×两种计数表示×1/4恢复lane，共12例、1536次完整输出恢复；逐拍/事件全轨迹一致，结果与独立直接 W8 dot 整数参考加同一原恢复 oracle 一致。后者的独立性在整数dot，不是第二套编码/浮点恢复实现。

固定例均为两组64输入、64输出，300ns下游初始停顿、单加法器II2；12例均为2.97µs。这是刻意保留的下游瓶颈：增加恢复lane没有改善该条件例。计数生产是测试边界，未计真实SC周期，因此不能拿T16/32/64相同时长比较完整FFN性能，也不是新整模型质量结果。

RTL 在主服务器个人目录通过独立 CPU-only Slurm 作业运行，GPU显式屏蔽。保存源/输入/工具 hash、命令、应用和调度终态。27场景覆盖BF16/FP32编码与T32恢复、depth1/3/5、三seed，包含随机bubble、长停顿、顺序、同沿出入、在途/队列复位及极小数反例。恢复 T16/T64 目前为软件参考覆盖，未冒称本轮RTL已验证。

PPA、面积、每输出能量、STA达标频率均为未知；无DC/PT、新PPL、训练或GPU实验。需要继续完成116发布版本接合、完整FFN数据流、实际活动及工艺表征后，才能替换原费用或声称架构收益。

## 复现

在仓库根执行（Python标准库；需检出根目录 `format_conversion_rtl_20261016`）：

```text
python -B -m unittest architecture_tlm.encoding_restore_contract.test_arithmetic
python -B -m architecture_tlm.encoding_restore_contract.run_cycle --backend-root /checkout/with/pinned/cycle_v1 --out /new/output
```

设置 `ENCODE_CYCLE_BACKEND` 为该 checkout 根后运行 `test_adapter`、`test_review`。RTL命令：

```text
python -B architecture_tlm/encoding_restore_contract/sim/validate_ready_valid.py --iverilog /personal/tools/bin/iverilog --vvp /personal/tools/bin/vvp --build-dir /new/build --out /new/evidence
```

共享主机必须在CPU allocation内运行。测试输出目录须不存在，避免覆盖历史证据。
