# 当前结果：T64非线性直连Wd

用户要求64有效采样；N64/M8、8位g/u和比较器、SS1.08V125℃100MHz。加权单累加器20位、OR4每平面9/10位饱和；两者均保留现有全LUT/共享概率缓存实现，不新增Wd门控。全LUT66拍660ns，共享单银行98拍980ns，输出共同指数eg+eu+ew−6。

8配置、RTL与门级各26952逐拍PASS、87PT窗口，完整三seed结果及实际时序/告警如下。每帧8个64项输出；不要把功率比、帧能量比和采样比混为一个指标。面积raw仅乘0.81一次。

- [功率、能量、面积、T32比较及原生时序](results/REPORT_ZH.md)
- [完整小型数值与Sigmoid/后端分项](results/SUMMARY_SMALL.json)
- [执行源、报告索引与SHA](results/SOURCE_INDEX.json)
- [RTL及成熟VCS/DC/PT流程源码ZIP](results/SOURCE_CODE.zip)：含独立rebuild_fixtures.py，Python≥3.10可重建72个激励/期望/窗口文件，全部原字节匹配冻结manifest。

g/u/W与冻结T32合成功耗帧一致；T64门限格为4×4×4，旧T32为4×2×4，不能称同随机轨迹、训练重放或新模型质量验证。OR4/9位与10位饱和均为近似。GU、编码、SRAM、实际PRNG/广播、跨K/BF16和CTS/SDF/SPEF不在边界内。功耗已算出不等于后布局时序签核。

idle诊断保持g/u/W、en=0，自由时钟和外部随机门限端口仍有活动；全系统停源/停钟待机成本需采用对应激励另计。

统一run nonlinear-wd-t64-204-20261031。精确执行源为source_base7b299808＋冻结ZIP/manifest字节；公开交付commit不是服务器执行源commit。旧T32结果及p-bit交叉核对保留。
