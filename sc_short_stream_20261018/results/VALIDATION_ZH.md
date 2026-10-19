# 2026-10-18 实际 RTL 功能与活动窗口验证

本报告是数字 RTL 仿真记录，不是 DC/PT 功耗、SRAM 评测、芯片实测或真实模型 PPL。源码基线为 workspace `3553996bf014a29dee7fdb2250a3965e8fd881a4`，新增源码是该基线上的独立补丁；各 JSON 记录本次实际源码 SHA-256，`SOURCE_PROVENANCE.json` 给出来源与汇总。Icarus Verilog 12.0，100 MHz 合成输入激励。

| 本次实际运行 | 配置数 | 帧数 | 逐拍核对的有效样本 |
| --- | ---: | ---: | ---: |
| 五种主模式 × 内/外源 × N1/N8/N64，起始种子 0x13579bdf | 30 | 210 | 196,224 |
| strat64/128、N64、内部源，另两个种子 0x2468ace1/0xdeadbeef | 4 | 28 | 2,688 |
| strat256 控制，N64、内/外源，确认无随机源推进并恢复精确枚举 | 2 | 14 | 3,584 |
| 合计 | **36** | **252** | **202,496** |

全部通过。逐拍核对包括门限、比较位、signed W8 空间/时间精确和、样本计数与完成脉冲；覆盖 busy start/seed_load 被忽略、start 与 seed_load 冲突、valid 停顿、同种子跨停顿重播、帧边界 checkpoint 重播、0 种子规范化。输入幅度覆盖 q0/q1/q2/q26/q128/q255，独立符号；权重使用 -128/127/-1/0 边界模式，是人工压力数据，不是模型权重分布。

`rtl/sc_ss_fixed_tops.sv` 的全部 **31 个定型 top** 都实际通过 Icarus elaboration。body 与 integrated 使用同一 `sc_ss_exact_body`，故上述集成逐拍和也覆盖其算术逻辑；threshold-only 包装层没有声称额外单独的数值/PPL 评测。

另外实际生成 **7 个**单帧 VCD：五个主模式的 integrated 内部源，统一 q1/2、种子 0x13579bdf；以及 strat128 sampler-only 内/外源各一个。五模式窗口分别为 IID4096=40,970 ns、IID128=1,290 ns、strat64=650 ns、strat128=1,290 ns、enum256=2,570 ns。均恰好包含 1 个启动拍加 T 个有效拍，reset/seed_load 不在窗口内。原始 VCD 已裁剪并平移到首时间戳 0，截止点 `$dumpoff` 人为 X 块已删除，DUT 活动窗口内 X/Z 检查为 0。**这些是 RTL 活动波形，未运行门级功耗仿真，不证明 PT 注释覆盖率。**

其余完整的 3 seed × 5 case × 5 模式功耗激励矩阵未在本次全部生成；脚本保留重跑能力。ACC22/21 的面积/功耗优化、真实 PRNG 相关性导致的模型 PPL、SRAM/接口、广播布线与上游 seed 保持状态尚未表征。

执行命令（在本目录父级 Git 根）：

```sh
python sc_short_stream_20261018/sim/run_sim.py --seeds 0x13579bdf --out sc_short_stream_20261018/results/final_local
python sc_short_stream_20261018/sim/run_sim.py --presets strat64 strat128 --n 64 --rng 1 --seeds 0x2468ace1 0xdeadbeef --out sc_short_stream_20261018/results/extra_seeds_local
python sc_short_stream_20261018/sim/run_sim.py --presets strat256_control --n 64 --rng 0 1 --seeds 0x13579bdf --out sc_short_stream_20261018/results/enum_control_local
python sc_short_stream_20261018/sim/run_sim.py --power --rng 1 --cases 1 --seeds 0x13579bdf --out sc_short_stream_20261018/results/power_representative_local
python sc_short_stream_20261018/sim/prepare_active_vcd.py sc_short_stream_20261018/results/power_representative_local
python sc_short_stream_20261018/sim/run_sim.py --power --presets strat128 --rng 0 1 --cases 1 --seeds 0x13579bdf --sampler-only --out sc_short_stream_20261018/results/power_sampler_local
python sc_short_stream_20261018/sim/prepare_active_vcd.py sc_short_stream_20261018/results/power_sampler_local
```

Windows 实际使用 bundled Python 和项目历史 portable Icarus，路径及工具版本记录在 JSON。该旧 Windows Icarus 在受限进程环境会出现系统 DLL 重定位错误；在获授权的正常进程执行环境运行后完成上述全部仿真。不是通过静态 Python oracle 代替 RTL。

归档小文件：`functional_main_20261018.json`、`functional_extra_seeds_20261018.json`、`functional_strat256_control_20261018.json`、`top_elaboration_20261018.json`、`power_representative_20261018.json`、`power_sampler_20261018.json`、`active_vcd_representative_20261018.json`、`active_vcd_sampler_20261018.json`。43 份实际仿真文本日志压缩于 `simulation_logs_20261018.zip`，各原始日志 SHA 仍保存在对应 JSON；大型 VCD/VVP 留在上述被忽略的本地输出目录，没有上传 Git。
