# TT100 / TT250 配对复核

同一 TT1.2V25℃、原 RTL、不同周期重综合。面积为原始面积乘0.81一次；功耗与能量不乘该系数。以下为前布局活动功耗，不是芯片签核。

|模块／工作模式|面积100→250 mm²|变化|功率100→250 mW|单位能量100→250 pJ|能量单位|
|---|---:|---:|---:|---:|---|
|ab_both / work|0.045655 → 0.047237|+3.47%|0.803 → 2.036|1112.228 → 1128.392|query K128/S64|
|bf_vacc16 / stalled|0.143097 → 0.159201|+11.25%|5.961 → 16.667|6.019 → 6.732|vacc: one scalar ADD; ctrl: one accepted sample descriptor; idle operations0|
|bf_vacc16 / stream|0.143097 → 0.159201|+11.25%|7.657 → 21.767|4.907 → 5.580|vacc: one scalar ADD; ctrl: one accepted sample descriptor; idle operations0|
|bf_vctrl4 / backpressure|0.066089 → 0.066532|+0.67%|2.886 → 7.229|216.947 → 217.343|vacc: one scalar ADD; ctrl: one accepted sample descriptor; idle operations0|
|bf_vctrl4 / cold|0.066089 → 0.066532|+0.67%|4.089 → 10.200|125.428 → 125.163|vacc: one scalar ADD; ctrl: one accepted sample descriptor; idle operations0|
|bf_vctrl4 / reuse|0.066089 → 0.066532|+0.67%|4.076 → 10.200|122.058 → 122.188|vacc: one scalar ADD; ctrl: one accepted sample descriptor; idle operations0|
|db_fma16_c4 / backpressure|0.201733 → 0.248797|+23.33%|11.500 → 34.133|8.058 → 9.567|FMA|
|db_fma16_c4 / continuous|0.201733 → 0.248797|+23.33%|12.467 → 36.967|8.005 → 9.494|FMA|
|db_fma16_c4 / paced25|0.201733 → 0.248797|+23.33%|3.378 → 9.958|8.485 → 10.006|FMA|
|db_fma64_c4 / backpressure|0.813693 → 0.989459|+21.60%|46.700 → 134.767|8.180 → 9.443|FMA|
|db_fma64_c4 / continuous|0.813693 → 0.989459|+21.60%|50.700 → 146.533|8.138 → 9.409|FMA|
|db_fma64_c4 / paced25|0.813693 → 0.989459|+21.60%|13.633 → 39.167|8.562 → 9.839|FMA|
|screen_norm16 / group|0.066021 → 0.072781|+10.24%|1.576 → 4.162|27264.800 → 28803.347|4Q normalization group, N2048|
|screen_top16 / feature|0.020003 → 0.020569|+2.83%|0.646 → 1.630|1047.280 → 1057.189|one feature selection frame|
|screen_top16 / token|0.020003 → 0.020569|+2.83%|0.959 → 2.429|7815.611 → 7916.357|one token selection frame|
|softmax_r8_gf64 / work|0.078440 → 0.080910|+3.15%|0.805 → 2.052|1715.504 → 1749.900|query K128/S64|
|softmax_systematic / work|0.080741 → 0.083222|+3.07%|0.725 → 1.870|1209.311 → 1248.759|query K128/S64|

FMA64/250原批因超时缺seed1009回压与两idle窗，三窗已补算并合并，15/15窗齐；原超时及原报告保留。不同模块的能量单位不同，不能逐行直接相加。

采样器工作窗包含12次查询及窗内间隔，以原窗总功率×时长÷12计价。SparQ归一化group是4个Q头；top的feature/token是各自单个选择帧，不等同整个Attention。

原归档器误跳过名为work的目录，已从原服务器报告补收18个工作功耗窗口并核验SHA，未重跑这18个窗口。原包和原manifest均保留。

门控idle仍可能包含ICG上游时钟引脚功耗和漏电；完整细分见JSON。新增PV4复位候选、共享QK包装与真实K布局调度仍单独验收。
