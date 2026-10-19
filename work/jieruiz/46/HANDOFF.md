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


## T64完整WT2补测（2026-10-19）

用户追问64次，接续Issue46/PR47。新执行源a7bae630c62f08165a01192fe4226d9beac34e7c，kernel/test与首批e6f29b1完全相同；12单测及41/22/9配置数检查通过。Slurm2298重新跑身份/原BF16与测试，2299为dynamic64/pot4/pot8的64次完整WT2各3seed，最多4GPU，无前缀skip门槛。旧65项和快照不覆盖。当前只已提交，未宣称新PPL结果；下一步收回11项输出与3份元数据，逐SHA核验并补充完整T64表。


## T64完整结果已收回（2026-10-19）

Slurm2298/2299全部结束，本人队列空，11项计分/14原件SHA/31执行源码blob通过；两批模型、原文、token和冻结依赖一致，BF16完整精确复现11.652735。4档T64为13.038027±0.010666，8档13.038505±0.012030，dynamic64为14.559275±0.005839，均3seed/299077目标。正式补充qwen/results/fixedw_multiscale_t64_20261019/，首批报告新增联合表但旧SUMMARY/ARTIFACT_INDEX及原始65项不改。结果本地已整理，待提交上传并同步Issue/备忘录；PR47未合并，无PPA，Projects缺read:project待同步。下一步核验发布回执或审阅PR，不重复已完成76项。


2026-10-19最终回执：T64结果a4a15018与备忘录c59ac5d均已实际发布，17项新发布blob与旧20项原发布blob核验通过；Issue评论https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/46#issuecomment-6261116248。PR47 ready待审未合并，Issue46open，Projects缺read:project待同步。T64_DELIVERY_RECEIPT记录完整回执；下一步审阅/验收或独立RTL/PPA，不重跑76项。


2026-10-19接续Issue46：固定相同W8，新增experiments/qwen_multiscale_stratified_20261019，67项完整WT2+2BF16对照；扫描B1/2/3/4/6/8与K1/4/16/T，无训练/Attention变化。新13项kernel、旧12项严格IID与mean回归通过；独立审核67唯一配置及analyzer K1/K4分组和篡改拒绝通过。源码准备冻结，尚未提交Slurm，不宣称新PPL。执行前保持只读旧快照；后续提交/作业与成果另记STRATIFIED_*。


## 多档＋分层完整WT2扫描运行中（2026-10-19）

执行源db27fa3d7ed8eced13513f0cad10061a3cc59a71，Slurm2308/2309（67配置，最多4GPU），原BF16完整11.652735已复现；13新kernel/12旧multiscale/8旧range及shared测试通过。已公开冻结源码，执行快照不可改。新结果尚未收齐，不宣称分层PPL；新正式目录将为qwen/results/multiscale_stratified_20261019，旧76项不覆盖。下一步检查2309状态，收回69项计分＋3元数据，逐SHA后联合旧同源IID结果分析，更新PR47及备忘录。Projects缺read:project，PR47未合并。


发布补充：db27fa3之后仅本地修整runner空白行、增加后处理K分组fixture和plot脚本，不改变已提交db27fa3快照。文献已保存，备忘录afbe90b已发布；当前67配置仍运行，结果待完整收回。


## 多档＋分层结果本地核验完成（2026-10-19）

Slurm2308/2309结束、本人队列空，69计分/72服务器原件/37执行源blob核验。4档细分层T16/32/64/128=11.900826/11.736131/11.693775/11.683928；2档T32=11.769199；同T64四档K4/16=11.893101/11.736863，均3seed完整WT2。原BF16精确11.652735。正式结果qwen/results/multiscale_stratified_20261019/，COMPARISON与图/LITERATURE为总入口，旧76输出不覆盖。当前本地结果已完整整理，待提交发布/更新PR及长期备忘录；PR47未合并、无新PPA，Projects缺read:project待同步。
