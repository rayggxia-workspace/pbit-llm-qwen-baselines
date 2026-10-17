# Issue #14：Llama 2 7B BF16与当前TLM

负责人 @jieruiz；task/14-llama2-baseline-tlm；独立工作树tmp/llama2-7b-issue14-20261017。PR base为TLM分支07d03385a3b16b1f81a987c031f667c13876edf1，含已合并Llama1 PR13。

服务器个人项目 `/home/Hongjie_Zeng/projects/pbit-llama2-7b-20261017-issue14`。镜像下载、BF16基线与捕获最初快照baseline_9ee1ab47d031不可修改；作业1960/1961/1962。捕获源随后加上segment-start201979，需取消旧pending捕获并提交新快照，记录新ID；不改旧提交快照。基线1961仍是原样完整WT22K/4K、stride512、N-1目标唯一计分。

用户已明确允许镜像源。所有下载requests.Session.trust_env=False，不读取HF token或cookies；ModelScope源及官方SHA元数据在configs/MIRROR_SOURCE.json。权重/分词器/配置逐文件验证，model_identity.json最终保存源/revision/实际SHA和下载job/source。长轨迹、权重和原始事务日志留服务器，不上传Git。

真实QK捕获必须先运行原BF16，再运行观察钩子，输出逐bit相同；TLM入口强制REAL_LLAMA2身份及manifest匹配，禁止误用同形状Llama1轨迹。4K新增长度不当作旧Llama1原生能力。镜像config没有rope_theta时沿用官方默认10000。

已有验证：基线协议9tests、TLM结构/身份7tests；4K合成结构可运行但不是模型质量结论。还需实际下载、GPU PPL/capture、完整TLM与SHA核验。代码和结果只有本地/服务器，未宣称推送/合并。Projects仍缺read:project。

并行工作树baseline-code与tlm-code仅各自范围，通过cherry-pick61c0259、5b80767集成。后续继续前读Issue14、PR和本STATUS；提交时只stage新Llama2目录、个人work14/STATUS与必要索引。
