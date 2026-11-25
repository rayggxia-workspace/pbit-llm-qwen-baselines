# 21bit与本地PRNG交接

2026-11-25，rayggxia，同Issue225/PR266，分支task/225-cim-bank32-20261124，复用tmp/cim-bank32-tlm-issue225-20261124。基线远端f1552ea23d7c3721305b5b1fff029efbb89e3842。

正式变更/边界见architecture_tlm/process_28nm/cim_bank32_20261124/COUNTER21_LOCAL_RNG_ZH_20261125.md。TLM计数/结果改21bit、容量到128，默认仍16/32服务；冻结19bit电路未覆盖，21bit价格未知部分不再沿用为实测。现有功能原型cf_backend8 AW21可作五核RTL移植算术依据，双结果槽仍需同步21bit再做PPA。无新RTL/STA/PT/整机/PPL。

默认本地PRNG持续，不要求中央固定步长/跳步。初始按核装载一次，后续重播种保留既有随机服务接口；采样消费推进，等待不推进。旧jump软件验证保留为可选参考，不代表硬件要求。

10项unit、六组新trace、六类错误轨迹拒绝通过。执行源码/命令/配置/日志和SEAL保存在本目录case子目录及归档project_archives/cim_count21_localrng225_20261125/RAW_AND_SOURCE.zip，SHA e0f62912cff03437f412fcb4cb4f414267f043a34be153bfdec0ff9ce47b9ad5；正式JSON含完整成员SHA。未重跑昂贵整机，旧19bit结果保留原件。

下一步：模块对话把校准核计数、FIFO、打包、进度计数同步21bit并校准；尺度封装和描述符满握手独立跟进。本轮源码/新状态通过同PR266交付，不合并、不新建Issue或checkout。实际发布以PR head为准；Projects待维护者同步。
