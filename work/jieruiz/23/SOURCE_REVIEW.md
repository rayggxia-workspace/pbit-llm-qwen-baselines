# Issue23 来源核对

日期：2026-10-18；负责人：jieruiz。正式阅读文件位于 architecture_tlm/PBIT_LLM_RECOMMENDED_READING_ZH_20261018.md。

- uGEMM：作者14页PDF；题名/ISCA2020、45nm DC综合、MNIST及uMUL路径与共享条件核对。
- SASCHA：作者12页PDF；CASES2022/TCAD特刊、GEO+完整二进制累加、Genus/CACTI及CNN验证核对。
- DS-CIM：arXiv2601.06724v1全文；双PRNG、SRR、CMR及宏/模型验证范围。既有Issue5成果只读。
- p-PIM：PubMed42814470、PMC13626169索引全文与Methods；真实器件时间复用+FPGA HIL，集成阵列为预测电路模型。没有集成64×64实测或LLM。
- SANTA：arXiv2605.01910v1；PV采样、prefill并集、GPU内核与模型质量分开。
- Z1T：Extropic官方说明及HF模型卡；工程发布而非同行评审论文，映射、重训与估算边界保留。
- VLSI2024 SCIM：UCLA作者2页PDF；实测芯片、6位SRAM权重、SNG/32MAC共享与事件/普通模式区别。
- SC-CNN：PMC7793640开放全文；2020扩展工作与原始DAC2017 BISC区分。
- Dither/P2LSG/tubGEMM：固定arXiv版本2102.10732v2/2309.05235v2/2412.17955v1；混合舍入、低差异与非随机unary分开。
- ICCAD2018：作者8页全文；低差异多维乘法来源。
- ASTRA：Colorado机构仓储7页作者PDF；GLSVLSI2025、确定性编码、光电归约和模型规模边界。
- Current digitizer：APS官方题录/摘要及MIT介绍核对。全文未取得，清单明确建议下载；未推断完整集成加速器PPA。
- FIGNA：用户已提供本地PDF及此前细读记录；本任务不新增数值比较。
- NeuPIMs：作者PDF及官方repo；两阶段分析、核心generation调度、ONNXim/DRAMsim3/Micron模型范围。
- LLMCompass：作者PDF及Princeton官方repo；映射/层级/校准，验证误差不外推至任意新ASIC。

所有正文引用均指向论文、作者、出版商、机构或项目官方资料。MANIFEST记录URL及既有本地材料字节SHA；不上传PDF、模型、数据、工艺库或凭据。网页内容可变，带arXiv版本的链接固定到所读版本；此任务未归档网页全文。

文档验证：UTF-8/LF、所有本地链接实际存在、用户副本与正式文件逐字节一致，SHA见MANIFEST。外链已按原文入口核对；不是对出版商长期可用性或任意网络环境访问权限的保证。
