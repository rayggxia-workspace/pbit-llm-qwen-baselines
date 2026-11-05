# Issue95 九项数字p-bit预算表

2026-11-02，rayggxia；task/95-nineway-power-20261102，base main0320f486。独立小工作树tmp/rng-nineway-issue95-20261102，未改旧catalog目录的其他任务未提交状态。已核实PR215真实合并6d5471c1；Issue95仍继续。

正式结果architecture_tlm/random_service/digital_pbit/nineway_20261102。三源×全LUT/4节点共享/8节点共享，128节点，SS100MHz，K1/64/128。不是整阵列只用4/8表；q8寄存存已算概率，不存输入x。源取38322118整端点，比较/输出保持不重复收；载入时端点idle，缓存用q9/valid残差代理，q8端点裁剪显式标注。全部组合估算，不是九核实测或同质量验收。

实际验证python build.py两次输出逐字节一致；27行81项量纲/能量/容量守恒断言。输入原件SHA及费用在INPUTS，逐项能量RESULTS；模型/语料不适用，无新EDA/PPL/波形，不新增电路run，不改旧记录或TLM默认。中央summaries/20261102_digital_pbit_nineway及根architecture镜像同字节。

功率依旧完整端点+组件活动价；纯8DFF、选路写译码、输入保持、ICG、实际组合活动/扇出和物理熵源仍未闭合。不得把旧紧凑GF Attention整机query价混入三类裸源比较。下一步按实际K、共享含义和端点边界选真实集成验证；本轮未提交远程作业。发布回执见PUBLICATION.json；Projects尚未同步，不自动合并/关闭Issue95。
