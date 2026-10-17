# Issue #14：Llama 2 7B BF16与当前TLM

负责人 @jieruiz；task/14-llama2-baseline-tlm；独立工作树tmp/llama2-7b-issue14-20261017。PR base为TLM分支07d03385a3b16b1f81a987c031f667c13876edf1，含已合并Llama1 PR13。

服务器个人项目 `/home/Hongjie_Zeng/projects/pbit-llama2-7b-20261017-issue14`。镜像下载、BF16基线与捕获最初快照baseline_9ee1ab47d031不可修改；作业1960/1961/1962。捕获源随后加上segment-start201979，需取消旧pending捕获并提交新快照，记录新ID；不改旧提交快照。基线1961仍是原样完整WT22K/4K、stride512、N-1目标唯一计分。

用户已明确允许镜像源。所有下载requests.Session.trust_env=False，不读取HF token或cookies；ModelScope源及官方SHA元数据在configs/MIRROR_SOURCE.json。权重/分词器/配置逐文件验证，model_identity.json最终保存源/revision/实际SHA和下载job/source。长轨迹、权重和原始事务日志留服务器，不上传Git。

真实QK捕获必须先运行原BF16，再运行观察钩子，输出逐bit相同；TLM入口强制REAL_LLAMA2身份及manifest匹配，禁止误用同形状Llama1轨迹。4K新增长度不当作旧Llama1原生能力。镜像config没有rope_theta时沿用官方默认10000。

已有验证：基线协议9tests、TLM结构/身份7tests；4K合成结构可运行但不是模型质量结论。还需实际下载、GPU PPL/capture、完整TLM与SHA核验。代码和结果只有本地/服务器，未宣称推送/合并。Projects仍缺read:project。

并行工作树baseline-code与tlm-code仅各自范围，通过cherry-pick61c0259、5b80767集成。后续继续前读Issue14、PR和本STATUS；提交时只stage新Llama2目录、个人work14/STATUS与必要索引。

更新：1962旧pending捕获已取消；正式1963已完成，512/1K/2K/4K均1024头且输出逐bit一致，前2K IDs匹配旧Llama1。下载1960的11文件官方匹配完成；基线1961运行，完整2K PPL4.9795028452，4K尚未结束。TLM1964 Link72、1965 Staggered36、1966 NoPD8已启动；数组并发上限24/8，实际受Slurm资源调度。执行源b5964b165dfead06676580029235bf5e952b5dad、57输入不可变，PPL源9ee1ab47d0317430212364e75adb78abec9797fb。PR #15已推送草稿，不自动合并。

BF16基线1961已全部完成，2K PPL4.979502845218782 / 4K4.895831220529201，13个原始成果文件含manifest字节已核验，正式存baselines/llama2_7b/results/bf16_wt2_20261017。Link72完成，DRAM36+8运行；最终后处理2069依赖1961/1964/1965/1966，report source358d8b8f943f60986f86362f7bc7aacfca531adc，输出reports/final_v1。未改执行57输入；报告修复数字/SC源hash键差异，通过11项检查并读取实际BF16与4个实际Link样本验证通过。
