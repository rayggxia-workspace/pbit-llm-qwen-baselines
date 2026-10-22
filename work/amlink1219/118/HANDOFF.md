# Issue118交接

发布已完成：[PR120](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/120)，科学head `8bea1dfd1db24263a6daea5e6a29de641b23f03c`，48个远端文件Git对象一致；Issue118结果与清单已同步。PR未合并，Issue保留开放。Projects实测缺read:project，未写看板；本轮后续提交仅补回执和当前状态。

负责人amlink1219；分支`task/118-ffn-storage-contract`，base `pbit-tlm-attention-details-20261016@46804fb3a1c50b29a19a7d0a3da6bb8f8b59af7d`；独立本机目录`workspace_projects/sf23`。开发/审阅辅助目录`sf23-model`未用于别的任务，不触碰`cycle23*`的未提交内容。

本轮交付：`architecture_tlm/ffn_storage_contract/` 的供数模型、独立validator、A/B整数诊断、30功能测试、6项条件接口执行、4非法配置、完整小轨迹、源码/结果SHA；另有研究状态报告与EVIDENCE表。32KiB/T32保持/重读为6.92µs/3.2768ms；48KiB→5KiB只是8tile计数状态，非物理PPA改善。

实际执行源用`results/run_20261023/EXECUTION.json`逐文件SHA绑定；原始结果用MANIFEST绑定。源基线、远端任务、用户输入的只读索引位于本目录。独立审阅发现的宏最小周期门禁已修复后才封存结果。测试调用曾因工作目录/非包discover入口失败，修正为README中的包模块命令后30项通过；未放松检查。没有新GPU/Slurm/RTL/STA/模型PPL，运行任务ID不适用。

发布状态：以同目录`PUBLICATION.json`实际回执为准；结果先交任务分支PR，不自动合并/关闭Issue。所有科学文件随本任务上传；大trace未存Git/服务器，只保留可重生成配置、输入与规范JSON hash，小fixture完整保存。Projects与另一台机器的固定台账阅读镜像仅在实际有访问能力时同步，不能声称跨机镜像已更新。

下一步可执行：

1. 按README运行30测试，在**新的输出目录**重放runner；不要覆盖封存run。
2. Issue116选定适配接口后接入sample接受/源冻结、read issue/complete与权重状态占用，避免重复计入旧weight-consume/驻留代理。
3. Issue107实现/表征真实本地保持及signed-bin归约、计数读写、读出/清零；保持逐档FP32恢复顺序，新增RTL后登记新的run。
4. 有STA/PPA与同质量依据后，再做同面积/同资源搜索；当前两策略是合法合同示例，不是全局最优。

不接管Issue95/107/112/116；没有向其个人服务器提交或读取私有任务。新量化Attention质量另由冻结算法协议解决；旧25项完整联合WT2不重跑。
