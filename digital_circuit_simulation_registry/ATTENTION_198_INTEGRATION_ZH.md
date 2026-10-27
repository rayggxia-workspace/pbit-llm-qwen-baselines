# Issue198登记增量

本PR保留v1 `attention-rejection-198-20261027`，新增v2 `attention-control-198-v2-20261027`。v2为124项RTL功能、8项Yosys/ABC库映射与3项零延迟门级回放的同批候选评估，STA/PT未运行。

main尚无完整台账工具；未将其他分支的79条记录或整套catalog覆盖进本PR。实际按根阅读镜像79条增量合成80条，registry.py check/render通过，旧记录原字节不变。检查和增量同步回执在work/rayggxia/198/CONTROL_REGISTRY_CHECK.json、CONTROL_REGISTRY_SYNC.json；根阅读镜像已更新总览/结果索引/CSV。

集成到台账维护分支时，合并两个独立record，再执行registry.py add/check/render。原始ZIP新增两行（v1补索引、v2新增）在work/rayggxia/198/CONTROL_ARCHIVE_INVENTORY_APPEND.csv；按路径去重追加到archive_inventory.csv，不能拿单一旧catalog覆盖其他并行增量。本地原字节和成员SHA已核，路径只代表本机授权归档，不宣称远端可访问。
