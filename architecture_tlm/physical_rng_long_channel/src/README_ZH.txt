CMOS随机通道长记录首轮 / long_channel_v1 / 2026-10-23 / Issue152
======================================================================
任务：https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/152
依赖Issue95的随机服务接口；不修改其模型/RTL、原始波形或已提交任务快照。

一、选定一个通道，明确电路边界
----------------------------------------------------------------------
原两MOS零外加C核心 + 真实旧15MOS buffers_x2比较器 + 原5fF输出负载。
核心1.2V，VN=0.3V、VP=0.8998115919357365V；比较器0.8V、IREF=10nA；TT25C。
器件尺寸、偏置、5fF负载与zero_cap_readout_38237164中的buffers_x2相同。
核心和比较器始终通电，不做间歇开关、选行、MUX或锁存；本结果不覆盖这些工作模式。
5fF是当前明确的输出负载，不是版图PEX或真实1.2V接收器/电平转换器模型。
逻辑低<=0.16V，高>=0.64V；阈值判决用0.4V，MID/超轨另标，原始bit不删除。
不加Ccore，但MOS本征电容仍在；没有理想放大器/理想比较器替换。
工艺库只读引用，并核对已有27项SHA，不改也不上传PDK。

二、为什么分三次提交
----------------------------------------------------------------------
1 s / 2.5 ns至少4亿个内部步。20ms固定启动段另加后，每条至少4.08亿步。
8核用于并行独立案例，每个Spectre显式-mt单线程；不保证一个小电路快8倍。
只写10us strobe减小结果体积，不降低内部噪声带宽或求解工作。
本包不会在pilot完成后自动提交昂贵长任务；先查看实际耗时与门禁。

Cadence文档指出1/noisefmin不能超过瞬态总时长。因此：
- 500Hz短成本/精度记录总时长>=2ms；
- 10Hz校准/精度记录总时长120ms，不使用无效的20ms/10Hz组合；
- 1Hz/10s专项不在本轮自动执行，需另外设计协议。
10Hz是研究参数：低于它的噪声PSD被平坦化，不是器件真实低频极限。

阶段A：pilot，先短耗时/器件噪声及500Hz精度筛查
- 正反/细DC、OP/AC/noise、原±10mV阶跃：5个前置物理门禁。
- 四个3ms成本/噪声诊断：全噪声、仅核心、仅比较器、全部关噪声；同一probe seed33013。
  noiseoff直接选实际MOS实例，用输出/内部sense波动与关噪声对照确认两组器件噪声有效。
  这不是瞬态噪声功率贡献分解；加密PDK系数不公开/修改，不假称读到了flicker系数。
- 500Hz三个新seed32003/32009/32027，各22ms丢2ms，保存100ns：
  (100MHz,2.5ns)、(100MHz,1.25ns)、(200MHz,1.25ns)，共9例。
- 比较核心/比较器幅度CDF网格、标准差、P1、中间电平比例和ACF；保存每seed差值。
  固定容差为工程筛查，不把小样本通过当成收敛证明。任意门禁失败不解锁下一阶段。
- 正常18例，成本外推写cost_projection.json，不能当作实测1s耗时。

阶段B：calibrate，独立10Hz校准，冻结后做10Hz精度检查
- 用30011/30047/30071三个校准seed；每点120ms，固定丢20ms、有效100ms、保存10us。
- 只把历史校准冻结值608.527348mV作为初始中心，预先规定±4mV夹逼、4次二分，
  最终0.5mV区间内插值并量化5uV。6个电压点×3seed，正常18例。
- 若不包围P50/非单调则停止，不事后扩区间或根据验证结果换种子。
- 写frozen_reference.json及SHA；此后不能根据任何检查或验证结果重调Vref。
- 另用35023/35053/35081三个数值检查seed，在冻结参考下跑上述三设置、各120ms丢20ms，
  保存500ns，共9例。这解决500Hz短检查不能自动覆盖10Hz工作点的问题。
- 正常共27例；若10Hz精度检查失败，冻结文件仍保留，长验证被阻断，不能悄悄重调参考。
- 20ms启动段是预先固定的保守预算，依据旧通道微秒阶跃尺度并由本轮阶跃门禁复核，
  不因某段统计不好改剪裁，也不宣称20ms自动证明低频过程已经平稳。

阶段C：long，三seed秒级验证及同参考500Hz对照
- 41011/41047/41077独立于所有校准/数值检查及历史seed。
- 每seed有效1s，启动另加20ms，总1.02s；10Hz、500Hz各三条，共6条独立记录。
- noisescale=1、noisefmax=100MHz、maxstep=2.5ns。
- strobeperiod=10us、strobeoutput=strobeonly；保存time/out/bit，不保存稀疏电流冒充功耗。
- 从t=20ms起，每十个strobe精确取一点，区间[20ms,1020ms)，每条恰好10000 bit。
- 同一冻结Vref用于两个fmin，便于观察低频设置导致的偏置/漂移；不重新校准500Hz。
- 三seed分别报告，不拼成连续波形，也不据其选择“最好seed”。
- 1s记录完成不等于概率50%/IID/熵/读取可靠性通过。尤其旧比较器中间电平必须照实报告。

三、上传与第一条命令
----------------------------------------------------------------------
上传整个long_channel_v1文件夹到新远端目录：
 /public3/home/t6s011227/analog_pbit_20261016/long_channel_v1/
只上传本文件夹，不上传PDK、旧结果或__pycache__。

 cd /public3/home/t6s011227/analog_pbit_20261016/long_channel_v1
 bash submit.sh pilot

默认每阶段一个8核16GB作业，v6_384，上限3天；上限不是预计耗时。
pilot只提交短阶段。完成后下载自动归档和sha256，先检查summary、noise_audit、
numerical_screen_500Hz和cost_projection。旧p50任务如果仍在运行，不取消/修改它。

后续在pilot成功且成本预算合适后：
 bash submit.sh calibrate /public3/home/t6s011227/analog_pbit_20261016/long_channel_v1/results/PILOTJOB_pilot
再于calibrate成功后：
 bash submit.sh long /public3/home/t6s011227/analog_pbit_20261016/long_channel_v1/results/CALJOB_calibrate

前一阶段必须已完成、job_exit_status=0、源/配置SHA相同并且eligible_for_next_stage=true。
预览结果不能解锁实际运行。数字模型等不是该门禁的一部分。
long按前一阶段实测成本乘2作保守外推；若超过每例LONG_CASE_TIMEOUT_S默认250000秒会停止。
外推不是保证，受低频噪声发生器、节点负载和自适应步数影响。
如需改变资源，在新提交时显式指定并查看metadata；必须让Slurm总时间覆盖单例及收尾：
 STUDY_WALLTIME=7-00:00:00 LONG_CASE_TIMEOUT_S=580000 bash submit.sh long /绝对/CALJOB_calibrate
 STUDY_WORKERS=4 STUDY_MEMORY=16G bash submit.sh pilot
更长墙钟是否允许由队列决定；脚本不会改噪声/步长来勉强满足预算。

若1s估计不稳定，后续独立4s扩展（不自动提交，不与1s拼接）：
 STUDY_EFFECTIVE_SECONDS=4 bash submit.sh long /绝对/CALJOB_calibrate
使用新51001/51031/51071，冻结参考不变；需先核实更长资源预算。

四、每条记录输出什么
----------------------------------------------------------------------
raw_100us.csv：真实时间、核心/比较器电压、阈值bit、LOW/HIGH/MID/超轨标记；所有样本保留。
quality.json：
- 总体P1及10ms/100ms分块P1；无效电平数及每块计数。
- 原始流lag1/2/5/10/20/50，覆盖100us到5ms；报告配对数。
- VN全部阈值输出及有效电平输出分别统计偏置/相关/保留率；记录实际输出间隔。
- VN序列lag与物理时间lag分开；例如VN不可能在每个100us都输出，缺配对处为null。
- raw/VN按32bit字和Bivium六字装177bit状态的重复、汉明距离及对应位lag1相关。
- 零种子和无效电平包留在诊断中；不能按质量挑包后称原始样本。

VN规则预先固定：不重叠(0,1),(2,3)...；01->0，10->1；00/11丢弃。
vn_pairs.csv记录每对、时间和原因；vn_all_emitted.csv保留包含无效电平的诊断输出。
仅both-rail-valid的输出形成VN传输字，显式记录因此排除的数量；这种选择也可能有偏，
不把VN视为独立性修复或熵认证。原始MID不会从raw统计里消失。

raw_seed_words.csv / vn_seed_words.csv：最早bit为LSB，32bit字到达时间为第32个bit完成时间。
raw_seed_trace.json / vn_seed_trace.json：有来源、时间戳、rail资格标记和原字；
physical_entropy_certified=false。rail有效不等于熵合格。
原始/VN波形和源配置均保留；置信参考1.96/sqrt(N)仅是IID参照，不当作相关过程置信区间。

五、送入现有随机服务模型
----------------------------------------------------------------------
timestamped_seed.TimestampedSeedWords可替代RandomNetwork的source：
 source = TimestampedSeedWords('某例/vn_seed_trace.json', clock_ns=10)
 net = RandomNetwork({'local': Endpoint('lfsr32')}, source, clock_ns=10)
模型必须逐沿推进，合格字在available_s之前返回None；耗尽报错，不回绕、不补OS随机数。
raw trace遇无效电平默认拒绝；允许flagged的开关只用于明确的诊断，不代表硬件合格。
不得把VN不等间隔供给压成每拍一字，又声称是实测源速率。

可选“包/递推接口探针”，在有原数字包/仓库及合适Python的本地机器运行：
 python -B replay_seed_probe.py --service-root /数字包根 --trace /某例/vn_seed_trace.json --kind lfsr32 --out probe.json
 --kind还支持lfsr32_shared64/bivium。它调用现有Endpoint并记录其源码SHA，逐包独立初始化，
只验证实际种子包可被接收并生成结果；未逐沿模拟采集等待，不作TLM时延/换种时序/PPA结论。
本EDA脚本只需Python>=3.6；外部数字模型需要其自身声明的Python版本，不在服务器强制安装。

六、归档、复核与避免昂贵重跑
----------------------------------------------------------------------
每阶段结果：results/JOB_pilot、JOB_calibrate、JOB_long。
结束自动生成long_channel_JOB_STAGE.tar.gz和.sha256，包含原始PSF、网表、命令、配置、
版本/-h tran/-h noise、27PDK哈希、逐例status、冻结参考、统计及源码快照。
流式压缩及逐成员SHA/gzip校验，内存不随整个压缩包大小增长。
普通错误也归档成功兄弟案例；强制超时/SIGKILL可能来不及收尾，确认任务停止后手动：
 python3 -B /原SOURCE/run_long.py --pack /本目录/results/JOB_STAGE
同名归档/partial拒绝覆盖；缺压缩包不代表需要重跑计算。
若Spectre完成而后处理失败，用同版源码分析已有单个长case到新目录，不重新运行Spectre：
 python3 -B run_long.py --reanalyze /绝对/JOB_long/long_fmin10_seed41011 --out 新分析目录
稀疏10us电流均值不能用于精确功耗；本包不输出长记录功耗，供电积分需另做全求解点专项。

无需许可证的检查/预览：
 python3 -B run_long.py --verify
 python3 -B -m unittest discover -s . -p test_long.py -v
 python3 -B run_long.py --stage all --generate-only --out preview_all
生成数据明确标记GENERATED_NOT_SIMULATED，不能当结果；默认全过程18+27+6=51份网表。
本机没有Spectre，实际编译、noiseoff行为、PDK噪声、精度/校准/耗时必须由pilot等远端结果确认。

依据：
 https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/34456/transient-analyses
 https://community.cadence.com/cadence_blogs_8/b/cic/posts/spectre-tech-tips-using-the-spectre-strobe-feature
 https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/23936/transient-noise-spectre
 https://community.cadence.com/thread/1348522?ContentTypeID=1
