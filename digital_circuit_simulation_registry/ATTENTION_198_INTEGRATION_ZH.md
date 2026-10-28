# Issue198登记增量

本PR保留v1 `attention-rejection-198-20261027`，新增v2 `attention-control-198-v2-20261027`。v2为124项RTL功能、8项Yosys/ABC库映射与3项零延迟门级回放的同批候选评估，STA/PT未运行。

main尚无完整台账工具；未将其他分支的79条记录或整套catalog覆盖进本PR。实际按根阅读镜像79条增量合成80条，registry.py check/render通过，旧记录原字节不变。检查和增量同步回执在work/rayggxia/198/CONTROL_REGISTRY_CHECK.json、CONTROL_REGISTRY_SYNC.json；根阅读镜像已更新总览/结果索引/CSV。

集成到台账维护分支时，合并两个独立record，再执行registry.py add/check/render。原始ZIP新增两行（v1补索引、v2新增）在work/rayggxia/198/CONTROL_ARCHIVE_INVENTORY_APPEND.csv；按路径去重追加到archive_inventory.csv，不能拿单一旧catalog覆盖其他并行增量。本地原字节和成员SHA已核，路径只代表本机授权归档，不宣称远端可访问。

2026-10-28：另新增attention-control-198-eda-20261028，8top/116回放/66PT窗口，STA=violations、power=calculated。合并独立record并按EDA_ARCHIVE_INVENTORY_APPEND.csv增量追加，check/render结果见EDA_REGISTRY_CHECK.json；不能覆盖其他分支catalog。

2026-10-28用户要求将Softmax调研也纳入功耗面积目录：新增[08_Softmax文献功耗面积周期参考.md](08_Softmax文献功耗面积周期参考.md)及references/softmax_20261028/REFERENCE.csv、REFERENCE.json，14个文献参考点；明确工艺、整行拍数、时钟周期、面积与功耗频率。不是本项目新run，不修改catalog/records或仿真总数；根阅读副本逐字同步，既有台账文件SHA不变。

2026-10-28：新增09_KV读取与数字Attention基线参考.md及references/kv_baseline_20261028两份同字节地址算术数据；100几何核验/18旧单头案例，不新增run，不改既有records/catalog。主报告/源索引在attention_compare；真实后训练GQA与同质量端到端仍待补。
