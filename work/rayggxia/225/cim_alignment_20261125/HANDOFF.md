# Issue225：TLM／RTL对齐完善交接

2026-11-25；负责人rayggxia；复用 `task/225-cim-bank32-20261124`、PR266，base main206bf81f18ea。独立工作目录 `C:/Users/86134/Documents/a_P_BIT/tmp/cim-bank32-tlm-issue225-20261124`。启动已核对远端README/AGENTS、Issue225、PR266与本人STATUS，目标仓库为rayggxia-workspace/pbit-llm-qwen-baselines，登录rayggxia；未接管其他RTL任务。

用户要求按TLM_RTL_ALIGNMENT_REVIEW_20261125完善模型。输入原件同字节保存在本目录INPUT_REVIEW.md，SHA d3fd3f9029859e0068cf928e399acafce3cb6848f7244b62656e1b0fbafe2920。

正式代码仍在 `architecture_tlm/process_28nm/cim_bank32_20261124/`，不另开一个独立TLM。新入口是ALIGNMENT_CONTRACT.json；报告ALIGNMENT_REPORT_ZH_20261125.md；数据布局/时序表RTL_CONTRACT_ZH_20261125.md；汇总ALIGNMENT_RESULTS_20261125.json，恢复索引ALIGNMENT_INDEX_20261125.json。历史RESULTS.json/SOURCE_INDEX.json和11月24日归档不改写。

已做：显式每核双结果槽与捕获事件、四拍32项状态接口、结果/状态释放分开、当前4ns时钟入口、缓存生命周期与16B读写核对、共享DMA元数据容量和目标阻塞测试、逻辑tile随机状态提供接口及实际RTL转移的GF(2)跳步参考。核价格已包含结果FIFO/输入缓存/本地随机源，未重复加面积能量。

实际验证：8个unit通过；父BeatSRAM 32拍/128ns完整8KiB写入通过；六个封存trace场景和五份错误轨迹拒绝通过；同后端完整首层回放完成，队列/owner/信用/工作量/SEAL检查闭合。核心默认五核、250MHz、16/32采样，SRAM616KiB，总面积代理6.776269mm²不变。首层1.106372→1.106300ms、片上0.342181→0.342178mJ。不是新完整token/PPL/RTL验收或新Ramulator原生结果。详见JSON与报告。

运行命令：COMMANDS.json给出共同参数和七个case的实际选项，所有输出为本目录全新子目录；CHECK_LOG.json保存实际unit/BeatSRAM/回归stdout、stderr和退出码。run.py绑定冻结parent/snapshot/runtime/dependencies的SHA；执行源码原字节在executed_source内。最终只删actor.py末尾空白行，执行/交付SHA和AST一致性保存在SOURCE_CLOSURE.json，原manifest不重写。

没有运行中任务、没有新远端作业。一个首层回放已在本机CPU完成（约243秒墙钟）；不是在Slurm提交。未修改冻结runtime、已提交GPU实验或其他人的RTL。源归档与SHA见正式ALIGNMENT_INDEX；只归档小代码/结果/trace，不复制权重、库或运行环境。

后续动作：RTL对话按正式接口表实现五核调度、实体槽和共享DMA，导出同名事件；起始随机状态提供器目前为1拍/II1条件宏，需要真实实现/PPA差额；512B定制CIM bank仍为普通S0容量等效价格代理。64描述符当前峰值30，若未来超过64需补生产端等待而不能扩大为无界队列。完整36层原生回放仍待独立执行，不将首层乘36当新TPOT。

发布：沿同一PR266增量交付，不合并。发布前远端头e29befa4272fd92e7e72a71d7ae6059a19447d44。本地Git与API提交历史不同但旧树一致，不直接native push。实际新提交、树及回读验证以PUBLICATION.json为准；尚未写入该回执时只表示本地完成。Projects待有权限的维护者同步。

## 已发布核验

source commit401d1db5715a1814d8e7e31aeceedd2c5f1e180b，tree5e5cd5755242aa3b661d7d8e61535ef7d6433354与本地25文件来源树一致；8个关键文件blob回读通过。PR266 ready/open，未合并。PUBLICATION.json保存回执，Projects仍待维护者同步。后续元数据提交不改变以上执行结果或源码身份。

本地根阅读镜像21文件逐SHA同步。PROJECT_MEMORY_ZH.md与Issue28规范编辑副本同字节追加本次记忆，SHA fc998bc7d8388c3909e76cb79a0c66968fa422b2c32fd50dadadb71a8d6fbb7b；本PR发布PROJECT_MEMORY_DELTA.md，未把规范备忘录的其他未发布历史混入。
