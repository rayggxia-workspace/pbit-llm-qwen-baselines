# 已有三seed各20000次采样

数据：`C:/Users/86134/Documents/a_P_BIT/analog_pbit_20261016/ideal_and_old_20000_v1/`。

每个 `seed*_samples.csv` 含20000行、真实时间、核心电压、理想判决和旧比较器判决/电平标记；每个 `seed*_ideal_0p6V.txt` 和 `seed*_old_comparator_threshold.txt` 均为20000行0/1。三个seed分别保留，不拼接。

原始时间为2ms到21.999ms，固定1us间隔；理想阈值固定0.6V，旧比较器判决0.4V、有效低<=0.16V/高>=0.64V。理想bit不是新实际比较器，旧阈值bit含MID而未删除。500Hz/20ms数据不覆盖长期漂移或熵认证。

精确原始归档/PSF成员/SHA和统计见SUMMARY.json；逐导出文件SHA见manifest.json。执行时的导出代码原字节保留在 `work/rayggxia/184/export_existing_executed.py`，其SHA与SUMMARY一致；便携版本仅将写文件方法调整为Python3.6兼容。
