## 2026-11-09 新补测回收（2/11）

250MHz R8 GF64已修复原4.089ps setup违例：原RTL/输入不变，仅综合目标3.9ns，正式PT仍4ns。三seed/六功耗窗齐，面积0.08056208mm²、工作2.051000mW、1.749047nJ/query、212.278拍，setup/gate-setup+0.050210ns、hold+0.106584ns。已用新行更新COMPARISON.rows；旧行保留historical_rows，下方旧表为历史证据。与现有Ising相比：Ising能量少35.49%、面积少41.37%、延迟少35.16%。

另TT100 ADD完成15窗，面积0.00802629mm²、stream gross7.063483pJ/op，setup+1.256253ns。仍待其余9配置；不把这两项回收写成全部补测完成。原件/成员SHA校验通过。自动收集38638257依赖两个数组结束执行，完整线上数字控制器仍为原语组合估算。

---

# 55nm Attention数字对照：100/250MHz库存与补充

2026-11-09，Issue198 / PR199。本页只讨论本项目raw65面积×0.81的55nm等效流程，功耗/能量不折算；与28nm结果隔离。

## 已有同条件采样核对照

K128/S64、S12/F4输入先整数max-gap、共享LUT/P8、采样输出。Ising为关钟＋提前赢家保持，无histogram。共同TT1.2V25C、setup/hold额外uncertainty0；三seed17/503/1009，原RTL与输入轨迹相同。新的FP32 max-gap前端及SRAM、QK、PV均不在本表。hold按用户决定暂缓闭合，setup违例仍显式保留。

|核|MHz|周期/query|时间ns|工作mW|nJ/query|面积mm²|setup ns|
|---|---:|---:|---:|---:|---:|---:|---:|
|ab_both|100|137.639|1376.389|0.8027|1.112228|0.04565494|0.349700|
|ab_both|250|137.639|550.556|2.0360|1.128392|0.04723745|0.000938|
|softmax_r8_gf64|100|212.278|2122.778|0.8047|1.715504|0.07843953|0.253041|
|softmax_r8_gf64|250|212.278|849.111|2.0520|1.749900|0.08090967|-0.004089|
|softmax_systematic|100|166.000|1660.000|0.7245|1.209311|0.08074142|0.290508|
|softmax_systematic|250|166.000|664.000|1.8703|1.248759|0.08322177|0.002174|

工作能量按实际窗口总能量/查询数，包含窗内间隔；不能用平均工作mW乘去间隔周期要求末位相同。250 R8仅4.089ps setup违例，原结果保留为诊断，已提交3.9ns综合、4ns正式STA的独立修复；不放宽验收。

|时钟|数字对照|Ising能量降低|Ising面积降低|Ising延迟降低|
|---|---|---:|---:|---:|
|100|softmax_r8_gf64|35.17%|41.80%|35.16%|
|100|softmax_systematic|8.03%|43.46%|17.09%|
|250|softmax_r8_gf64|35.52%|41.62%|35.16%|
|250|softmax_systematic|9.64%|43.24%|17.09%|

这是模块/旧输入合同的成本比较，不是匹配PPL后的整Attention优势；R8输出数可变，Ising/systematic固定64。

## 哪些已做、哪些仍需补

|对照|100MHz证据|250MHz证据|当前处理|
|---|---|---|---|
|Ising vs Softmax+R8 GF64/systematic|SS100主表及TT100配对|TT250三核已测|本页已整理，R8小setup违例补修|
|Softmax+R8 Bivium|SS100实测|此前未做同TT配对|补TT100/250两配置；随机前端参考|
|采样PV ADD vs数字完整PV FMA|实测|FMA16/64、vacc16、PV4包装已测|复用PAIRED_PPA/WRAPPER，不重测|
|稠密在线Softmax+完整PV|旧原生LPDDR模块、当前小SRAM局部回放|当前共享池/48KiB槽的12点双频局部回放已做|标量SS100代理待TT补测替换|
|同SparQ+数字完整PV|同上|同上，筛选/FMA已用TT价格|同上|
|同SparQ+数字PV采样|旧2.5MiB/独立计算配置原生LPDDR已做|采样核TT已测；当前小SRAM共享池整链尚未同边界回放|不把旧100整层数除2.5冒充250|
|全局Top64/128、候选内Top64|旧100算法/选择RTL功能及成本估计|选择原语可用TT；没有相同最新整层映射验收|历史参考，不能称250完整PPA已测|
|K256备用|旧核100实测，新核迁移估算|当前是K128→256校准估算|保留估算标签，不当实测|

## 补测范围与避免重复

在线Softmax补FP32 ADD、MUL、exp LUT、reciprocal seed，TT100/250八配置；原算术RTL/三seed激励不变，真实周期和窗口纳秒重新对应，不以频率比例算能量。现有55 FMA/PV/筛选/前端结果复用。Issue204正在补另一套FFN ADD250，其负载1fF、setup uncertainty0.5ns；本任务沿Attention已用20fF/0ns配对合同，二者不混用。
用户允许暂缓hold闭合，新scalar不运行激进hold修复；原RTL内已有4个enable延迟单元保留。所有min路径继续记录，修buffer成本未来随实际后端回填。
新增任务/阶段/SHA见RUN_STATUS.json；结果未回收前不把价格填入TLM，也不改冻结100/250整机默认。

## 结果入口

- 已有核配对：../attention_tt250_followup_20261107/PAIRED_PPA_ZH.md
- PV/QK包装：../attention_tt250_followup_20261107/WRAPPER_PPA_ZH.md
- 旧整层模块：../attention_digital_paths_20261105/REPORT_ZH.md
- 当前小SRAM数字合同：../attention_digital_small_20261107/HANDOFF_ZH.md
- FP32前端A/B：../attention_score_front_ppa_20261108/HANDOFF_ZH.md
- K256估算：../attention_k256_20261108/HANDOFF_ZH.md
