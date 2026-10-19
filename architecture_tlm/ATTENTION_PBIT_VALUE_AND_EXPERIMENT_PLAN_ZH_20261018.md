# Attention 概率筛选、Ising Softmax 与随机源：文献依据和仿真实验安排

2026-10-18；负责人 `amlink1219`；[Issue #33](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/33)。代码审计基线为集成分支 `pbit-tlm-attention-details-20261016` @ `3553996bf014a29dee7fdb2250a3965e8fd881a4`。本文件是调研与实验计划；本次没有新增模型推理、GPU训练、PPL、RTL/DC/PT或DRAMSys运行。文献的测量/仿真不等于本项目验证。

## 1. 当前判断与要回答的问题

目前没有足够证据认定项目中的概率QK筛选或Ising宏已经胜过传统数字实现。需要分别测三类收益：

1. **筛选算法价值**：减少K读取/QK后，是否足以支付摘要、代理打分、标准化、选块和地址组织。
2. **采样算法价值**：用少量V样本近似PV，相对准确数字Attention是否达到同质量且节能。
3. **p-bit电路价值**：同一个筛选或类别采样任务，原生p-bit是否胜过数字sigmoid/EXP、PRNG和采样器。

因此先做用户要求的常规数字硬算Softmax，再补online/fused和数字采样强对照。p-bit若只胜第一条数字实现，结论范围也只到该实现。以下质量门槛和时程是本计划提出的工程默认值，尚不是用户最终验收承诺。

建议先测试小规模原生概率筛选器与数字systematic PV的混合结构，同时为原生类别/Ising模块求有效采样率、配置能量和反馈时延的盈亏边界。大型耦合网络是否值得实现，由这些实验决定。

## 2. 文献证据与对本架构的含义

| 文献 | 实际核查内容及证据范围 | 本计划采用的方法或约束 |
|---|---|---|
| [Online normalizer, 2018](https://arxiv.org/abs/1805.02867) | 算法3/4、在线max/sum递推与融合；GPU算法证据 | 数字方案可共享归约、每行求一次倒数，不能假设每元素一套除法器 |
| [FlashAttention, 2022](https://arxiv.org/abs/2205.14135) | 第3节、算法1、IO分析及官方decode/GQA接口 | 数字准确路径能融合QK、online Softmax、PV；不强迫全概率行写DRAM；decode仍有KV带宽 |
| [Softermax, DAC2021](https://doi.org/10.1109/DAC18074.2021.9586134) | 第III-VI节、表I-IV；7nm综合/物理估算及BERT微调证据 | PWL exp2/倒数、移位归一化可作近似对照；直接e^x→2^x改变温度，不能称无需验证的Qwen等价实现 |
| [ITA, ISLPED2023](https://doi.org/10.1109/ISLPED58423.2023.10244348) | 第III-V节、图4及表I；公开RTL；22FDX布局后synthetic-switching功耗估算 | 共享倒数器、低位指数和重叠调度很强。文中Softmax约占完整加速器估算功耗1.4%，此比例不能外推到本项目 |
| [VEXP, ARITH2025](https://doi.org/10.1109/ARITH64983.2025.00016) | 第III-VI节、表III/IV；GF12nm布局后BF16结果 | BF16数字EXP已有低成本结构。968μm²是EXP面积，7.1mW/0.45Gitems/s是每核整Softmax；不得拼成完整算子PPA |
| [SANTA/S²ANTA, 2026](https://arxiv.org/abs/2605.01910) | 第2/3/5节、表1/5；GPU采样/质量和GQA数据 | 每query/head一个systematic偏移就能生成一组样本；V稀疏收益不是物理p-bit专属。其Bernoulli QK是query特征采样，与本项目token块筛选不同 |
| [Whitehead等, Nature Electronics2023](https://doi.org/10.1038/s41928-023-01065-0) | CTMC/Poisson类别神经元及16/144电路实验 | 原生事件率可形成类别采样机制，但不能推定2048类Attention的面积/速率 |
| [Whitehead等, JXCDC2024](https://doi.org/10.1109/JXCDC.2024.3452030) | 第II/V节、式3、表3；65nm实测电路 | 二元p-bit的50MHz flips、81μm²、1pJ/flip不是独立Softmax类别样本PPA；需另算配置、状态/读出和大类别网络 |
| [Singh等, Nature Communications2024](https://doi.org/10.1038/s41467-024-46645-6) | sMTJ异步时钟+数字PRNG实验；另有综合/HSPICE估算 | 物理源可深入更新时序，但这与慢更新seed不同；不把桌面毫秒器件和纳秒估算混称实测 |
| [Lee等, Scientific Reports2025](https://doi.org/10.1038/s41598-025-93218-8) | 180nm可控概率/chaotic源、FPGA系统和方法 | 可研究本地独立噪声；4.26pJ/bit对特定48-bit LFSR的比较排除FPGA外围，不能据此宣称整机获胜 |

特别相关的 [Energy-Efficient Parallel Ising SoftMax Engine…](https://doi.org/10.1109/LED.2026.3691358) 已核实正式元数据：IEEE EDL 47(7),1458–1461,2026-07，8作者。官方/作者开放入口未取得可读全文，官方PDF链接返回HTML。已有Zotero条目 `7QSGIULK` 复用；本计划不使用摘要中的32μs/FP16宣传作为定量依据。缺口是原文中的向量长度、误差/采样协议、器件/系统边界与PPA表。

阅读记录、合法PDF和已收录条目见 `work/amlink1219/33/REFERENCES.json`。上述文献均未在本次独立复现；原文访问不足的项明确标注。

## 3. 现有随机源的真实实现

根服务和本地PRNG的层级理解基本正确；代码未规定根源必须位于芯片外。当前主要事实：

| 层次 | 已实现/已建模内容 | 尚缺的证据 |
|---|---|---|
| 根物理熵预算 | 配置为4路×1MSample/s；1024原始样本形成256bit；根256bit默认1秒刷新；32bit种子总线@100MHz | 这些是宏参数，未认证器件、min-entropy、健康检测、调理电路或封装位置 |
| FFN本地源 | 默认每tile派生32bit子种子；32bit状态和checkpoint，输出8bit随机字供64路；输出波恢复同一检查点 | `periodic`的1ms参数不是默认per_tile的周期；不能破坏其重放语义 |
| Attention leaf | 数字32bit随机字，默认4word/cycle；根epoch后域分离派生；router为数字sigmoid+PRNG比较 | 数值mask仍由软件理想PRNG产生，未回放硬件leaf实际位流 |
| PV systematic | 每query/head一个随机phase，样本约L/16 | 不需要每个样本一个新的32bit随机字；相关序列质量还需模型验证 |
| Ising v4 | 内部源、状态、抑制反馈、编码器包含在独立宏PPA；外部供候选bias并接类别索引 | 默认ideal IID oracle只生成地址，内部网络、混合、有限精度和真实PPA未实现/标定 |

当前Llama主表使用固定权重FFN；仅可选dual_sc_sz会启用大量权重侧PRNG，不把该成本套到主表。根物理熵不应与PRNG扩展位数混为一谈，SHA256/SHAKE的软件域分离也不是免费硬件。

按现配置做一个量级核算：Llama2 4K、32层×32头，router合计65,536个32bit字/token，systematic合计1,024个字/token。若leaf连续4word/cycle@100MHz，仅生成服务分别约0.16384ms和0.00256ms；不含播种与调度。Ising当前100ns/sample、256样本、1024个head-query的串行间隔约26.2ms/token，另有配置/预热/直方图背压。这些是配置算术，不是新仿真或实测；提示优先优化有效类别吞吐与控制接口，而非单看raw随机bit速率。

首个实现要求是让数值与TLM使用同一份随机/索引轨迹，消除“软件用一种理想源、硬件按另一种源收费”的断层。明确stream ID：run/root_epoch/token/layer/head/purpose/chain/counter；跨头复制相同seed作为故障负对照，不能当正常共享。

## 4. 公平基线及输出契约

| ID | 路径 | 用途 |
|---|---|---|
| D0 | FP32稳定Softmax：max→减法→EXP→sum→每行一次倒数→归一化 | 数学/质量参考；记录实际FP32和BF16边界 |
| D1 | 常规数字专用流水：共享lane、EXP范围约简+LUT/PWL、FP32累加、共享倒数、行缓存 | 首先回答与传统硬算比；不人为堆M个除法器 |
| D2 | online Softmax+未归一PV，最终一次倒数与d维缩放 | 准确整Attention强对照，计running-max更新造成的输出重缩放 |
| D3a | 同一数字Softmax+IID类别采样+相同V-gather/累加 | 隔离相同IID任务的采样器成本 |
| D3b | 同一数字Softmax+systematic单偏移采样+相同V-gather/累加 | 更强数字采样对照，按最终误差/方差匹配，不能只匹配样本数 |
| P0 | 相同score/温度的原生sigmoid p-bit筛选+数字D3b | 优先验证的小型混合候选 |
| P1 | 有限时间binary Ising/硬抑制网络+索引输出 | 要有真实转移/反馈/非法态模型，不能用ideal oracle代替 |
| P2 | 可调事件率原生categorical/Potts候选 | 与P1分开命名；率发生器/锁存/编码器及时间相关都收费 |

常规D1先固定1/4/16 lane、同一55nm工艺/角/电压和100MHz目标；exp用数学等价 `2^(x·log2(e))` 的范围约简/PWL候选，FP32累加。D0严格IEEE语义参考与D1近似电路的误差分开。BF16输入/输出、FP32内部为一档，完整FP32为另一档，不拿BF16文献功耗冒充FP32。ITA/Softermax式8/12/16bit作后续质量匹配Pareto点，不默认无需训练。

先固定比较接口：

- **完整概率向量**：p-bit必须加直方图、归一化及足够采样，不能拿少量索引与完整p向量比任务完成时间。uniform长行可暴露此任务的采样成本。
- **S个类别索引/计数**：比较D3a与P1/P2；二者消费同一logit、候选映射和输出接口。
- **最终d维Attention输出**：比较D2、D3b及P0/P1/P2，包含全部K/V流量、累加与缩放。筛选后估计的是候选条件分布，丢弃质量另测。

三个层次分别计账，不能因为Ising直接输出类别就同时宣称完整概率也已精确求出。物理随机性不是推理正确性的前提；数字PRNG必须保留。

## 5. 可改变的随机源架构

| ID | 架构 | 需要的接口/计费 |
|---|---|---|
| R0 | 软件高质量独立IID参考 | 只验证数学，不计作已实现硬件 |
| R1 | 现根TRNG→调理/扩种→慢刷新→local PRNG | 熵/健康检测、seed总线、启动、状态/重放、PRNG更新和分发；保持当前基线 |
| R2 | 分簇本地无偏TRNG/更改重播种策略，仍数字sigmoid+比较 | TRNG去偏/调理/相关性及供给速率；仅改seed部署不称原生概率计算 |
| R3 | 保留R1服务FFN/控制；原生可调p-bit直接输出router mask；PV用数字systematic | 省掉的数字sigmoid/RNG/比较与新增bias驱动、校准、sense/CDC按同范围比较 |
| R4 | Attention独立原生类别/Ising模块，FFN继续R1 | bias load、settle/burn、反馈、状态、编码、直方图/背压；内部源不重复计费 |

默认不强迫FFN、router、PV和Ising用同一种源。第一轮优先R1/R3/R4。是否分簇、物理源放片内或外部、复用多少p-bit，都作为设计变量。

慢更新seed本身不必然导致统计偏差；更频繁seed也不必然改善精度。先验证周期、域分离、跨消费者相关性和实际位流。改变root epoch不得中途破坏FFN需要的checkpoint重放。per-query reseed若超过熵/总线供给，必须出现排队/背压，不能假设免费服务。

## 6. 分阶段仿真实验：先回答价值，再扩大

| 阶段 | 具体内容和有限规模 | 交付/放行条件 | 预计安排 |
|---|---|---|---|
| E0 基线与接口 | 核模型/语料/代码SHA；定义三个输出契约；明确FP32/BF16/定点；接硬件PRNG位流和sample_trace；不改变FFN | 标识、端点、mask、概率、索引、计数守恒检查；当前基线可复现 | 第1工作日 |
| E1a 完整概率/硬算 | D0 FP32、BF16/FP32、数字LUT/PWL：3M×3profile=27行；native索引直方图S512/4096、3seed=54行 | 固定完整概率向量契约；81行单行微基准，不是模型PPL | 第2–3工作日 |
| E1b 有限样本任务 | M64/512/2048、S32/128/512、uniform/peaked/real、4类采样backend、三seed，共324行 | 先12个pilot估时；按实际V输出误差及匹配IID有限样本带评判，不用短序列经验TV直接判错 | 第2–3工作日 |
| E1c 小状态与长链诊断 | M4/8小状态8项；M512两类输入的burn/spacing敏感性54项；最多3入围配置×3seed的独立长诊断9项 | 共最多71项，长链与任务S严格分开；受pilot运行上限限制，不可行点列未验证 | 第2–3工作日 |
| E2 独立筛选器 | dense、确定top-B、数字Bernoulli、无偏TRNG+数字比较、原生p-bit；匹配总块保留率1/8、1/4、1/2；L512/2K/8K拆行，补dense对照；首/近块规则一致 | 保留mass、候选方差、GQA并集、实际K burst、摘要/路由成本；native必须单独胜数字判决 | 第3–4工作日 |
| E3 真实模型质量 | Qwen2.5-0.5B全部24层，FFN先保持原BF16；逐层/逐头trace后仅选不超过3个随机方案做完整WT2 | 完整2K/stride1024，重跑原BF16；≤3随机方案×3seed，加1个数字近似对照，本轮最多11个正式PPL，边界5seed的最多6次追加另列下一轮；逐更新Ising不默认进入；失败点停止扩大 | 第4–6工作日，GPU时间由pilot确定 |
| E4 RTL/工艺PPA | 对通过E1/E2的D1/D3/router/RNG与counter做功能一致RTL、同频同接口DC/PT；native器件使用可核曲线或目标参数扫描 | 真实cycles、area、active/idle能量、timing/注释覆盖；模拟单元无模型则只给达标边界，不编造工艺结果 | 第5–8工作日，取决于库/许可证 |
| E5 系统闭环 | Qwen2K为通过同context质量的6类×3seed；8K的18点仅成本压力测试，不作同质量获胜结论；合计最多36个TLM | 2K比较时间/J/面积、实际字节及总账；8K若要升级结论，先另列同context BF16与入围方案PPL预算 | 第7–10工作日，取决于前面是否放行 |

这是建议工作日安排，不是已运行耗时或GPU配额承诺。所有新重计算走Slurm计算节点，先核身份、个人根、模型/数据授权和allocation；先一个短preflight，后一次GPU任务，不盲目提交全矩阵。未知环境/数据只阻塞相应执行，不把计划写成结果。

### E1：用最少计算验证最危险的假设

M为候选类别数，L为原上下文，S为采样数，B/spacing为网络更新预算，四者分开。M≤8时枚举有限状态转移并核目标稳态；硬互斥合法态模型与有限抑制/延迟产生非法态的模型分开。大M先3类代表输入、固定B=16/spacing=4作为数字串行参考，记录所有attempt。1次sweep=(M−1)次更新尝试；不能将它称为一次物理翻转。可用保留等待时间的事件驱动软件加速，但硬件仍计所有应付更新。

真实异步网络采用离散事件模型，显式加入p(I)、相关时间、反馈延迟、读出/死区和冲突。bias切换后从至少两种初态测响应；warm start必须付新分布的稳定代价。器件gain/offset/温度或公共噪声来自可核数据；没有数据的0/1/5/10%误差点只标压力情景。

E1a的完整概率主契约为FP32输出：相对D0的TV≤1e-3、归一化行和误差≤1e-5、无NaN/溢出；BF16转换另列其量化误差。native直方图必须计足采样、计数和归一化，达不到门槛就记录该契约失败，不外推到直接V采样契约。

E1b只有S≤512，不能用其经验直方图的绝对TV阈值检验大M分布：例如uniform M2048/S512，即使理想IID，经验TV也至少为1−S/M=0.75。此阶段比较任务V估计bias/方差及匹配IID有限样本参考带。

E1c对最多3个入围配置单列长期诊断，初始131072个保留输出/seed，按pilot决定是否可承受；它不同于模型使用的S。报告重要类别indicator、合并尾部和实际V投影的ESS及区间；稀有态样本不足不宣称已认证。大M经验TV必须与等长IID参考及有限样本区间对照，不能套小M阈值。每backend先120秒pilot；长期诊断预计超过30分钟/配置时先停止扩大或采用已验证事件驱动方法，无法达到统计要求则保持未验证。

E1c还扫描burn={0,16,64}、spacing={1,4,16}，16/4只是旧数字参考，并非证明充分混合。以上324行不包括E1a或E1c。双峰、长尾、flat-tail、mask/all-masked和突然切换是另行声明的诊断输入集；all-masked须输出约定invalid/空行状态，不能以NaN通过。

uniform、近delta、双峰、长尾、真实logit及mask压力输入覆盖概率范围。长行显式8-bit概率可能全部归零，必须检查；优先FP32/BF16或不物化概率的D2，整数累加按位宽+ceil(log2M)+guard推导。禁止把8bit输出短序列论文直接搬到8K。

类别样本测indicator和实际V投影的自相关/ESS，不对整数类别编号直接算有物理意义的ESS。报告TV/JS、稀有事件置信区间、输出bias/方差；p-bit在ESS比例r时可能需约S/r次采样匹配IID方差，该近似只作诊断。最终与systematic按实际输出误差匹配。

### E2/E3：真实数据和质量口径

Qwen主线为GQA：24层、14Q/2KV、d=64。用于校准的train窗口与test评估窗口分开；第一轮选择8个固定test窗口、每窗口8个decode位置，L=512/2048/8192，各64个query，记录窗口锚点/IDs和全部头。L512共有8块，强制3块使总保留率下限为3/8；1/8与1/4目标标为不可行并跳过，禁止静默改成另一保留率。CSV拆成108个筛选配置行（24个不可行）与3个deterministic dense对照，87个有效planned点。先在其中固定96个覆盖不同层/头/查询的row做筛选，随后评估完整集合；不择优挑样本。长trace/V保留授权服务器，Git只索引和SHA。

筛选比较：同强制块规则、同目标保留率，所有路径都算摘要/mean/std和评分；另做不筛选对照。数字和native概率实现使用同一score/温度与量化映射；控制相关性实验改变head/KV组共享时注明算法已变，并重新做质量。一次选择同样比例不意味着同mass或同物理K流量。

正式首轮完整PPL仅Qwen2K协议。主质量门槛建议为相对当次BF16的 ΔNLL≤0.01 nats/token（约PPL增加≤1.005%），并画0.005/0.02两档敏感性；随机至少3seed；11次是基础上限，若边界仍需5seed，另列最多6次追加（最坏总17次），不默认启动。区间使用query/window成组、seed重复的配对分析，不把共享头当独立样本。每窗口按目标token总NLL合并，不平均窗口PPL。局部NMSE/cosine/mass只是筛查，不能代替PPL。

原样串行random-scan Ising不得直接塞进全WT2：M2048、B16、spacing4、S128时，每head-query要1,080,816次attempt，Qwen每token约3.63e8次。先按pilot估完整评测成本；超运行预算则只做局部真实网络与明确标注的质量上界。若采用高效统计/事件代理，须先在留出logit上核bias、时序相关和输出误差，并标为surrogate；ideal IID不能作为物理p-bit完整质量已通过的证据。未经验证的native方案不进入等质量系统胜负表。

8K本轮只做成本stress，不作等质量优势结论。若升级，另建后续质量批次：至少1次同context BF16，加最多3随机方案×3seed（最多10次），独立预算/门禁。不能用2K的11.652735当分母。Llama2若进入泛化，遵守其2K/4K、stride512协议，不能外推8K或继承Qwen质量。Attention先独立通过，再与Issue19/22/32确认的FFN版本联合；联合点重新验证，不能拼接两个独立PPL。

### E4/E5：成本与收益的边界

常规数字面积、功耗用同一PDK/角/电压/目标时钟和相同激活trace；比较同资源、同吞吐、同面积三种口径，区分Pareto点。计算SRAM端口、row缓存、反馈、DAC/驱动、校准表、seed扩种、encoder、计数/缩放、控制、时钟和泄漏，不能只报p-bit阵列核心。

无同工艺native模型时，数字可先做55nm SS/100MHz综合与PT，native以目标能量/时间/面积曲面求盈亏线。不能把65nm/180nm论文器件的fJ、翻转率按线性比例搬成55nm实测。物理源always-on、duty-cycle和wakeup成本分别建模；S2ANTA式数字phase仅用少量随机字，不能按S倍虚增其供给需求。

系统两档：全部工作集驻SRAM的模块边界；KV在外存的DRAMSys边界。所有方案使用同内存控制器、容量、burst、数据格式和地址布局。先同mask/index trace回放隔离硬件代价，再各自真实sample trace比较质量和流量；同地址结果不等于各源已达到相同质量。

## 7. 盈亏条件及停止规则

筛选算法的净收益：

`saved(K physical traffic + QK) > summary build/update/read + proxy dot + normalize + select + budget repair + extra address/burst cost`。

原生筛选还必须满足：

`E_native_bias/sense/calibration + E_native_decision < E_digital_sigmoid + E_PRNG + E_compare`，输入score、质量与吞吐相同。

原生类别采样总成本：

`E_native = E_bias_load + E_settle/burn + E_updates/events + E_feedback + E_encoder/readout + E_histogram/backpressure + idle/leakage`。

与D3比较时，数字侧为max/EXP/sum/倒数或未归一采样、随机源及采样控制；公共V费用只在实际S、地址分布和实现相同后才可抵消。与D2比较时必须加回V读取、累加和最终缩放。

时间同样计配置+稳定+有效样本+读出，多个链/宏只能经资源调度获得并发，不能直接把时间除副本数。绘制M、S、配置带宽、bias位宽、effective sample period/ESS及模块面积的盈亏边界；“需要达到1ns”这样的点只表示器件目标。

继续标准：同一完整质量门槛下，P0/P1/P2至少在能量/面积/延迟中形成有意义的Pareto点；可用≥20%总Attention能量改善作为优先工程目标，同时报告所有连续结果。该20%是计划优先级，不是显著性定理或用户已确认阈值。

停止/降级：若只减少随机源数却不改善真实模块成本；若胜过D1但输D2/D3；若只有理想oracle可满足质量；若反馈/ESS/配置成本已超过数字边界，则停止放大Ising网络，保留小型native筛选+数字PV或完整数字方案。负结果仍归档。

## 8. 执行入口、交付和权限

待实现改点：`attention_reference_v3.py::TraceSource.random/selector` 接统一RNG后端；router原生路径替换sigmoid+random_words+sampler并保留摘要费用；`ising_macro_v4.py` 使用已有sample_trace接口回放带candidate_ids的真实有限时间索引；实际加载的 `llama7b/runtime/` 与根目录副本分别固定版本，不只修改未加载副本。

建议新增模块为 `architecture_tlm/experiments/attention_value/` 下的数字golden/位明确模型、RNG后端、器件事件模型、trace导出和聚合器；此目录本次尚未实现。配置安排见 `configs/attention_value_plan_20261018.json`，有限case清单见 `work/amlink1219/33/EXPERIMENT_MATRIX.csv`。这些是配置规格而非已可运行的仿真命令；执行实现另有明确验收后再启动。

每次run记录run_id、Issue、代码commit/dirty补丁、配置/模型/tokenizer/语料/校准SHA、环境、seed与stream协议、Slurm ID、命令、指标及产物位置/SHA。原始数据/权重/长trace/VCD、工艺库留授权共享存储；不公开其原件。当前本任务只有小型计划、参考索引和协作记录。

当前GitHub身份 `amlink1219`，目标仓库push=false、triage=false；本任务Issue已建立，但文档任务分支/PR尚未上传，Projects缺read:project待同步。不得改用其他账号或旧个人库。任务独立分支 `task/33-attention-value-plan`，交接见 `work/amlink1219/33/HANDOFF.md`。本次完成调研与安排不代表上述实验已执行。
