# 当前GU共享输入前端结果

K64/T64，100MHz、SS1.08V125℃；M16=8g+8u，M64=32g+32u。一套SNG64共享所有输出，对比每8列复制一套；所有复制端口收到同样x/门限，逐拍事件与结果相同。后端均为固定sign+mag7权重、64路归约和20位/输出累计，无OR缩位。

- [实测功耗面积与比较](results/REPORT_ZH.md)
- [三seed小型摘要及分项](results/SUMMARY_SMALL.json)
- [准确执行源、原始包及SHA](results/SOURCE_INDEX.json)
- [小型源码ZIP](results/SOURCE_CODE.zip)：含完整RTL/流程及独立36文件激励重建脚本。

4配置、RTL/门级各12960逐拍PASS，48PT窗口。首valid640ns，完整服务/计价660ns；55等效面积raw单次乘0.81。前布局/原生STA与功耗模型告警保留。

外部x/W SRAM与保持、实际随机源及上游分发、跨K对齐/宽累加、g/u出口量化、BF16、CTS/SDF/SPEF均在外。源/事件跨输出波次的重播由外部负责，不从同一输入幅值推断独立物理源数。复制对照表示分立8列核；若原整机已合并SNG，则不能再记一次共享收益。没有新模型/PPL，不将本核活动能量当完整GU或整机成本。

统一run gu-shared-frontend-204-20261101。执行源是base3a0fa539加冻结未提交文件，以manifest/执行ZIP SHA为准；发布commit不是服务器执行commit。
