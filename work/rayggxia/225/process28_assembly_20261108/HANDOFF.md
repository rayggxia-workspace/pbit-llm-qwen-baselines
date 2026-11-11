## 2026-11-08：28nm已有数据足够先搭组件接合版

用户询问现有28nm数据可否先搭TLM、等待补测确认。已只读消费204/198最新5份JSON，新增process_28nm/prepare_bindings.py与250/500 BINDINGS：FFN18/34拍、250/500服务72/136和36/68ns、同一GU/Wd后端；state/codec/scale、1KiB暂存代理及13/12张Attention合格卡已收。显式A前端＋gap输入Ising，32加载握手不双计，旧ab_both仅参照；不暗用55价格、28面积×1。已补4项CPU集成验证，无新TLM整机/RTL/PT/EDA/GPU任务。

后续可沿成熟bank/DMA/credit/重叠执行器，存储与公共服务先给显式宏，再用PPA替换；不用等全部PT才能搭。当前缺SRAM28组织/2或4ns/价、DMA向量、PV紧凑价与共享FMA新流水绑定，整机值保持null。250可用旧合格FMA16/C4，500仍待合格数字结果；FFN0setupunc与Attention10%period分别标注。未确定最佳核数、未宣称完整28芯片结果，不改55默认和健康冻结任务。正式process_28nm/README_ZH.md；4检查及输入SHA见VALIDATION；发布以本目录PUBLICATION为准，PR249待审不合并，Projects待同步。

恢复：先读最新owner交接，运行prepare_bindings和4检查；若输入SHA更新，记录新版本，不修改旧执行快照。可调宏不得默认0。当前两档仅组件消费入口，尚无完整整机入口。
