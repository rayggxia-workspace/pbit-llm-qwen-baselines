# 2026-11-01 最新三模块预算刷新

用户要求读取本地module_handoff更新后重算，继续Issue225/PR226，独立目录/分支不变。
新增architecture_tlm/module_estimate_20261101，原module_estimate_20261031及原模块不改。

已校验GU13文件/8成员、NL9文件/6成员、Attention36SHA/24头/1536样本/4反例；
初次NL镜像缺CONFIG、Attention参数名错误已保留，改用正式源/正确参数通过。
准确来源及原字节SHA在INPUTS，脚本重新读取时无需私有大包。

默认GU16/NL256/KV8：参考52.562–61.358ms、已计价片上49.279–55.261mJ、
0.857671–0.979926W、已覆盖面积139.758mm²。
GU帧218880、1.304337mJ活动；NL帧1751040、1.470418mJ活动。
GU16/NL256各需128KiB驻留，可分阶段复用，GU32/64需扩容并单列。
新GU按100MHz实测66拍，旧GU忙时2.1312ms不能直接留作新核时间。
两个旧计数池用途均换完才整体删除旧counter活动/背景/面积；跨K/量化恢复和外部RNG预留保留。
Vpath组合替换旧标量PV，禁止双收费。七情景守恒/容量/尾波/单位检查通过。

**这不是完整统一TLM/DRAMSys重跑。** 旧HBM全局时间与局部DDR4八组实跑
仅形成条件包络，113µs未作为固定actor安装。完整DDR4 TPOT/能量/整片PPA、PPL为null。
SRAM128独立bank/接口、统一异步DMA及FFN争用、KV双布局维护/尾块和Vctrl新时序仍待真正接入。
没有新增GPU/EDA/DRAM运行，不以预算结果代替物理时序。

下一步：复用unified_v6，在同一个memory service中接入有界异步request/completion，
共享DDR credits/返回缓冲；保留事件因果与真实bank分配，再跑全模型DDR4数字/概率对照。
不把constant113us替代这一步，不重跑健康原任务，不修改冻结源码。

本地最新报告及阅读镜像已生成；远端发布状态以REFRESH_PUBLICATION.json为准，未发布前不可写已上传。
Projects工具无接口，待维护者同步。长期备忘录增量见MEMORY_UPDATE_20261101_ZH.md，
不以旧main历史覆盖其他成员正在维护的全量备忘录。
