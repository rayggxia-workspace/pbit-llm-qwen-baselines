# LLaMA-1 7B 的独立 DRAM 情景

负责人：@jieruiz；Issue #12。这个目录仅包含 LLaMA 的外存配置、桥和验证，不覆盖 Qwen 历史数据。

使用 **2 通道 × 每通道 2 rank × 每 rank 8 颗 4Gbit x8 DDR4 = 16GiB**。每个 die 的几何、电流和时序保持 4Gbit 情景，增加的是 rank，不是把 4Gbit 电流随意套给 8Gbit die。RANK_BIT 为 `[33]`；原 BYTE/COLUMN/CHANNEL/BANK/BANKGROUP/ROW 位不变，地址位 0～33 无遗漏、无重复。

适用主场景为原生不超过 2K 上下文、单 token decode。完整 BF16 权重加 2K KV 可以容纳；不能据此声称 8K 的 BF16 地址空间也能装进 16GiB。模型地址分配器还必须对实际权重、KV、摘要总量做最终容量检查。

| 配置 | 低功耗策略 | 用途 |
|---|---|---|
| `configs/ddr4_2ch_2rank_Staggered_core_limits.json` | Staggered | 主低功耗情景 |
| `configs/ddr4_2ch_2rank_NoPowerDown_core_limits.json` | NoPowerDown | 关闭低功耗的成对对照 |

两者都采用 Issue #5 / PR #6 溯源的 Micron 4Gb x8、Rev. A、DDR4-1866、正常温度电流限值。来源是 Micron 原数据手册 Rev. M 03/2020 表 146 及注 21～23，PDF URL 与 SHA-256 见 `micron4gb_reva_1866_limits.json`。删除旧 iBeta 覆盖，使用工具 iBeta=I0 的默认约定；没有采用“VPP-PD 电流置零”的诊断配置。

**这是有来源的核心电流限值情景，不是实测典型功耗。**原 I/O 参数、PHY、控制器和板级损耗未校准；多 rank 拓扑与时序是架构情景，没有完成 DIMM/板级时序认证。整体比较应分别报告 DRAMPower core 和 interface，后者保留为代理项。

## 扩容后的背景能量不能漏算

以下是同一状态的电流公式结果，尚未乘实际驻留时间，不是一次 LLM 运行的平均功率。

| 状态 | 每通道每 rank，W | 全部 4 个 rank-channel 同状态，W |
|---|---:|---:|
| Precharge 待机 | 0.4824 | 1.9296 |
| Active 待机 | 0.6456 | 2.5824 |
| Precharge power-down | 0.3480 | 1.3920 |
| Active power-down | 0.4824 | 1.9296 |
| 正常温度自刷新 | 0.2520 | 1.0080 |

DRAMPower 6.3.1 的 DDR4 核心计算逐 rank、逐 device 计费。已有桥导出全部 rank 的状态时间，不应再把每通道结果乘 2 个 rank 或 8 颗器件，否则重复计费。若独立分析低功耗驻留，使用 `rank_stats`；RD/WR 命令则按该 rank 的 16 个 `bank_stats` 求和，不能读取未聚合的 `rank_total.commands` 作为命令总数。

## 已执行的验证

2026-10-17，使用个人项目 `/home/Hongjie_Zeng/projects/pbit-llama7b-tlm-20261017/dram_smoke/` 做 CPU 小测试，未提交 GPU 工作，也未修改旧桥目录。

- 本地预检查：2 个配置的单 die 容量、rank/channel/device 数、电流/电压、iBeta、全部地址位及低功耗状态功率通过。
- 复用已构建的 `pbit-pv-stream-v6-20261016/build/pbit_dram_bridge_sg_v6_audit`，握手返回 **17,179,869,184 bytes**，支持 `scatter_gather_v1`。
- 每个配置向 rank 0/1 × channel 0/1 各发一次 64B 写、一次 64B 读；再发跨 rank/channel 的 4 地址 scatter read。每例共 **8 个读 burst、4 个写 burst**，全部完成。
- 每通道实际导出 2 个 rank 状态、32 个 bank 状态；每个 rank 都有 RD 和 WR；DRAMPower core 分项求和残差通过。
- 这些事务不带存储数据载荷，验证的是地址、命令、完成时间及功耗统计通路，**没有验证读回数据内容，也不是全模型 DRAMSys 结果**。

第一次检查错误地要求 `rank_stats.commands` 含 RD/WR，因 DRAMPower 将它们记录在 bank 级而失败；修正检查后重跑通过。配置与桥未因这个测试问题改变。最终原始 JSON 和日志保存在 `results/bridge_smoke/`；`results/preflight/` 为本地静态检查。

复现（Python 3 标准库）：

```sh
python architecture_tlm/llama7b/dram/audit_dram.py --output NEW_PREFLIGHT_DIR
python architecture_tlm/llama7b/dram/test_dram_config.py
python architecture_tlm/llama7b/dram/audit_dram.py \
  --bridge /path/to/pbit_dram_bridge_sg_v6_audit \
  --output /verified/personal/project/NEW_PROBE_DIR
```

新验证应使用新的输出目录，保存其配置、源码及结果字节，不覆盖已引用的结果。

## 桥和上游版本

`CMakeLists.txt` 可在新 build 目录构建本目录的 `bridge_sg_v6_audit.cpp`。默认获取 DRAMSys 固定提交 `9f15aaf1fe6f05ff16a2e521a20a96f3bfe29d52`（5.6.0）；该版本依赖 DRAMPower 6.3.1、DRAMUtils 1.16.0、SystemC 3.0.2。也可通过 `-DDRAMSYS_SOURCE=/path/to/vendor/DRAMSys` 和 CMake FetchContent 的各 `FETCHCONTENT_SOURCE_DIR_*` 指定已核查本地依赖；不要在已有 build 内覆盖编译。

```sh
cmake -S architecture_tlm/llama7b/dram -B NEW_BUILD_DIR -DCMAKE_BUILD_TYPE=Release
cmake --build NEW_BUILD_DIR --target pbit_dram_bridge_sg_v6_audit -j 4
```

本轮复用旧二进制，没有重新编译。实际 CMake cache 的依赖目录、版本文件、桥源码和运行二进制哈希另见 `BRIDGE_PROVENANCE.json`。握手本身不认证库版本；不能只看到 `ready` 就声称固定提交得到验证。

来源和字节变换见 `SOURCE_MANIFEST.json`；本目录文件校验和见 `manifest.json`。本次不发布厂商数据手册、工艺库、权重或凭据。
