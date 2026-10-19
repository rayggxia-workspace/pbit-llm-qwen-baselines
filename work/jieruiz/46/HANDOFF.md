# Issue46 初始交接

2026-10-19，jieruiz；目标rayggxia-workspace/pbit-llm-qwen-baselines，base pbit-tlm-attention-details-20261016@c1555ae。独立分支task/46-fixedw-multiscale，主目录tmp/qwen-fixedw-multiscale-20261019；kernel并行目录tmp/qwen-fixedw-multiscale-kernel-20261019。

用户授权固定INT8 W，只改输入多尺度，测试自然随机T<=256。最新README/AGENTS/TLM索引/个人状态已读取，GitHub身份jieruiz，8张5090空闲且本人队列为空；注意这是开工时快照。Attention成员PR42-45和Issue33/35/36/37不接管。

当前本地实现中，未提交/部署/运行。root负责runner、发布/部署/汇总；并行agent只改multiscale_core.py和test_multiscale_core.py，独立工作目录。下一步核对正确性和控制W完全一致，冻结源后以Slurm prepare重跑BF16/hash，再执行41项screen；实际速度确认后提交22项预选full（有明确skip门槛）。详细协议见README_ZH.md。

无新PPA，无更改TLM默认；Projects既往缺read:project，待发布再核实。不要把本地文件写成远程作业已提交。


本地冻结前验证：12/12新kernel测试通过，dynamic64固定W与旧参考逐位相同，跨档/跨W tile逐拍R8计数恢复等价。runner编译和41/22配置计数通过，依赖source_manifest已加入worker复核。尚未提交服务器。


已实际提交：执行源e6f29b113405df53f2ca32b084d9de0dc9859343；Slurm prepare2234、screen2235(41配置最多4GPU)。完整新方案PPL未生成，full尚未提交。归档SHA见SUBMISSION.json；不可覆盖快照。


完整评估已提交：screen41项已齐且无错误；Slurm2276为预定22项full，最多4GPU，执行源仍e6f29b1。完整结果尚未产生；前缀4档T256约12.2230、dynamic约12.8165、BF16约12.0892，不混称全量。完整原BF16已复现11.652735047455899/299077。服务器新12+旧8/共享计数验证通过。


## 全部结果已核验（2026-10-19T14:04:56+08:00）

65项计分全部齐（41screen+22full+2BF16），无skip/pending；新方案完整WT2已完成。原件逐bytes/SHA与执行Git blob复核通过，结果qwen/results/fixedw_multiscale_20261019/。执行源e6f29b1不可覆盖；analysis后续提交未改变执行快照。PR47待审未合并，Issue46保持open直到验收/合并；Projects仍缺read:project。未跑新训练/PPA/物理源或TLM。T64仅512前缀，未完整验证。


最终发布回执：结果提交312bc4d已实际发布，20文件Git blob与RESULTS_MANIFEST一致；PR47已ready for review、未合并，Issue46保持open。Issue评论https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/46#issuecomment-6260853264。备忘录35fc829已推送PR29，根阅读副本与远端同字节。下一步审阅/验收PR47，若继续才做T64全量或RTL/PPA，不重复65项已完成实验。Projects缺read:project待同步。
