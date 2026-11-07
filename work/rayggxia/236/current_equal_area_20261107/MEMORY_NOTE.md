## 2026-11-07 Issue236：当前100/250数字等面积基线准备与模块交接

用户要求两版最新概率硬件建立等面积数字基线，宿主可做部分先做、专门模块需求写文件。复用Issue236/PR244、task/236-fair-digital-20261105原checkout，不重跑/覆盖旧67.5mm²、2.5MiB、17项及1888BF16成果。新目标1001088KiB/33.284710mm²；250960KiB/20.872325旧TT参考，修复PPA待收后按17.963887+3A重算。选BF16dense、W8dense、W8同SparQ K128准确PV三类×两频率，整机总面积匹配，SRAM/DMA/外存/计费边界一致。

已完成预算与源SHA冻结、全形状work/权重流量审计、合法FMA16配额工具与4测试、六项待接配置。源architecture_tlm/equal_area_100_250_20261107，PLAN明确pending/无时间能量；未接真实数字执行适配，不把旧基线结果缩放冒充新结果。FFN每层74,711,040MAC，36层含head权重BF16约8.044544GB、W8约5.354947GB；136.4606GB/s理想纯权重流下界58.95/39.24ms，不是新TPOT，量化节省与随机收益分开。

唯一给模块文件module_handoff/DIGITAL_BASELINES_100_250_NEXT_ZH_20261107.md：204提供BF16/W8 GU/NL/Wd数制/端点、共享池/固定组件、L/II/context/合法配置与小SRAM映射；198提供dense/同SparQ准确数字Softmax/PV，共享池实际租用/在线有限tile/GQA/不同并发组、状态控制面积与事件成本。复用已验收16lane PPA，未要求所有电路重做；缺物理细节可用显式宏/代理，不假填0。旧512QK+512PV/2.5MiB/1728或1888lane不能原搬。

模块返回后由宿主配总面积、接公共后端做单层门禁，再提交EDA CPU原生36层+head；本轮没有新TLM任务/GPU/训练/PPL/RTL/PT或电路台账run。不接管204正在运行TT门限缓存修复；未将其失败映射当有效价。公开与回读以PUBLICATION.json为准，PR244待审不合并，Projects待同步。
