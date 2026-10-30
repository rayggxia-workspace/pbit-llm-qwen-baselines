# GPU能量测量核验补充（2026-10-30，Issue212 / PR214）

结论：累计能量差分的方法合适，本次未发现J/mJ或token数量的换算错误；几J/forward的数量级再次出现。但应称为特定实现/设备条件下的NVML设备遥测，不能称为已通过外部校准的绝对能量或GPU最优能耗。

Slurm3417已完成。新增计量验证与原3399分开封存，不改写原结果；复用同一模型revision、准备清单SHA和token SHA，B1/2K/BF16/SDPA。每阶段两次，预热4秒，约15秒窗口，另线程约20ms读取一次功率。两条接口都来自NVML，属于内部一致性核验，不是独立电表。

|执行方式|累计能量J/forward，两次|功率积分J/forward，两次|接口差异|
|---|---:|---:|---:|
|普通固定forward|5.262 / 5.291|5.194 / 5.263|1.30% / 0.52%|
|CUDA Graph固定forward|4.378 / 4.435|4.362 / 4.428|0.36% / 0.16%|

模型驻留空闲约65.11W，两条接口差异绝对值均小于0.14%。六个窗口最大差异1.31%；这不是NVML绝对精度的上界，不能写成测量准确到1.31%。

## 怎样解读原来的高数值

原3399的能量主值直接用(结束累计mJ－开始累计mJ)/1000，再除以生成token数或forward次数。GPU在边界同步，prefill、加载和图捕获在窗口外；整段能量没有混入模块回放能量。平均W也是由同一累计能量除时间得到，因此它与J/token的算术吻合不能作为独立验证。

例如原2K连续decode三次平均759.226J/128token＝5.931J/token，耗时约3.292秒；原Graph固定forward约3.928J/次。约400W执行10ms本就对应约4J；这只解释量纲和数量级，不替代传感器核验。5.93J/token对应每1000token约1.65Wh。

补测由Slurm分配了同型号的另一张RTX5090（UUID哈希不同），且带功率轮询线程、每16次同步等验证开销，温度/频率也不同。因此本轮Graph约4.38～4.44J与原3.93J不是相同条件的精确重复，不能把接口差异很小理解为跨设备结果稳定到1%。

主值是未扣空闲的设备能量，包含闲置等待和相关显存电路，不是仅乘法器动态能量。原2K Graph若扣当次空闲诊断约从3.93降至3.21J，约18%；简单扣空闲依赖工作状态，只作为诊断，不能当作严格分离的计算能量。

## 当前GPU基线的效率限制

只读核对了服务器实际安装的Transformers4.51.3 SDPA源码：GQA先调用repeat_kv展开K/V，再调用SDPA；Qwen3的8个KV头需展开到32个Q头，存在额外数据搬运。DynamicCache每步追加还会torch.cat已有K/V。CUDA Graph可减少主机发射开销，但不会自动消除这些复制，也未把各类Norm/非线性全部融合。

所以这些数据可以作为该Transformers实现的GPU遥测基线，不能作为RTX5090能够达到的最低J/token。用于论文最终比较还应补充分页/静态KV、原生GQA和融合内核的成熟推理实现；这是执行优化问题，与差分测量公式正确性不同。

模块隔离回放改变缓存/顺序/并发，不能与整段能量相加或称为原生模块独立轨测量。GPU设备能量与ASIC比较时仍须包括ASIC外存/漏电/转换及未价项。当前0.447J/token是已计价项＋旧片外代理的条件预算，不是完整校准芯片能量，不能用这些数值直接宣称已验证8.8倍节能。

## 方法依据与证据

- [NVIDIA NVML接口文档](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html)：累计能量单位mJ；功率包含相关电路，现代卡powerUsage通常是一秒平均值。文档没有给本卡累计能量的通用绝对误差保证。
- [Zeus/ML.ENERGY测量说明](https://ml.energy/blog/energy/measurement/measuring-gpu-energy-best-practices/)：支持同步后的累计能量差分。
- [Oxford研究](https://arxiv.org/html/2312.02741v3)：板载遥测会有采样/平均机制引入的误差，不能只看软件调用频率。它没有验证本次5090。
- [HotCarbon2026作者机构说明](https://mucdai.hm.edu/aktuelles/newsdetail/news_detailseite_528704.de.html)：计数器存在平台差异，须验证，不能默认可用就准确。

本次封存小文件在audit_20261030/。SOURCE SHA、原依赖SHA、输入/模型清单SHA、设备UUID哈希和状态在PROVENANCE；全部服务器文件的SHA在ARTIFACT_MANIFEST，原始功率样本保留同一任务存储。无训练/PPL/EDA；原3399健康结果未重跑或改写。
