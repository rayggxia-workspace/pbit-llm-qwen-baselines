# Issue198：服务器DC/VCS/PT评估

2026-10-28用户授权。在现有任务分支测试8个固定控制top；不测试模型或其他整片设计。私有库由AC_TARGET_DB、AC_MODELS环境变量指定，登录工具和连接参数不放本目录。

本轮固定SS1.08V125°C、100MHz、输入slew0.1ns、输出负载0.02pF、setup uncertainty2ns、hold uncertainty0.1ns、core边界IO delay0。保留与先前准备脚本相同约束，不能放宽hold掩盖违例。长作业通过Slurm执行；每项单CPU/8GiB，矩阵最多2项并发。

先DC单顶层预检，再其余7top。VCS分别对RTL固定top与该次DC映射网表逐周期核对独立flat oracle；三seed压力轨迹与零/单/多/保持/rank cap、配置和输出等待。映射网表用配套厂商SVT模型、不反标SDF，不关闭timing checks或修改notifier。该逻辑验证不替代实际延迟后仿或STA。

PT读取同一网表、SDC和该网表门级VCD的显式窗口，使用averaged模式，报告活动覆盖、未标注、check_power、setup/hold和功率分项。零延迟活动未包含真实门延迟引发的全部毛刺；没有SPEF、CTS或布局。功耗算出而时序违例/标注告警必须同时保留。

原始面积保留；按用户确认的SHARK未缩几何口径，另列55nm折算面积=原值×0.81。不是按55/65比值重新推算，不将该系数用于功耗/能量/频率。完整RNG、概率比较/重编码、QK、V、存储、输出累加不在本控制边界内。

runner.py按SOURCE.json核验冻结执行文件；已提交snapshot不修改。prepare_vectors.py在本机生成输入/golden，端口回放不观察已被综合删除的debug统计。失败预检、修复版本、作业与结果SHA见work/rayggxia/198/EDA_*索引；准确结果以RESULTS.json/RESULTS_ZH.md为准，尚未生成不表示阶段完成。

本次首个DC失败暴露DC2018不接受coin_mask先引用后声明；仅调换两行声明，拒绝20项/90000拍复核通过。旧快照、旧仿真与库映射原件不改写。
