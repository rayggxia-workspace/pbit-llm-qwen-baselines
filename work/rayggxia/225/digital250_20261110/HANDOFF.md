# 28nm250数字基线提交交接

2026-11-10，rayggxia，Issue225 / PR249；模块依赖236/204/198，复用225当前checkout/分支task/225-tlm-unified250-20261107，不重复建全量工作副本。

用户已明确沿55nm三组：BF16_dense、W8_dense、W8_screen。新全定点P8/W8数字CIM只保留补充，不替代主表。正式实现architecture_tlm/process_28nm/digital250_20261110/，父过程和55nm默认不改。

已提交：原生单层门禁数组38650227，完整数组38650228；每组aftercorr依赖对应门禁。下标0/1/2依次BF16_dense/W8_dense/W8_screen。2026-11-10北京时间13:30提交，最近状态以STATUS.json为准；提交不表示完整结果完成。

远端根/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm28d250_full225_34375c559476。包67324B，SHA371485605a0d3ba723279345b19f62dea32f7772ba757bd40b938dd75e3f02bd；manifest0873dd0ba873923be07792f19cf31f354f6914421100616cbef0ffb0ff67c967。各case独立CWD及原生内存统计，不并发覆盖；worker验证三已有环境manifest、源和输出SEAL。

每任务请求1CPU/12GiB，无GPU，集群实际按节点粒度分配3CPU，sacct为准。门禁4h、完整24h上限，各数组最多2并行；两个数组可能同时运行不同已通过方案。24h是上限，不是预计用时。未取消其他人的任务。

已完成本地首轮三组解析一层＋384head，工作量/有限池/832KiB/队列/能量和面积检查PASS。最终版特征TopK按四Q展开服务/动作，又进行三项同源局部验证，结果见VALIDATION.json；门禁不是完整模型结果，也非STA。早期构造import/namespace/inspect错误属于新适配调试，错误与修复范围在VALIDATION记录，旧模块/冻结概率源未变。

概率完整三seed38644764已全部收齐，原件在project_archives/tlm28p250_full225_20261110，汇总正式250MHz/FULL_RESULTS_20261110_ZH.md。平均51.132604ms（扣head43.594377ms）、15.267553mJ片上、4pJ情景188.432048mJ、面积6.480303mm²；旧46.01856ms是外推，不再当作完整结果。原源/SEAL不改。

恢复：使用本目录ops.py status经既有paracloud_client读取，账号/凭据不进入仓库。输出outputs/pilot_<scheme>及outputs/full_<scheme>；work同名目录有INVOCATION/EXIT/run.log。完整只认Slurm COMPLETED/0:0＋status=completed＋SEAL/SHA/VALIDATION。若失败保留诊断，新冻结包修复，不原地改提交源，不重交健康作业。

下一步：检查门禁/完整状态；收齐后下载小型JSON、核源/配置/SHA、36层/完整head/权重字节/全部资源及账本，按近等总面积与同外存比较，含/扣head均列。完整作业暂未完成；最新发布回执见PUBLICATION.json，不把本地完成写成已推送/合并。Projects缺写接口待维护者同步。
