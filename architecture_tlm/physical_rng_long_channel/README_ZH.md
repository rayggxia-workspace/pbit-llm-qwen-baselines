# 单通道秒级噪声记录准备

Issue [152](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/152)，负责人 `jieruiz`。依赖 Issue95 的现有随机服务模型，不修改其模型、RTL、进度或旧结果。

可上传脚本在 [src/README_ZH.txt](src/README_ZH.txt)。本轮是脚本及检查器交付；没有远端 Spectre/Slurm 执行，也没有新的物理随机质量或 PPA 结论。

选现有 `buffers_x2`：原两 MOS 零外加 C 核心、15 MOS 旧比较器及 5 fF 输出负载，TT/25℃，核心 1.2 V、比较器 0.8 V/10 nA，始终通电。没有共享读出、间歇开启或真实 1.2 V 接收器模型。

按三个独立作业执行：

1. `bash submit.sh pilot`：物理门禁、四种噪声贡献开关、500 Hz 短程步长/带宽检查及成本外推，正常18例。
2. `bash submit.sh calibrate /绝对/PILOT结果`：10 Hz 独立三 seed 校准、冻结 Vref，再用另外三 seed 做10 Hz步长/带宽检查，正常27例。
3. `bash submit.sh long /绝对/CAL结果`：10/500 Hz 各三条1.02 s记录，每条丢固定20 ms、有效1 s；100 µs实际取样，恰好10000原始bit，正常6例。

默认每作业8核16GB，独立案例共享最多8路单线程Spectre，不自动提交下游长任务。10 Hz短记录总长120 ms，满足文档的 `stop >= 1/noisefmin` 条件。稀疏保存不替代内部2.5 ns步长或100 MHz噪声设置。

每 seed 单独输出分块 P1、多 lag ACF、电平标记、VN全部/有效输出及真实时间戳、32 bit和Bivium177 bit种子包重复/汉明/对应位相关。原始MID不删除；VN选择也可能有偏，不认证熵。提供有时间戳的模型source适配器和调用已有Endpoint的包接口探针；探针不作完整时间线/PPA结论。

[本地验证](validation/VALIDATION.json)：20项脚本检查、16模块Python3.6 AST、两入口Bash、27个本地PDK哈希、51份预览网表及6项既有数字模型包接口探针通过。1 s/10000 bit统计检验输入是明确标注的合成夹具，不是本次Spectre结果。PDK本体不在仓库；实际18.1编译、noiseoff、噪声启用效果、校准与耗时仍待用户运行验证。

源码包的精确字节由 [package_manifest.json](src/package_manifest.json) 标识；局部属性保留归档字节。中央台账以 prepared 登记本批，不把51份预览计为51个已完成实验。
