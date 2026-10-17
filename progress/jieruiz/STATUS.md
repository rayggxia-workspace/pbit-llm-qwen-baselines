# jieruiz 项目进度

## 当前任务：Llama 2 7B（Issue #14）

更新：2026-10-17（Asia/Shanghai），负责人 @jieruiz；正式仓库rayggxia-workspace/pbit-llm-qwen-baselines，实际GitHub登录已核验。

- 分支task/14-llama2-baseline-tlm，PR base pbit-tlm-attention-details-20261016 @07d03385a3b16b1f81a987c031f667c13876edf1；独立目录tmp/llama2-7b-issue14-20261017。
- 用户已明确授权直接使用镜像。ModelScope shakechen/Llama-2-7b-hf @e61a2c602c83286a3ffbadaa29c20ad1160a8c4e；权重分片与官方meta-llama @01c7f73d771dfac7d292323805ebc428287df4f9的LFS SHA匹配，小文件另核Git blob。不发送token或cookies。
- Slurm：下载1960完成，11文件与官方记录逐字节匹配；真实捕获1963四上下文逐bit一致，1962旧pending捕获已取消；基线1961完成，2K/4K完整PPL=4.9795028452/4.8958312205；Link1964全部72项完成，DRAM1965/1966运行中。
- 已完成本地基线9项协议测试及TLM7项契约检查；源代码已提交本地。4K支持与PV256已实现，旧Llama1和Qwen结果只读。
- 实际捕获验证已取回；116项真实轨迹TLM已提交并运行。下一步等待完整DRAMSys完成；报告作业2069依赖全部结果成功后自动汇总，再发布成果SHA；不能把合成结构检查作为真实Llama2结果。
- 本次代码已推送并建立PR #15（草稿，未合并），Issue #14同步；Projects缺read:project，看板待权限补齐。

## 已交付历史：LLaMA-1 7B（Issue #12）

更新时间：2026-10-17（Asia/Shanghai）；已核验GitHub实际登录 jieruiz。

| 项目 | 当前状态 |
|---|---|
| 当前任务 | [Issue #12](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/12)，LLaMA-1 7B 当前标准 TLM |
| 负责人 / 正式仓库 | @jieruiz；rayggxia-workspace/pbit-llm-qwen-baselines |
| 分支 / PR base | task/12-llama7b-tlm → pbit-tlm-attention-details-20261016 |
| Base | 9608c0d06cf8b421cbbd348aca4fc84c5990aae7 |
| 独立目录 | a_P_BIT/tmp/llama7b-tlm-issue12-20261017/ |
| 当前阶段 | 全部82项结果及代码已推送，用户已验收并授权合并；[PR #13](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/13) 为合并交付记录，最终合并状态及SHA见GitHub与Issue #12验收评论 |
| 执行源码 | 84c131951b9ce69a52778e8725d62a21ab9cc40f；不可变tlm_84c131951b9c快照 |
| 已完成 | 真实BF16捕获1877逐位一致；1878全部60项Link、1879全部18项Staggered、1896全部4项NoPowerDown完成；18项本地检查及82项后处理闭合通过 |
| 运行中 | 无本任务运行中作业；服务器未启用sacct，依据完整结果和squeue核查 |
| 成果位置 | architecture_tlm/llama7b/；服务器 /home/Hongjie_Zeng/projects/pbit-llama7b-tlm-20261017-issue12/ |
| 数值边界 | 单公开WT2窗口真实BF16 QK作为地址oracle；随机FFN/比例PV/新max4/Ising宏没有新PPL |
| 待同步 | 合并成功后在Issue #12记录实际merge SHA并关闭；Projects缺read:project，看板待权限补齐 |
| 下一步 | 本次用户授权合并交付，参见work/jieruiz/12/MERGE_ACCEPTANCE.md；后续新架构或PPL任务使用新Issue/分支/快照，不重复提交旧作业 |

此前治理#1/PR#2、架构审计#3/PR#4、DRAM#5/PR#6、FFN#7/PR#8及#11、筛选K流量#9/PR#10仍为各自独立待审分支。本任务没有覆盖其工作树。
