# 常规比较器与2万次读出

Issue [184](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/184)，负责人 `rayggxia`。依赖 Issue152 的既有波形，仅只读使用原件，不接管其旧通道、执行快照或进度。

现有导出数据位于 `C:/Users/86134/Documents/a_P_BIT/analog_pbit_20261016/ideal_and_old_20000_v1/`。三个seed各20000次1us采样，CSV同时包含核心电压、理想0.6V判决、旧比较器电压/阈值位/有效电平；每条另有两个单列0/1文本。Git只存[来源与统计](results/exported_20000/SUMMARY.json)、[原字节索引](results/exported_20000/manifest.json)和导出代码，完整CSV/TXT留在上述本地数据目录。

理想读出是对真实Spectre核心电压进行软件判决，原核心已连接旧比较器，不能改称完全裸核心或实际数字输出。旧比较器20000次中MID分别1089、1145、1115，不删样本；所有时间戳保留。原归档为 `project_archives/analog_long_channel_20261024/results/long_channel_38380128_pilot.tar.gz`，SHA `c02d6ad9e148b143b906c6b3f87c151c9ce8e05e53fe26683dfaf29d4404134c`。

新比较器采用10MOS差分输入、镜像负载、尾电流及两级普通CMOS输出，取消输出限流。1.2V、10/20uA参考电流、SVT/LVT输入四候选，原两MOS噪声核心及5fF输出负载保留。是否属于常规偏置以真实OP的过驱动/gm/Id和饱和裕量为准；单元测试不替代实际工艺结果。

[便携脚本说明](src/README_ZH.txt)包含物理选型、独立校准冻结、新种子数值检查及每seed20ms有效/1us/20000采样。最多8个独立APS1案例，6h计算上限，自动结果包；没有自动1s长任务。500Hz短验证不覆盖10Hz长期漂移；没有阵列MUX/锁存/PEX或熵认证，精确动态功耗未测。

[本地验证](results/LOCAL_VALIDATION.json)：8项脚本/门禁测试、17模块Python3.6 AST、Bash语法、27本地PDK原字节和11个导出文件SHA通过。实际Spectre/Slurm状态见 `work/rayggxia/184/HANDOFF.md`，本页的脚本准备不能当成新比较器已通过。
