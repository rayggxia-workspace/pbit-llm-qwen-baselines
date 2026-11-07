# 当前100/250 MHz整机等面积数字基线准备

Issue236 / PR244，2026-11-07，rayggxia。复用旧数字任务checkout，不覆盖已封存17项或BF161888配置。这是预算/合同/工作量工具，尚不是已接合的数字周期模拟器。

当前目标：100 MHz/1088 KiB/33.284710 mm²；250 MHz/960 KiB/20.872325 mm²（旧TT概率核参考，待修复PPA后重算）。每种频率只做BF16_dense、W8_dense、W8_screen三种。共享存储容量、DRAM时序/峰值、有限DMA和计费边界一致，按整机总面积匹配，不将旧1728/1888lane套入新面积。

已完成：

- TARGETS.json冻结当前两版预算、5类可直接保留的宿主组件、PVT/时钟/容量与来源SHA。其余组件并未按0处理，必须由模块返回。
- WORKLOAD_AUDIT.json核算每层GU49,807,360、Wd24,903,680 MAC；dense QK/PV各8,388,608，SparQ粗筛＋精确QK为2,621,440，K128完整PV为524,288。模型按36层，head单独统计。
- 仅矩阵权重读取：全BF16约8.044544 GB/token，W8 FFN约5.354947 GB/token；按136.4606 GB/s的理想纯权重流下界约58.95/39.24 ms。没有计KV、metadata或等待，**不是预测token时间**。BF16/W8比较含量化节省，不能全部归因于随机计算。
- planner.py对资源ID去重，并在明确合法配置中选不超预算的最近面积点；缺模块、缺固定成本/时序接口时只输出pending，不给负数核、免费算子或假时间。当前PLAN.json六项均待接入。
- 四项测试通过：共享组件一次计费、合法粒度、预算不可行、操作数/权重量化边界、缺模块不能变成零成本基线。

需要转给其他模块的唯一说明文件为`architecture_tlm/module_handoff/DIGITAL_BASELINES_100_250_NEXT_ZH_20261107.md`，分别列FFN和Attention责任。现有代表核可以复用；仅对缺失接口/小SRAM映射补适配，不要求重新综合所有阵列。

运行：

```powershell
python -B architecture_tlm/equal_area_100_250_20261107/test_planner.py -v
python -B architecture_tlm/equal_area_100_250_20261107/planner.py --out <新计划.json>
python -B architecture_tlm/equal_area_100_250_20261107/planner.py --modules <合并后的模块bundle.json> --out <新配置.json>
```

模块bundle以`100/250`为第一层，BF16_dense/W8_dense/W8_screen为第二层；每项status=ready后才参与配额。必需字段：clock_MHz、SRAM_KiB、fixed_components（resource_id/area55_mm2/roles）、pool（resource_id/lanes_per_slice/area55_mm2_per_slice）、legal_pool_slices、entry_points和timing_contract。固定模块角色须覆盖FFN_nonmatrix、attention_control、reduction、QK_staging、output_format；公共host组件由TARGETS自动加入。允许有声明的宏/代理，但要给对应边界与来源，不把ready误写成RTL签核。

回传后仍需实际接入当前TLM执行路径，验证实际lane/端口/工作量与配额一致，完成解析单层门禁，再用相同原生LPDDR快照在EDA CPU跑36层。配额工具本身不模拟时序，SparQ/Softmax/PV也没有在此复制成第二套模拟器。

本轮无新GPU/训练/PPL/RTL/PT或完整TLM结果，无新数字电路台账run；不重复或取消旧健康任务。250概率核修复任务仍由Issue204继续。
