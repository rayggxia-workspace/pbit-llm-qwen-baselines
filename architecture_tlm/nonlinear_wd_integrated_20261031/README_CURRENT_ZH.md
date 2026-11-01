# 完成：已有g/u→非线性→Wd的真实集成PPA

2026-10-31，Issue204/PR219。从已算好并编码的raw8/raw9 g/u开始，不包含第一GU矩阵或写入前编码。当前入口：[完整表](results/REPORT_ZH.md)、[精简数据](results/SUMMARY_SMALL.json)、[源码索引](results/SOURCE_INDEX.json)、[两版完整小源码ZIP](results/SOURCE_CODE_V1_V2.zip)。统一run为`nonlinear-wd-integrated-204-20261031`。

N64/M8/T32：一份64路转换、64全Sigmoid LUT、192比较器、三路AND，实际驱动8列固定W8，完成OR4/精确归约、时间累计及尺度恢复。每帧34周期/340ns输出8个K64点积，每列32位整数C和共同指数e表示C×2^e。没有额外z或概率寄存层；权重在功耗窗口内驻留，g/u只在帧边界更新。

8配置、3seed：RTL和门级各11,496次逐拍oracle检查通过，48个PT窗口计算完成，100%叶单元活动覆盖。SS1.08V125℃100MHz，输出负载.001pF/bit；面积raw单次×.81，功耗/时间不缩放。原位平面精确、OR4safe11、OR4signed9饱和均保留；另补每拍权重加法树＋每列单19位时间累加器，和原精确版stim/expect字节相同，不是按输入先计数再数字化。

精确单累加器版能耗：8位436.6733、9位479.8533pJ/帧；OR4signed9版458.7733/467.9533pJ/帧。OR4更省面积，未必更省能。精确版仅对相同采样事件不增加OR/截断误差，仍有T32随机采样误差；合成激励的OR碰撞诊断不等于模型质量评测。

所有配置在当前前布局约束下setup/hold均非负，但weighted的setup余量仅.015331ns(8位)/.001764ns(9位)，不能当布局后已闭合。PT保留out_of_range ramps告警（8位weighted单窗口例如69处）。无CTS/SDF/SPEF，不冒称物理签核。

四档[3,4,5,6]是测试尺度、活动为合成码，不是真实模型轨迹。RNG、SRAM及读保持、整层跨K合并和BF16格式恢复在外；旧两共享随机源/映射逻辑可另作约24.8769pJ/帧代理，不能据此称实际随机源及64lane相关性已接合验证。

重放源码：`rtl/integrated.sv`是v1位平面版本，`execution_v2/integrated.sv`是加入weighted的版本，应分别编译。源码ZIP含完整RTL、top、bench、工具流程与准确执行manifest；每版本目录执行`python -B rebuild_fixtures.py`生成并SHA核对原合成激励。VCS/DC/PT和外部MATRIX_PRIVATE_LIBRARY绑定需自行提供；job.sh需显式指定工作目录。ZIP不含工艺库、凭据、模型/语料、原始波形或网表。大输入包和原始报告留既有项目归档，索引见中央run。
