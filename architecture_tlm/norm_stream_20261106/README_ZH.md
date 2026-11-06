# 归一化权重按层双缓冲：无损存储变更

2026-11-06，Issue225。用户授权删除全模型norm权重常驻，改为逐层双缓冲；这里增量接入现有整机TLM，不修改旧执行快照或另建整机模拟器。

## 变了什么

RMSNorm的gamma是训练得到的逐通道缩放向量。原Qwen3-4B模型将36层的两个RMSNorm向量、每层Q/K-headnorm向量和最终RMSNorm向量全部预留在SRAM：392192B，即383KiB。它们不是运行时求出的均值/方差，也不是全模型矩阵权重。

新方案仍在DRAM保留完整原始BF16参数，两个16KiB片上槽保存当前/下一层参数。每层块为`attention_gamma[2560] + ffn_gamma[2560] + Q_gamma[128] + K_gamma[128]`，BF16共10752B；最终gamma为5120B。槽内存储不做量化、压缩或数值转换，不改变RMSNorm公式和算术顺序，因此没有这项变更引入的数值精度损失。TLM本身不执行真实模型算术或PPL。

embedding阶段装入第0层；第i层QKV阶段预取第i+1层，最后一层QKV预取final gamma。每槽含tag/ready/released状态；只有本层attention norm、Q/K-headnorm、FFN norm全部读完才允许覆盖，DMA完成前不得读取。只保留两槽，没有额外无限队列或全局排空；请求共享既有有限DMA、24KiB返回保持、512个1RW bank和LPDDR时序后端。

## 配置与价格

|配置|norm预留|SRAM总容量|声明总占用|作用|
|---|---:|---:|---:|---|
|resident_2p5|383KiB|2.5MiB|2359KiB|匹配参考；全部gamma预热驻留|
|stream_2p5|32KiB|2.5MiB|2008KiB|只变norm策略，对照额外搬运|
|stream_2m（新入口默认）|32KiB|2MiB|2008KiB|再缩物理宏数并重排激活/FFN宽状态|

第三配置仍有512个16B/1RW物理bank，但都为4KiB；激活和公共FFN宽状态分散到前256个bank，避免部分bank容量溢出。没有删计算核、缩Attention缓冲、减少K/S/T或修改权重量化。2MiB是本次布局点，不是算法容量下限。

按已有4KiB宏价，SRAM面积17.22447→13.77958mm²，原覆盖67.54145→64.09655mm²（−5.10%）。原65流程面积已单次乘0.81，功耗/时间不套此系数。新缩容的外围/互连没有新增PT，不能把宏拼接面积当整die布局结果。

每token额外读取392192B；相比原5.410998GB约0.00725%。4pJ/bit下外存增量约0.01255mJ/token。相同运行时间、同SRAM单次访问价下，减少128个4KiB宏的保持功率约0.9926mW；旧49.56325ms窗口约省0.0492mJ背景。动态读写不自动按容量缩小20%，新装载动作及实际时间变化由新回放收费；这不是已完成的新整机能量结果。

## 新旧对照中的一处共同修正

旧合并RoPE/headnorm宏没有单独的gamma SRAM读。为了使数据供给明确，三个配对配置均新增每层512B `headnorm_gamma_explicit`读取，保持原RoPE/headnorm算术延迟不变。它是共同的数据流展开，不能把新配对参考称为原49.56325ms封存的逐拍重现。所有旧封存原字节保留；新结果单独发布。

## 验证和运行

8项CPU检查通过：全形状2008KiB/逐bank容量、每个参数段的逐字节复制oracle、36层及final各一次装载、prefetch和槽释放顺序、读前ready及错误tag、无lm时不取final、两侧相同gamma读/算术工作量、构造钩子不泄漏。使用真实beat/bank/DMA执行器和明确的解析外存代理；不是PPL、RTL或PT。

依赖Issue236不可变执行快照，精确版本及SHA见`work/rayggxia/225/norm_stream/REMOTE_PROBE.json`和`SUBMISSION.json`。已用Slurm CPU提交机制检查、三配置两层前缀门禁及九项完整36层＋lm_head（三配置×三seed）；先门禁后完整运行。任务ID和实际状态见交接，提交不等于完成。原生外存是LPDDR5派生8533时序情景，不是厂商LPDDR5X签核。

入口：`python architecture_tlm/norm_stream_20261106/launch.py --runtime <冻结运行根> --tests`；实际回放再加`--profile stream_2m --seed 17 --out <新目录>`。新`make_model`默认stream_2m，旧统一入口/已提交任务未被静默改写；PR待审时以此候选为用户新授权方案。

当前只支持已捕获Qwen3-4B的32Q/8KV/d128及既有角色。Llama/DeepSeek不能直接绕过各自头数与元数据适配。没有训练/PPL或新电路仿真，不新增数字PPA run；SRAM沿已有统一台账宏数据计价。

## 已完成的原生两层预检

保留36层分配、执行前两层、不含lm_head，seed17；三个任务均COMPLETED/0:0，RESULT/BUDGET/执行源SHA及队列/面积/能量守恒已核。

|配置|两层时间ms|两层已计总能量mJ|覆盖面积mm²|
|---|---:|---:|---:|
|resident_2p5|2.36889|9.75659|67.54145|
|stream_2p5|2.36889|9.75765|67.54145|
|stream_2m|2.36845|9.75525|64.09655|

三配置矩阵/Attention actions完全相同；流式两配置多读32256B（3个层块，第三块为有界跨层预取），其他外存读写量不变。当前两层数据表明norm新增装载被重叠隐藏，2MiB重排没有降低吞吐；不能据此替代整token或三seed最终结果。完整九项38614103自动通过依赖门禁后运行，最终数值待SEAL。详细原字节SHA见PREFIX_RESULTS.json。
