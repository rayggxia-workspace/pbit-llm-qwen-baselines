## 2026-11-09 用户接受28nm默认832KiB

Issue225/PR249；28nm250/500的WHOLE_CONFIG已逐字节换为通过配对的832配置：208个4KiB/1RW宏，前端136/Attention72、激活96KiB/8×36KiB Attention，其余资源/采样/外存不变。两频默认SHA与冻结测试文件相同，运行函数AST一致，四SEAL保持，55源SHA不变。960参考另存WHOLE_CONFIG_960_REFERENCE。

无15%统一预留的28nm250/500面积预算6.758447/6.784987mm²，SRAM2.471065mm²。已测局部时延+0.159069%/+0.094963%；完整832的36层/full-vocab时延与能量尚未重跑，旧45.901/40.991ms只作960参考，不能改标签。新完整命令默认会实际执行208bank；当前不启动新长任务或PPA，不动冻结运行/55设置。

正式process_28nm/DEFAULT_SRAM832_20261109_ZH.md/json与两频WHOLE_CONFIG；intake_sram.py修复当前默认不能套给历史960结果的容量标签，历史重计仍显式960。旧小配对创建时default_changed=false保留，当前默认状态以新接受文件为准。发布看本work/PUBLICATION.json；PR待审未合并，Projects待同步。

下一步完整token评估用默认832并新建结果目录，960对照显式传--macros WHOLE_CONFIG_960_REFERENCE.json；不要重标签旧报告或覆盖封存。
