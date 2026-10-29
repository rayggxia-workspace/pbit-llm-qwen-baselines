# 数字Softmax之后的采样：与Ising统一输出边界

2026-10-29，Issue198 / PR199。只读审计SANTA v2、官方CUDA及PyTorch2.7.1源码，并补全对照边界；没有新GPU、PPL、RTL或EDA结果，不新增仿真run。

比较必须覆盖“相同128个候选分数→可用于V读取的候选索引/次数”。数字采样路线需要计Softmax等价权重处理之后的随机数、CDF/scan、选址或计数、必要缓冲及控制。标准dense Attention直接做加权PV，不执行采样，不能给它额外强加这笔费用。

## 1. 0/1表示需要区分

独立Bernoulli：每个位置b_i=[u_i<p_i]，同一轮可有零个或多个1。即使sum(p_i)=1，也只保证置1数的期望为1，不能直接作为“恰好选一个V”的替代。随后简单挑任意一个1一般也不会恢复目标categorical分布。

Categorical：一次抽出一个位置J，P(J=i)=p_i；one-hot只是J的另一种表示，数字硬件/GPU可以直接输出索引，不必生成128bit再编码。当前Ising候选p-bit向量也还要经过赢家保持/合法状态处理/公平仲裁，不能把未仲裁的bit直接作为等价V读请求。

S次采样最终可以表示为索引序列，或每个候选的命中次数n_i。V读取mask是[n_i>0]，但求和必须保留次数：output=sum(n_i*V_i)/S。去重读取不能把多次命中变成只加一次。候选局部索引还需共同的SparQ token映射和物理KV地址生成。

## 2. GPU的常规有放回采样

[PyTorch2.7.1 CUDA源码](https://github.com/pytorch/pytorch/blob/v2.7.1/aten/src/ATen/native/cuda/MultinomialKernel.cu#L390-L450)的有放回多样本路径包含归一化、前缀和、Philox随机数及CDF二分查找，直接写索引。可用`torch.multinomial(p,S,replacement=True)`表达此任务；默认参数不是有放回，不能漏写。这里只说明锁定版本的多样本路径，不声称所有GPU采样API或单样本路径都用同一算法。

数学参考：C_i=sum_{j<=i}p_j，每个样本取u~U[0,1)，输出最小满足C_i>u的i。CDF建一次、供S个样本共用，而不是每次重新做Softmax。N=128的理想平衡选择树为7层；并不等于GPU固定7拍，也不等于串行扫描128遍。实际CUDA有存储访问、分支和有限精度边界处理。

ASIC可用串行或并行前缀加法、CDF寄存器/SRAM、PRNG及选择树。还可对未归一权重w_i=exp(z_i-max(z))做前缀和W_i，取u*W_last与W_i比较，在数学上采到同一Softmax分布；因此优化基线不必物化每项归一概率或为每项另做一次除法。有限精度和数值质量仍须验证。

## 3. SANTA如何产生选择：systematic计数

[SANTA v2 §2.1及附录P算法5](https://arxiv.org/html/2605.01910v2#S2.SS1)已说明系统采样；官方代码也实现了它。单分布可用一个随机偏移和有序CDF网格，直接求各位置命中次数。分块实现使用每头、每tile的偏移，不是整个模型只有一个随机数。

为说明硬件意义，采用归一CDF的等价写法：r~U[0,1)，C_0=0，

    n_i = floor(S*C_i + r) - floor(S*C_{i-1} + r)
    read_i = (n_i > 0)

理想算术下sum(n_i)=S、E[n_i]=S*p_i。样本间相关，不能冒充S个IID样本，也不能继承Ising的混合或PPL结果。定点下floor可由取整数位实现，但前缀累加、缩放、溢出/舍入控制和发射仍要付费。

本次锁定官方仓库`OPUSLab/SANTA` commit `2e5f861196ec3d634d4b64729609fa7d687937b5`：

- [prop内核L771–805](https://github.com/OPUSLab/SANTA/blob/2e5f861196ec3d634d4b64729609fa7d687937b5/santa_fused_proportional_tile_budgets/santa_cuda_kernel.cu#L771-L805)：warp前缀scan、随机偏移后的floor差，保存整数次数。
- [L810–855](https://github.com/OPUSLab/SANTA/blob/2e5f861196ec3d634d4b64729609fa7d687937b5/santa_fused_proportional_tile_budgets/santa_cuda_kernel.cu#L810-L855)：按次数生成flag并压缩索引，再加载V，以次数参与累加。代码中存在`cf * V`，不能把论文名称“No-mulT”解释为CUDA完全没有乘法。
- [flash内核L72–85与L277–309](https://github.com/OPUSLab/SANTA/blob/2e5f861196ec3d634d4b64729609fa7d687937b5/flash_style_fused_santa_fixed_tile_budgets/santa_cuda_kernel.cu#L72-L85)：偏移由splitmix64派生，局部scan及floor差产生计数。这不是调用128个独立p-bit比较器。

上述源码证实采样被执行，但没有给出这一子模块的ASIC面积/功耗。已包含采样的SANTA整体kernel计时也不能再重复加一遍估算采样时间。

## 4. 纳入本项目的公平比较

三条路径共享同一SparQ候选集合、相同QK输入、候选→token映射及可比较的V读/累计接口：

| 路线 | 从分数到选择结果需要计入的模块 | 随机需求特征 |
|---|---|---|
| 数字权重＋IID categorical | max/exp、总质量/CDF、CDF存储、抽样选择、可选直方图/压缩 | 通常每个输出索引一个均匀随机值，不是每位置一个 |
| 数字权重＋systematic | max/exp、质量缩放、前缀累加、整数计数、非零发射/压缩 | 一个分布或tile一个偏移；样本相关 |
| 当前Ising赢家保持 | 定点/参考max/差值、LUT、阈值保持、随机驱动/预存生成、比较、反馈/公平仲裁、输出及必要计数 | 每轮候选bit向量和公平选择；必须计有效样本数/混合 |

另保留准确数字Softmax＋完整PV作为任务质量/整条Attention对照，它没有采样阶段。

硬件测量终点分两级：先到候选索引/命中次数ready，再到相同GQA/KV布局下的最终输出。不能一边只算概率，另一边算到V地址；也不能强制数字路线生成one-hot或复制128套PRNG来人为增加成本。Systematic可以直接发射非零次数，不必先产生S个索引再写一次直方图。是否需要全部计数存储、如何与V读流水重叠，取决于统一的下游合同。

N=128、S=128时，数字CDF一次准备128项，IID再生成128个随机值并选择；systematic则一次扫过128项得到计数。Ising的128/160轮候选更新不能与数字的128项scan按“各一拍”直接等价。以上是操作结构，不是新周期/面积/能耗测量。先比较同S只是诊断，最终还需匹配数值误差/PPL和实际唯一V读量。

## 5. 现有结果的准确状态

本项目旧P0/P2并非完全漏掉采样：`core.py:93`用CDF与systematic偏移生成索引，`schedule.py:101–119`已计`CDF_scan`、`systematic_counts`和`histogram_RMW`等。近期普通Softmax文献PPA只覆盖Softmax核；缺口是后续采样及融合接口的同工艺电路PPA，不能拿旧宏动作预算冒充实测。

旧调度的概率写回、直方图和分阶段安排是保留的历史实现，不作为新优化数字基线的强制成本。后续数字端应至少包括CDF/IID与systematic两种实现，并允许合法融合、端口共享和流水；先明确输入精度/随机精度/吞吐/输出回压，再测同约束RTL。此次没有修改封存结果、启动EDA或改写质量默认值，也没有得出Ising已经获胜的结论。

来源定位与本地审计范围见同目录`DIGITAL_SAMPLING_SOURCES_20261029.json`。模型、训练/测试语料与种子SHA不适用：本次为源码/文献和边界审计，没有模型实验。
