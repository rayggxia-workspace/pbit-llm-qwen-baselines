## Issue173短流三路AND结果核验完成（2026-10-24）

Slurm2891三片封存完成，48份/46唯一配置、documents/sidecar原字节SHA、36层全前缀、每片27项预检通过。执行c44c2edc不变；同轮BF16及原尺度mean/IID64三seed与旧结果逐值一致。Qwen3-4B后训练、准确Attention、8×128后缀，非完整WT2。前级W8/x固定四档共享64 T=K64；后级4×2×4联合32区间，各1/2/4次。整体减半固定四档[S/2,S/8,S/32,S/128]的mean/IID64/联合32/64/128 PPL为13.4034/27.4020/103.8940/21.8821/15.3647；BF16=13.5660，最佳128仍高13.26%，不能称无损。gate/up恢复仍FP32参考；无训练/PPA。

报告qwen3/results/and_direct_20261024/short/REPORT_ZH.md及SUMMARY/RAW_INDEX。原件project_archives/qwen3_and_direct_20261024/short-sealed-2891.tar.gz，服务器与本机SHA均e498dc55cfe0dea649f52c3c4635272f32af33d67114b1270328f69ca9587467。不重交、无新增定时。本人jieruiz，task/173-and-direct-wd，沿用Issue173/PR174待审未合并；发布以SHORT_PUBLICATION.json为准，Projects缺read:project待同步。FSM另属Issue175/PR176，不混用结果。

## Issue173：短流分层Slurm2891已启动（2026-10-24）

固定执行c44c2edc23a9a66c9e48c7f9cf99300fa34cefb0，Slurm2891_[0-2]均RUNNING、每片27项CPU/CUDA/模型预检通过，三次BF16同为13.566049199388152；概率结果尚未收齐，不能称完整PPL交付。45配置＋3BF16，四档位置三方案、32联合区间(4x2x4)、每区间1/2/4次，总T32/64/128；前级四档共享64 T=K64不变。无FSM实现/训练/PPA。源包SHA46e52b88ed8b0ee7bdecd4f23ce4896a19ecaa1179664974fe194c40c7bca42b，已归档project_archives/qwen3_and_direct_20261024/source-c44c2edc23a9.tar.gz，无额外解压副本。

服务器个人ROOT pbit-qwen3-and-short-20261024-issue173，snapshot-c44c2edc不可变；SHORT_SUBMISSION.json含回执，SHORT_RECOVERY.json可恢复。不重交健康任务，不建立未请求的定时；完成后仅依据complete.json/documents/sidecar SHA核验48物理/46唯一结果、36层全前缀，并对original均值/IID64三seed与原Slurm2886做同值复核。交付仍Issue173/PR174待审未合并，Projects未同步。

## Issue173：固定四档与32联合分层短流准备（2026-10-24）

用户明确固定S不能随输入变化，要求非线性分层、采样不超过128；可32层每层重复。新增original=[S,S/4,S/16,S/64]、lower_half=[S/2,S/8,S/32,S/128]、lower_floor=[S,S/4,S/16,S/128]三固定四档。前级x/Wg/Wu保持固定四档W8共享64 T=K64。后级为4(g)*2(sigmoid)*4(u)=32联合等体积区间，各取1/2/4次，总32/64/128；不是每支各32段，同序边际分层会偏置乘积。7类边界Binomial严格压缩、Wd直连及整数移位路径不变。状态机仅调研，未实现。

22项CPU功能通过，3项CUDA与缺本地Transformers的runner留Slurm预检；45三seed配置＋3BF16后缀计划。正式qwen3/and_direct/short_core.py、short_run.py、SHORT_STREAM_ZH.md。待冻结上传与Slurm提交，作业ID/准确执行和实际进度以work/jieruiz/173/SHORT_SUBMISSION.json为准，未有回执不得宣称已运行。沿用Issue173/PR174、本人jieruiz及现有目录；无训练/PPA，不改旧快照，不合并，Projects未同步。

## Issue173：前级64次核验与SiLU状态机调研（2026-10-24）

已核验PR174当前head 0c94a2d8、Issue173与本人jieruiz；五个关键源码与冻结执行8249fad6原字节相同。g/u有限AND实验前级是固定W8、TRAIN固定四档x、共享64随机字、T=K=64分层；后级三流IID，两者不能混称。首层x/g/u给出的是RMS而非均值；gate/up恢复仍FP32参考。文献SMURF(2405.02356v1, ASP-DAC2025)实际测试Swish的64/256比特近似，但没有Qwen验证；候选可直接拟合p*sigmoid(sign*S*p)，保留尺度/符号，与独立u流AND。FSM状态/初始化/相关性必须实际模拟，不能用IID Binomial冒充，也不自动改善同量程的IID采样方差。

详细调研和四档位置/两档空缺分析追加在qwen3/and_direct/MULTISCALE_ZH.md；FSM_RESEARCH_AUDIT.json记录复核。没有新增PPL、训练、RTL/PPA或作业；下一步是状态机微测试与TRAIN选档，尚未执行。沿用Issue173/PR174与现有工作目录，不合并；本节远端发布以该PR提交及Issue回执为准，Projects未同步。

## Issue173多档发布回执（2026-10-24）

PR174已更新多档结果、ready待审未合并；科学提交a1e81c1d，发布核验head b079f455。42个文件经提交树blob SHA/长度核验，40个另原字节回读；两个大型文件使用内容寻址校验，HTTP中断未导致重复实验。Issue173已同步，MULTISCALE_PUBLICATION.json记录回执。Slurm2886已退出队列，无定时；Projects未同步。

## Issue173多档g/u直连Wd完成（2026-10-24）

用户提出幅度多档与输出移位对齐。已接续PR174实现，冻结8249fad60203679f6fc51f0661aaaac2889c86f1，Slurm2886五片完成；每片18项功能（含CUDA整数对照）通过。45份封存计分/41唯一配置、36层全前缀与SHA核验通过；无训练/RTL/PPA。Qwen3-4B后训练，准确Attention，8×128目标后缀；BF16五次一致13.566049，旧z重编码三seed及B1均值与前轮完全一致。

g/u每64通道的TRAIN固定S不变，通道选择固定档位：B2=[S,S/64]，B4=[S,S/4,S/16,S/64]，B8=[S,S/2,...,S/128]，无在线absmax。三seedPPL：B2 T64/256=2482468.68/2294.6095；B4 T64/256/1024=42.34168/14.46628/13.71393；B8=15.97791/13.90611/13.46984。均值对照B1/2/4/8=13.49820/13.45553/13.44746/13.43162。B8同时增加密度与低端覆盖，不把收益全归档数；不是完整WT2，不据略低于BF16声称能力提高。

首层x/g/u RMS=0.115725/0.211005/0.178412：g/u确实较x大，但相对量程占空比仍低。平均AND概率B1/B4/B8=.0009104/.123414/.227285。sigma必须按真实g驱动：幅度8+符号+指数经整数移位/RNE/饱和转signed8 field，再P8 LUT+独立比较器；不是sigma(g/Sg)。Wd同局部scale域的乘积指数合并B4为7类、B8为15类；先同指数归约再对齐，64倍=6位，双边64倍=12位。无z恢复/重采样；16位scale系数沿用，signed64容器/实际上界检查。gate/up恢复仍FP32参考，未完成全FFN bittrue或TLM/PPA接入。

报告qwen3/results/and_direct_20261024/multiscale/REPORT_ZH.md；方法与一手文献qwen3/and_direct/MULTISCALE_ZH.md。原件project_archives/qwen3_and_direct_20261024/multiscale-sealed-2886.tar.gz，SHA9d7fbc40697ebbd6e4a80194778308784e6b2b803864438fbbd5b34675935b4b；MULTISCALE_RECOVERY.json恢复源码包。负责人jieruiz/task/173-and-direct-wd，沿用tmp/qwen3-and-direct-issue173-20261024，PR174待审未合并。无定时、勿重交；Projects未同步。最终发布见MULTISCALE_PUBLICATION.json。

## Issue173 g/u多档扩展准备（2026-10-24）

用户授权接续同Issue/PR174，新增B2/B4/B8固定范围幅度编码、sigmoid整数真实尺度恢复、Wd同指数部分和移位后合并。旧执行与结果不改。5项新本地检查通过，CUDA1项待Slurm；新增45份后缀PPL计划，非训练。下一步冻结并提交multiscale.sbatch，执行/作业ID以MULTISCALE_SUBMISSION.json为准，未有回执前不得重复声称远端已运行。

## Issue173发布回执（2026-10-24）

PR174已转ready、待审未合并；结果提交898ba797，23个文件远端原字节核验一致，Issue173已同步。Slurm2881已退出队列，五片封存核验完成；无定时/健康任务遗留。FINAL_PUBLICATION.json记录回执，Projects未同步。

## Issue173有限AND直连Wd完成（2026-10-24）

Slurm2881五片完成，执行098c7a00db27dded1b7047dc5828871e4b057f70。每片12项检查通过，包括GPU有界整数GEMM与逐拍事件累加参考。27份封存计分/23唯一配置、documents与sidecar SHA、36层全前缀覆盖通过。后训练Qwen3-4B，8×128=1024目标后缀，非完整WT2；准确Attention。BF16五次完全一致13.566049，W8 13.414964；旧8位均值z再编码三seed13.428421，直连均值原尺度13.517797、有限系数13.498204。有限三流直连T64/256/1024/4096三seed分别8949057.252807/7735.004324/30.692997/14.937278。首层平均AND概率0.000910389，T64零事件95.02%；不能用旧均值PPL支持短流直连，也不能认为8位门限只需256次就充分。

新路径：幅度8+符号/驱动signed8/概率8+true-one，独立三流AND事件跨Wd输出共享；Wd固定W8，有限恢复系数16位、signed52输出累加、整数RNE BF16。无z重新统计/定标/采样。gate/up恢复仍FP32参考，无训练、RTL或PPA。建议先解决SgSu和稀少事件问题，再冻结训练硬件前向；勿把当前T64直连直接当可用训练配置。

负责人jieruiz/task/173-and-direct-wd，目录tmp/qwen3-and-direct-issue173-20261024，PR174依赖PR172，待审未合并。报告qwen3/results/and_direct_20261024/REPORT_ZH.md；归档project_archives/qwen3_and_direct_20261024/sealed-2881.tar.gz，SHA1f87f6f00a9ffda47ca03b0bca0d55d2236e6fe99cacd5c6bf88f9eed4d54309，RECOVERY.json包含源包恢复。无运行任务或新增定时；Projects未同步。结果远端发布以FINAL_PUBLICATION.json为准，勿重交。

恢复：先读Issue173/PR174。实验已完成，不重交2881。正式结果SUMMARY.json/RAW_INDEX.json含配置、模型、数据、校准及执行源码SHA，原始结果压缩包不必解压复制。重核验运行python work/jieruiz/173/summarize.py。发布阶段用同PR174，不合并。后续训练契约Issue159/PR170尚未自动采用本新路径；原57参数扫描不能直接沿用z重编码参数。当前输出恢复系数/宽累加为功能候选，没有硬件面积优越性证明。
