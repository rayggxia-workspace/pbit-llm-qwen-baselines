# Issue152 长记录脚本交接 / 2026-10-23

负责人：jieruiz（本轮GitHub API /user实测）；任务 https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/152 。
分支 task/152-long-channel；base pbit-tlm-attention-details-20261016@6966739a5223680888bf0315f7bb4f73423a1ae6。
工作目录 C:/Users/86134/Documents/a_P_BIT/tmp/long-channel-issue152-20261023，最小稀疏worktree；源码提交8f72debba6ce3b83626be7e1eb892fed8310c634。
依赖Issue95（rayggxia负责，PR134最新2becc3b2仍开放待审），没有修改其代码、工作树或STATUS。

本地完成：architecture_tlm/physical_rng_long_channel/src，23文件214983B；直接上传副本远端上传/long_channel_v1，逐字一致，无PDK/波形/__pycache__。
20脚本/统计门禁测试、16模块Python3.6 AST、两Bash入口、27真实本地PDK哈希、51预览网表及6个现有模型包接口合成探针通过。
23个Git源blob与package_manifest原字节一致。VALIDATION和预览/探针元数据在validation/；较详细本地证据在analog_pbit_20261016/long_channel_v1_local_check。

source manifest SHA256: 05d606a37c15bd65f583fb8a91cbea09284c69bedccf84429105b7ac2340e224
config SHA256: 664d02bd3addcfd882667c6b946d43aaa5f3256c71c5a0e879d3b26fced8a720
base config SHA256: 92ea9ed2d4e2111ca1039411ee72bc7e8a5801e045537ef44e8133df222b59d2

电路：零C两MOS + 旧15MOS buffers_x2 + 原5fF，TT25C，核心1.2V/比较器0.8V10nA，始终供电。
pilot18例：DC/OP/阶跃5 + noiseoff诊断4 + 500Hz三seed三精度设置9。先看成本，不自动交长任务。
calibrate27例：10Hz三个独立cal种子120ms/20ms丢弃，6电压18例，冻结；三个另新seed10Hz数值检查9例。
long6例：10/500Hz各3条1.02s，固定丢20ms，有效1s；10us保存每10点取100us，恰10000bit/seed。
记录raw电平、VN全部/有效输出、真实时间、seed包重复/汉明/对应位相关。源适配器时间戳不压缩；耗尽报错无回放/OS回退。
所有科学结果尚待Spectre；合成fixture和预览不能当噪声/熵/PPA。噪声帮助、noiseoff及低频成本需远端确认；统计/输出警告照实保留。

远端作业：本轮没有提交，无JobID。用户下一步上传整个文件夹到
/public3/home/t6s011227/analog_pbit_20261016/long_channel_v1，然后 bash submit.sh pilot。
等pilot下载审阅后按README传前阶段结果目录运行calibrate/long；不要重交仍健康的p50旧任务。
每阶段自动long_channel_JOB_STAGE.tar.gz+.sha256，缺包可同版--pack，后处理故障可--reanalyze，不重跑长Spectre。

中央台账新增 physical-rng-long-152-prepared，实际电路阶段全部not_run，cases为空。
本分支46条/root镜像53条各自check/render通过；root已有52条其他任务record逐SHA保留，不能用本分支旧catalog覆盖它们。
本条record本地/分支同字节。待PR创建后追加引用；正式合并由维护者处理其他并行run并集。

发布状态：当前本地代码与台账已完成，任务分支/PR尚未上传；后续回执以PUBLICATION.json为准，不写已合并。
Projects尚未写入，需核实权限/维护者同步；不作为本地交付阻塞。

本会话此前的架构HTML草稿 analog_pbit_20261016/random_architecture_visual_20261022/random-architecture.html 未验收/交付；
恢复时需按2026-10-23最新FullDecode integrated_service状态更新后再预览，不把旧草稿当最新架构。此轮用户要求优先准备长记录。
