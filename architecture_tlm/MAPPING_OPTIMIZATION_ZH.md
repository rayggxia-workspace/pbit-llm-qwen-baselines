# ZigZag/LOMA映射接入与固定资源调度实验

新增模块，2026-10-15。原`system_decode.py`、既有配置和历史结果保持原样。

## 实验入口

- [完整结果](results/mapping_20261015/RESULTS_ZH.md)：固定外存策略的优化前后、允许选择电源策略的最终结果、下界和适用范围。
- [映射适配器](zigzag_mapper.py)：调用真实ZigZag 3.8.5 LomaEngine和MemoryAllocator，不以自编启发式冒充LOMA。
- [新调度](mapping_decode.py)：有限双缓冲、pin/bypass及提前发出权重请求；仍使用原有片上Link与真实DRAMSys接口。
- [搜索与验证](run_mapping_optimization.py)、[支持空间穷举](exhaust_mapping_candidates.py)、[审计和报告](report_mapping_optimization.py)。

## 资源与语义契约

本次限定已有Qwen2.5-0.5B形状、batch1 decode、8个64×64随机阵列、512 MAC/cycle数字单元、16MiB权重SRAM、1MiB scratch、100MHz和原32源。所有前后与数字/p-bit路线使用同一物理资源，并计入未用单元待机。

输入样本数4096、原始概率位数、源供给、三类重放/部分和统计及SC输入tile外循环不变。比较器、归约和数据流的数字宏成本沿用旧模型，没有直接使用ZigZag的数字MAC成本替代p-bit过程。

LOMA以64×64逻辑任务块表达GEMV并检查存储映射。当前适配器把合法循环前缀投影到可执行的连续DMA粒度，再由本地模型重评分。尚不执行任意LOMA循环重排。输入逻辑数据的映射与实际随机重放容量分开核验。

权重驻留和staging相加不超过16MiB；固定128KiB块时两块staging为256KiB，剩余15.75MiB用于静态pin。Attention双缓冲与Q/输出状态单独检查不超过1MiB。既有完整模型仍采用聚合带宽，并未扩展为完整bank级片上模拟。

## 复现

映射工具需要Python≥3.11、`zigzag-dse==3.8.5`。可在独立Python环境安装`mapping_requirements.txt`。本地会优先使用`.deps/zigzag385`中的隔离依赖；下载包hash见`.deps/zigzag_dependency_manifest.json`。仿真与远端验证本身不依赖ZigZag。

```powershell
python architecture_tlm/zigzag_mapper.py
python architecture_tlm/checks/test_mapping_decode.py
python architecture_tlm/run_mapping_optimization.py
python architecture_tlm/exhaust_mapping_candidates.py
```

先在简化模型中搜索，在同一上下文对每条路线穷举支持空间。采用EDP作为选点目标，并保留最快、最低能量结果。完整空间为每个上下文数字104点、p-bit208点；两个上下文共624点。

在已有DRAMSys执行环境中，逐项运行：

```bash
python3 architecture_tlm/run_mapping_optimization.py --mode validate \
  --selection architecture_tlm/results/mapping_20261015/selection.json \
  --bridge /path/to/pbit_dram_bridge --context 2048 \
  --variant fixed_sc_exact --which after --policy Staggered
```

`context`取2048/8192，`variant`取digital_int8_ffn/fixed_sc_exact，`which`取before/after，`policy`取NoPowerDown/Staggered。16组均需执行，随后运行：

```powershell
python architecture_tlm/report_mapping_optimization.py
```

本次服务器项目为`/home/Hongjie_Zeng/projects/pbit-mapping-20261015`，复用既有DRAMSys可执行文件；Slurm任务1551和1563。结果中的源码hash、DRAM配置hash、bridge二进制hash和批处理记录用于审计。本次没有更换服务器，也没有重新编译DRAMSys。

## 下界与限制

时延分别报告资源工作量界、必要通信界及保持本轮阶段/RNG服务的理想无访存诊断。能量界用不变计算、必要SRAM动作、DRAMPower RD/WR公式和最低驻留功率；忽略ACT/PRE/刷新等正开销。它们都是明确条件下的乐观界，不是可实现最优调度。

同一混合ASIC的路线比较，不等于重新设计最优同面积纯数字ASIC。核心功率、片上SRAM和数字MAC仍是现有参数；DRAM示例vddq=0，PHY、CTS、host、prefill未覆盖。没有新增硬件数值精度/PPL验证。

64×64保留为已标定核心原语；DMA粒度独立搜索。更换物理阵列形状需要重新限定面积、总并行资源和归约/互连成本。
