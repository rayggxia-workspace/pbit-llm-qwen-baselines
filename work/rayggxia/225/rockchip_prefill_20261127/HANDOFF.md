# RK3588短输入资源对齐

Issue225/PR266，rayggxia，task/225-cim-bank32-20261124；源5cf1208b452d215d83c3015d74d773064a581921。复用当前独立目录，不切分支、不接管其他训练/RTL。

用户要求按瑞芯微位宽和token对齐后重估P-CIM核数。正式入口architecture_tlm/process_28nm/prefill_core_sizing_20261127/ROCKCHIP_MATCH_ZH.md和rockchip_match.py。复算依赖同目录已封存AREA_REVIEW_INPUTS.json，结果ROCKCHIP_MATCH_RESULTS.json/sha。

按RK3588公开MiniCPM3-4B/W8A8/128输入/64生成，TTFT1.40849s。使用MiniCPM3的62层及MLA真实投影，而非Qwen简单换名字。我们的28nm250M，GU16/Wd32，8个已测WS16整数阵列约.883TOPS、32向量、2state32、256KiB/256GBs状态、约1MiB激活/数字操作数工作区、每权重32输入复用；DRAM峰值33.792GBs、有效27，数字16行复用。4/5/6/8P-CIM核预算1.614/1.382/1.228/1.035s，8核状态阶段串行敏感值1.210s。5核临界，6核候选；20/30GBs时6核1.327/1.219s。

同预算16/32以外8/32、32/64、64/128最小条件核数4/10/18，不能把6核泛化到高采样。Qwen相同协议另表，不能对异模型算加速比。普通工作区/状态不是沿用decode576KiB，也不宣称已得最小SRAM或完整面积。CIM计算逻辑仍用19bit参考价，新21bit尚未标定。

已运行形状/独立MAC/分项和/容量/单调灵敏度与最小两文件快照复算。没有新权重或数据、GPU/EDA/完整prefill事务仿真。输入计数及主要矩阵位宽对齐；官方未披露的checkpoint/文本/板型/各算子数制没有补造。MiniCPM16/32的PPL未测，因此候选不改变decode/训练/RTL默认。

下一步：选择6核小形状prefill回放，明确32行复用、分期工作区、有限DMA、跨块状态读写；若用于论文加速倍数，补同checkpoint和同输入的RK3588实测及MiniCPM概率质量。原2048预算及PPA/质量数据不重跑、不覆盖。PR待审，Issue225广义工作不关闭，Projects未操作。最终推送以本地PUBLICATION.json为准；Issue28备忘录远端依原维护流程待同步。
