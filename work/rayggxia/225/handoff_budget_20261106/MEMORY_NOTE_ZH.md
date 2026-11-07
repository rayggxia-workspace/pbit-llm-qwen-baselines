## 2026-11-06 Issue225：最新模块交接功耗面积重计价

已核对普通数字池640路/40FMA16、K并行8/提前补货（128个末端归约器保留），以及GU跨K状态96KiB候选、SRAM1952KiB/488宏。FFN仍12个C20/T64、64位跨K；独立512路QK、PV和8×128KiB Attention缓冲保留。Attention64KiB/组、共享QK、CIM24槽、激活128KiB及DOT8未实现，不预扣。

当前覆盖面积57.573748mm²（旧67.541446，约减14.76%）；若仍152KiB/502宏则57.950534。50ms仅计价窗口，片上24.204832mJ/0.484097W，含4pJ/bit外存197.369327mJ/3.947387W；不是新联合native时间或芯片实测。MAC总次数不随lane数打折；归约ADD由29312640减到3256960；SRAM按动作计费，norm额外392192B及96分批额外读取均计。

正式architecture_tlm/current_handoff_budget_20261106/REPORT_ZH.md、INPUTS/RESULTS、estimate.py；12个源SHA、16旧能量分项、6项CPU检查通过。未提交新native/GPU/RTL/PT，未改198/204冻结执行源。旧norm只读收回6/9完整封存，其余不称完成。640整token/lm_head与96候选联合488bank调度、仲裁供数/结果槽/新互连增量PPA仍待验证，不继承新采样PPL。

代码已推送PR248提交aebf0e4c86f348092886cf5a3c26bd6f79903ff2，13文件逐内容回读一致；PR待审未合并、Issue225保持open，Projects待维护者同步。恢复入口tmp/norm-stream-issue225-20261106/work/rayggxia/225/handoff_budget_20261106/HANDOFF.md及PUBLICATION.json。本地根正式报告为同字节阅读镜像；不把其他成员未发布原件或并发备忘录修改混入提交。

---

