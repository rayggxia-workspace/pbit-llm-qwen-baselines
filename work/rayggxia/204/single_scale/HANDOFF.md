# Issue204 单尺度INT8完成回执（2026-10-28）

负责人rayggxia，task/204-matrix-t32，PR205 open/ready/unmerged，base main@d83eeb1fc6b89a3dff51b5b62bf79acf665c7166，科学输入基线cc04dee9890ea6dcfbeee872b0cab914d3b1c2c6。本地目录tmp/matrix-t32-issue204-20261028。沿用原Issue/PR，不改旧四档冻结输入、其他任务或整机/模型默认。

用户决定：64路共用一个尺度、真正signed INT8[-128,127]、N64/T32；每幅值位平面和符号先OR4，64→16个事件，再做精确并行计数。实现3版：V1直接实现；V2把每组正负各6位改为一个signed7时间计数；V3使用专用无符号popcount并隔离末端恢复输入，保留signed7组计数。mode3每拍popcount16再时间累计；mode6每组独立累计后求和，二者同事件OR oracle全等。SC内部20位，数字22位，输出符号扩展32位。

全部完成：V1 672帧、V2 96帧、V3 288帧，共1056帧功能PASS；16个综合变体、96个active/idle PT窗口，SS1.08V125C100MHz。3原始执行包和22报告归档远端/本地SHA/大小及逐成员校验；Slurm全部COMPLETED/0:0，本任务无遗留作业。执行索引EXECUTION_INDEX.json，结果architecture_tlm/matrix_single_scale_20261028/results/FINAL_SUMMARY.json和REPORT_ZH.md；源包/报告在project_archives/matrix204_single_scale_20261028。不得重复昂贵测量或改写冻结输入。

M1：精确树179.906pJ、OR4-popcount16优化版101.932pJ（能量-43.34%、面积-16.51%），16路signed7独立时间累计优化版348.483pJ；数字位串行38.797pJ。M8优化OR4 790.767pJ/帧、数字位串行262.133pJ/帧，每帧8点积。还不能证明SC能效胜数字。共同尺度省去bin选择/移位，但新旧码域、刺激及位宽也改变，不能作纯尺度消融归因。

主PPA为16帧驻留权重、uniform signed INT8输入、公共R8，三seed均值；SC原始期望=数字点积/4。OR损失另报，时间计数硬件改动不改变OR结果；真实模型单尺度质量未验。面积raw×0.81保留双列，不缩放功耗/时间。外部权重存储/保持读口、RNG/比较器、输入量化/尺度选择、最终浮点恢复、物理广播线及CTS/SDF/SPEF在外，CE未冒称ICG。全部时序与功耗警告保留。

中央新run matrix-single-scale-204-20261028，增量union check/render并保留其他record；结果见REGISTRY_CHECK.json。源码/结果本地已完成，发布回执以PUBLICATION.json和最新PR205为准；发布前不写成已推送。Projects既有权限限制仍待维护者同步。下一步审阅计数实现、hold/功耗表告警；真实ICG、SRAM驻留端口及真实后训练模型同质量验证独立开展，不自动启动昂贵模型实验。
