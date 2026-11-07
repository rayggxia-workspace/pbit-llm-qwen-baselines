# Issue225：FFN与Attention最新交接接合

负责人rayggxia；100MHz复用task/225-norm-stream-20261106 / PR248，独立目录tmp/norm-stream-issue225-20261106。远端基线f9f716fbf81194bd0c4eaec49ff18dcf666a2f74；250MHz仍在独立目录tmp/tlm-unified250-issue225-20261107 / PR249。未合并PR，不改原冻结运行包。

正式接合与报告为architecture_tlm/module_refresh_20261107，CURRENT_100MHZ.json指向host100.make_model。100保持6核/16KiB返回/1216KiB SRAM，替换SS100短T/C19核价，有限10KiB投影FIFO、静态交错权重和显式宽前端接入。完整冷单层配对1.19475→1.20762ms，算术/采样和外存字节/地址摘要守恒。core_budget按活动gross＋停钟等待计，已测GU/Wd25.40625/26.06844pJ/DOT64，FFN核池全层驻留0.041518mJ。覆盖小计33.76037mm²，加新前端宏预留0.38556后34.14593mm²；旧采样器准备面积未拆，保留残余重叠说明。

250接同一受控Attention包，删除旧v1安装与5.2µs额外预算，返回4ns、TT SRAM事件价格统一；3/2核完整冷单层解析回放1.085992/1.114148ms。新TT250短T/C19功耗待收，空值不套100价格；旧TT250/T64参考单列。共享校准代码作为PR248依赖交付，PR249更新时保留当前PR248树，避免回退100新默认。

100原始配对在本目录local100，SEAL与源码SHA保留。executed_host100.py与原始记录SHA一致；随后新增的g8/u8和转换字段仅合同元数据，不将其说成原始运行已有字段。两份SS100报告归档SHA与每帧/128单位核对见SOURCE_EVIDENCE.json，完整成员核验沿用上游。

250曾在GU阶段触发返回时钟断言；诊断值now=296591.9999996155、last=296588ns，根因为父循环1e-6ns事件容差与模块1e-7ns检查不同。宿主clock_bridge改为整数4ns周期审核；同周期重复tick和真正离边沿仍拒绝，私有模块与旧健康作业未改。3核执行源model/pricing在250任务executed_c3_sources逐SHA恢复，后续仅补合同和价格接口；2核运行源与最终工作源一致。源路径、原件与验收在两个任务VALIDATION/RAW索引。

只发布接合代码、校准数值、摘要及SHA；私有执行包/轨迹/工艺不复制。ATTENTION_SOURCE.json锁定10个文件，缺依赖直接报错。无新训练、PPL、RTL/PT或数字台账run；两版仍缺本次完整36层原生LPDDR回放，旧作业结果不能改名。新250 PPA收齐后更新FFN_PROFILE，再在新快照重跑；不要修改已提交包。

本地修改/验证已完成，上传状态以PUBLICATION.json和远端PR head为准；PR均待审，不宣称已合并。Projects待维护者同步。
