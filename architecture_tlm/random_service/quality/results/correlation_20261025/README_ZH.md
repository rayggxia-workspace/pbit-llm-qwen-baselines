# 全路长流相关性：2026-10-25

入口REPORT.html；LAYERS为核心电压、理想比较器、调理和串行打包的实际统计；SUMMARY绑定36个案例及原始数组SHA；PEAKS列每观测最差位置；CONFIG定义所有坐标轴。报告中的最大相关是带符号的绝对值最大项，不是平均值或统一验收阈值。

输入是既有模拟电路仿真的三个noise seed，各20k样本，理想阈值0.6V。不是三路同时物理测量，也不是芯片物理熵认证。数字案例每个只启动一次，seed按1us真实时间到达；本地连续输出131072帧只消费启动前缀，默认1e8拍重播种不触发。两种调理和三种后端分别运行，不把同一试验种子在替代方案之间的复用说成同时服务多个模块。

每案例2实例，words.bin为frame-major uint8、shape=(131072,2*lanes)，先a再b，lane从0编号；states为little-endian uint32、shape=(2,3,6)，依次中点/尾256帧前/最终状态。matrices.npz的*_acf轴为(CONFIG.temporal_lags,lane)；*_cross为(spatial_lag,i,j)，Pearson定义i(t)与j(t+k)；bitplane只含lag0。相关按实际配对区间分别中心化。概率阈值扫描离线作用于同一随机字，不代表硬件同时实例化五套比较器，也不据此统计五倍PPA。

时间lag1..128、256/512/1024；R8及q4/13/64/128/192空间lag0/1/2/4/8/16/32/64/128。全部8bitplane时间相同，空间只同拍。q128和bit7互为反码，同源自/互相关一致已全量核验。变概率、异阈值路对、其他lag不冒称已覆盖。各后端L不同，最大值的搜索数不同；合成同形状PCG64对照不是标准随机性认证。

复现（仓库根，Python>=3.10+NumPy；绘图另需matplotlib；新结果目录不得存在）：

```powershell
g++ -O3 -std=c++11 -mpopcnt -static-libgcc -static-libstdc++ architecture_tlm/random_service/quality/correlation_native.cpp -o <exe>
$env:RNG_CORR_EXE='<exe>'
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
python -m unittest architecture_tlm.random_service.quality.test_long_correlation -v
python -m architecture_tlm.random_service.quality.long_correlation --input <ideal_and_old_20000_v1> --out <new-results> --archive <new-archive> --exe <exe>
python -m architecture_tlm.random_service.quality.audit_correlation <new-results>
python architecture_tlm/random_service/quality/report_correlation.py <new-results> --archive <new-archive>
```

审计会读取上轮225例中18个匹配原始NPZ；需按原归档索引取得，不能缺原件却宣称golden前缀核验通过。CSV保留12有效数字，NPZ为float64。ZIP放在HTML同目录即可使用下载链接；本机交付路径在远端上传/。

C++是本地仿真加速器，无新RTL。7执行文件冻结于2dd9ec33；报告/审计为后处理。长流每个样本按原整数递推生成，初始前256帧对原周期模型、中段/尾段各256帧及最终状态对Python；另18×4096帧对上轮原件。无停顿长段操作数按固定动作累计，不说成每拍都跑RTL。健康调理、CDC和物理慢漂移仍按原条件限制。
