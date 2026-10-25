# Issue184 常规比较器读出 / 2026-10-25

负责人rayggxia（本轮GitHub连接器实测）；Issue184，分支task/184-normal-readout，独立目录tmp/normal-readout-issue184-20261025。PR base pbit-tlm-attention-details-20261016@d6d33995754fcdcea99286e4ce43f91647aa231a。依赖Issue152，原任务/源码/STATUS只读，本轮不把该分支未发布的v2冒称已合并。

已完成：三seed各20000次理想/旧比较器逐位CSV/TXT导出到analog_pbit_20261016/ideal_and_old_20000_v1，11文件SHA核验。源码字节与统计见formal results/exported_20000及本目录export_existing_executed.py；未重新运行旧Spectre。

新源码architecture_tlm/physical_rng_normal_readout/src：24文件，manifest743bbec6b48ee440773623698c5de423d21756ad721edc4ee1411b7082d8ec82。10MOS无输出限流比较器，扫描SVT/LVT输入和10/20uA，原零外加C两MOS核心/TT25C/5fF。主输入级过驱动>=60mV、gm/Id<=22，其他模拟导通管>=30mV、gm/Id<=26，必须有饱和裕量。8项门禁/脚本测试、17模块Python3.6 AST、两Bash入口和27PDK哈希通过，实际Spectre尚未在本条记录时执行。

一个8CPU/16GB、6h+15min作业执行物理检查→确定性选型→3seed短精度→独立短校准冻结→新三seed各20ms有效、1us、20000原始位。fmin500Hz；不覆盖10Hz长漂移、阵列、锁存或熵。异常/失败停止下游并自动保留/打包。提交前查队列/目标目录，防止重复运行；不能修改已提交快照。后续实际回执追加在下方，不能把本地准备当作远端已运行。

复用本地既有p50_shared_speed_8core_v1中未实测的10MOS拓扑，新的几何/电流/反型区门禁不继承其预览结果。实际选中的工艺反型区和速度必须读OP与step，而非根据uA命名。动态功耗没有精确积分，OP DC功率不是全通道随机位能量。

实际执行回执：2026-10-25新Issue184由本轮已核实rayggxia负责，独立task/184-normal-readout@d6d33995，tmp/normal-readout-issue184-20261025，不接管152/jieruiz旧任务。已把38380128三seed各20000次1us理想/旧比较器逐位CSV及单列TXT导出到analog_pbit_20261016/ideal_and_old_20000_v1，11文件SHA通过；旧MID分别1089/1145/1115，全部保留。真实源原本接旧比较器，理想判决不是完全裸核心或实际数字读出，500Hz短记录不证明IID/慢漂移。新normal_readout_v1复用未实测10MOS无输出限流拓扑，1.2V、SVT/LVT输入、10/20uA，输入反型及饱和裕量实测门禁；源01d63b66aa5653dffb4d116e1b1d5f9c951b1571，manifest743bbec6b48ee440773623698c5de423d21756ad721edc4ee1411b7082d8ec82；24文件逐个SFTP上传，无新源码压缩包，8本地/8远端测试、17Python3.6 AST、Bash和27PDK哈希通过。实际Slurm38387635已RUNNING，m3ca1003，03:54:35Z观察；8CPU16GB、APS1最多8案例、6h+15m，snapshot normal-JMJc0ox0/source不可改。4候选中SVT20u尾管VDS-VDSAT=-12.6162mV拒绝，另3正常；确定性策略选LVT20u，输入overdrive189.9/193.3mV、gm/Id11.98/11.86；1mV连接核心阶跃最坏3.5ns、10mV1.5ns，采样分辨0.5ns；不等于独立随机位率。短精度、独立cal62003/9/17冻结及新val64007/13/33每条22ms总/20ms有效/1us/2万位仍待执行结果，numeric63003/17/29与cal/val分离，fmin500Hz，本轮不自动1s/10Hz长任务或精确能耗。结果根/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1/results/38387635，结束自动normal_readout_38387635.tar.gz/.sha256。台账新增派生索引（cases空、不算新实验）与真实新run，拒绝项保留。PR实际发布以work/rayggxia/184/PUBLICATION.json为准，不虚报合并。
