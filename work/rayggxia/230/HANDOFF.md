# Issue230交接：纯数字基线仿真清单

日期：2026-11-02。负责人：rayggxia。目标仓库rayggxia-workspace/pbit-llm-qwen-baselines。
分支task/230-digital-baseline-plan，PR base main；本地目录tmp/digital-baseline-plan-issue230-20261102。

## 已完成

- 用户要求的总文件：digital_circuit_simulation_registry/41_纯数字基线仿真清单_55nm_100MHz.md。
- 13份原有record引用均在本机中央台账读取并解析；准确SHA见SOURCE_INDEX.json。
- 对照main规则、Issue198/204/210/227和PR211，未接管其任务；区别完整数字Attention、筛选后准确PV和128候选P8核。
- 根a_P_BIT数字电路台账目录同步同名字节副本。本轮没有改写已有record或创建仿真run，因此不对旧台账执行无关render。
- 文档UTF-8 LF，无BOM；SHA与镜像一致。未做RTL、EDA、GPU、Slurm或模型推理。

## 版本与验证

远端main核验7d42c7d30fa9c729c899ba7f815332dd6ed5671a，实际GitHub登录rayggxia（324905371）。
本地准备base为已存787489192ebfcdb61ad72edde406818f450aa3dc：git fetch首次DNS失败，重试连接重置。远端提交按API基于核验main构造，仅交付总文件、本SOURCE_INDEX、HANDOFF和保留既有内容的本人STATUS，不上传其他任务本地历史/源码。

本机核查：13个record路径存在和JSON解析；文档UTF-8/LF；正式文件/阅读副本SHA相同。具体文档SHA与引用SHA在SOURCE_INDEX.json。主体提交6d137fdbcb2d79db416e084558ccc24dd0c59feb已发布，PR #231 ready/open、待审未合并；PR四个文件的blob SHA与本机一致，原STATUS只有新增、零删除。本地PUBLICATION.json保留实际回执，不将本地辅助回执存在写成远端也有该文件。

## 未完成与下一步

- 本清单中的新电路实现、STA/PT和完整数字TLM尚未执行，不存在新作业ID。
- 先做16路FMA反馈切片、单路完整数字SwiGLU及4路在线Softmax；W8控制补已有N64核的必要包装。
- 再按占比处理归一化/转换及局部供数。DDR/SRAM沿既有模型重新计数字轨迹，不写整片DRAM Verilog。
- 保留原始面积，并仅对本项目raw流程×0.81一次；功率/时延不缩放。
- PR审查/合并之后才关闭Issue；看板缺可用写接口，待维护者同步。
- 不用本清单启动重复任务，不覆盖#198/#204/#227健康作业。
