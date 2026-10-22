# 第六轮PR审核与原始head集成（2026-10-22）

本轮审阅93/94/97，实际账号jieruiz，正式目标pbit-tlm-attention-details-20261016。93/97已原生合并；94因唯一负责人STATUS冲突，保持作者分支与原始head，通过本集成PR携带。全部实现和科学成果按原blob保留。

| PR | 原head | 交付方式 |
|---|---|---|
| [93](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/93) | e06f1bd05f2299d8dfba032d078eed31f943c262 | 原生merge129ae823ac1c3f1303c50400cf259d291279e447 |
| [97](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/97) | bec02df2d0afd7575dba59343f2829f342a32c9f | 原生merge27bf9c483e2b772b4fcdb4c988b3d86074c80049 |
| [94](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/94) | 424b4206874208c3ebb54ee84258ed3b112a17d9 | 本PR携带双亲合并2d3ec2e48ce713ff9c7febd8d7b22ca2391cc856；远端最终回执查Issue55 |

## 审核结论

93的32份唯一执行源、5份公开报告/冻结按Git原字节SHA通过，作者交付validator通过（13 AST/13相对链接/隐私/清单）。两台19CPU、6GPU synthetic、94包同字节freeze、27参数/3非持久buffer逐位相同及重载logits0.0等均有冻结记录。人工核对个人home/Slurm门禁、固定Torch底座校验、仅进程libgomp预载、离线wheel白名单与失败恢复。本人没有重新访问作者服务器、安装、申请GPU或取得13份私有原始报告，不能把作者报告检查叫本次新GPU验证。环境是2.6cu118，不能继承5090的2.7.1cu128真实模型质量/性能。

94的45CPU检查通过，含准确预算根的隐式梯度有限差分、256态边缘/真实两级采样、旧kind回归、文档隔离、blind文件门禁与篡改检测。本机为Python3.8/Torch2.4CPU，10项初测因Path.is_relative_to缺失报错；仅在运行器补等价路径API后45/45，无源码/测试修改。作者实际为Python3.12，故不改其声明环境。

准确核验134份包成员和90模型SHA；冻结早于评估启动、冻结选择与盲评选择一致，三个强max4均仅用VAL选出（层0硬阈值、层12温度0.03125、层23硬阈值）。15份预声明原始逐文档记录各48篇×3评估seed重新聚合，与90配置汇总/三训练seed均值一致，全部PV分母clamp为0。32MB完整冻结单、NPZ与长日志为作者私有索引，本轮未重新采集、训练或运行blind，不宣称已逐字节重新取得这些未发布原件。

训练目标/求根/隐式梯度、正确RoPE后BF16 QKV教师、因果/GQA、文档正文及截断token排除、TRAIN拟合标准化/偏置、强制首末块与可变mask均已沿执行源审阅。小网对原温度1有改善，对强max4为分层权衡；确定隐藏控制训练300而pbit6000，不能归因隐藏随机性优势。三个head/三个位置/三层局部结果不代表24层学生PPL，33–39% mask超512不能直接默认接现有宏。

94成本脚本完整重放，COST.json逐字节等原发布；9模型/2304隐藏态门控等价/6均值回算通过。每自由块32连续乘法/40加法/8bit门控/9概率节点事件、两阶段。三位置平均F21，新增672乘法多于当前候选QK约378/−165/379 MAC节省；还需归一化/驱动/随机服务。账本没有冒称PPA、9次节点事件没有冒称9串行时钟。

97的47CPU检查（19新+18旧采样器+10 v4）0跳过；3后端×3seed×900=8100沿独立重跑，每沿Python/RTL输出、握手、状态一致，操作账本和向量SHA与封存结果一致，FFN250沿/120帧通过。27源码blob/适配器SHA和用户便携ZIP（SHA7b067edb...）内26随机服务文件一致。人工核对启动外部种子、零种子拒绝、5拍/800步预热、排空响应后换种、锁定重放、每端点新种子包、回压保持、q/256端点、操作计费和原GF映射。

97只给通用数字核心与可选计时源。物理源/调理/CDC/共享仲裁器/LUT完整RTL不在本次；GF64总秩32、两两秩16不能推出64路联合IID，Attention默认拒绝其作为独立源。LUT量化改变目标，新后端不继承旧Softmax/PPL。未知能量/面积保持null；未执行DC/PT或器件测量。

## 如何合入及证据边界

93与94同时改负责人amlink1219 STATUS的开头，唯一内容冲突在该文件。本人分支以27bf9c48为第一父、94原head424b4206为第二父；直接采用作者94原blob9ee7dbdd，未手工改写其他成员状态文字。93原STATUS blob099017a6保留在原PR/129ae合并历史。作者任何分支未推送/重写；原94源和成果269个blob、93/97其余科学blob均精确相等，证明见evidence/ORIGINAL_BLOB_PROOF.json。AGENTS两条增量、双方备忘录历史均保留。

第一次哈希差异实际来自本机git archive/checkout按core.autocrlf转CRLF；不是远端PR损坏。此前已向用户纠正。正式核验改用git cat-file --batch并验证blob对象，原服务器CRLF档案继续原字节，作者内容不改。初次导出记录/运行器在本地审核归档保留。

本轮没有服务器写入、Slurm/GPU、真实模型推理/PPL、训练或综合功耗任务，也没有恢复旧定时。仓库实际admin/push可用，原生合并门禁checks/status为空，不能称CI执行。Projects沿原任务权限记录待同步，本轮没有改权限或宣称看板已完成。90/92/95均由原负责人接续，不自动关闭。

本报告为本次集成PR中的冻结快照；94远端合并、源PR状态与本轮目录回收等后续结果以Issue55最终回执为准。只保留一个稀疏审核目录，导出/仿真产物逐SHA本地归档后回收本人目录，不清理作者工作树、模型、唯一数据或共享Git对象。
