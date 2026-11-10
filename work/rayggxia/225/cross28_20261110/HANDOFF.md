# 两模型28nm250 TLM：提交与恢复

2026-11-10，rayggxia；Issue225 / PR249接续28nm，交叉引用245/PR247的55nm模型形状与Fixture，不改其任务。当前工作目录tmp/tlm-unified250-issue225-20261107、分支task/225-tlm-unified250-20261107；没有复制新全量checkout。

用户问Qwen BF16为何等待：原提交--array=0-2%2自设限制，不是EDA仅允许两项。本目录cluster.py已核所属job/name/user后只改38650228的ArrayTaskThrottle=3，THROTTLE_UPDATE.json保留前后命令及回执；随后REMOTE_PREFLIGHT已确认Qwen三项均RUNNING。没有重启/重交/改冻结源码；不推断集群不存在其他QOS或资源约束。

## 已提交

北京时间2026-11-10 14:09:49，原生门禁数组38650669（下标0—7）和12个依赖门禁的完整CPU任务均已提交，准确列表SUBMISSION.json。每项独立CWD防止native统计覆盖；源包不可变，不原地修复。

|模型|概率SC三seed17/503/1009|BF16_dense|W8_dense|W8_screen|
|---|---|---|---|---|
|Llama-3.2-3B-Instruct|38650670 / 38650671 / 38650672|38650673|38650674|38650675|
|DeepSeek-LLM-7B-Chat|38650676 / 38650677 / 38650678|38650679|38650680|38650681|

门禁0—3对应Llama SC/BF16/W8dense/W8screen，4—7对应DeepSeek同顺序。每个完整case依赖对应afterok:38650669_<index>；不设置%2或其他人工完整并行上限，真实资源限制仍由Slurm决定。

门禁请求1CPU12GiB，完整1CPU24GiB；集群按粒度实际分配3CPU，上限4h/24h不是预计运行时长。无GPU、PPL、训练、额外RTL/PT。

远端根/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm28cross250_225_e0291ed6b5a9。包80354B，SHA227f2509a117c4673807074f23b303473dc8aea4065cc9fae905ea0db7ca83b1，manifest874c258f0b87631b386a8567977f43920cf598e77e3336fd96a08191d58dec72。旧runtime/dependencies/snapshot三manifest逐SHA核对，准确路径UPLOAD_PLAN和FROZEN_MANIFEST。

## 验证与边界

本地8构造均通过，包含完整词表/tail工作量。解析一层＋384head局部结果以LOCAL_GATES.json和VALIDATION.json为准，正在运行的局部检查不能写成通过。原生门禁/完整最新状态见STATUS，最初8门禁RUNNING、12完整依赖等待，并非完整评估完成。

正式代码architecture_tlm/process_28nm/cross_models_20261110/，MODELS绑定原configSHA/revision。真实形状、3/1Q每KV、DeepSeek4波KV、元数据>32KiB地址重排和独立embedding均已适配；同832KiB/178宏，不增加额外硬件。固定4Q issue中的无效头按完整FMA16片门控动作代理，仍计物理issue时间、固定状态/面积和idle；物理/有效量分开。结果是代表事务TLM，不是新文本质量或完整芯片PPA。

## 下一步

1. 通过已有EDA helper运行本目录ops.py status；不要再prepare/submit，不重交健康任务。
2. 各门禁通过后完整自动放行；失败则保留EXIT、log和冻结源，修复另冻新包且只补失败case。
3. 完整结果按status=completed/full、真实28/30层、全部词表、SEAL/源/配置SHA/逻辑KV数/物理与有效MAC/权重字节核对；分别列含/扣head的时间、能量、面积。
4. 与Qwen28nm结果及同芯片三数字基线比较；不把55nm旧表混入新结果。PR未合并、Projects待维护者同步；发布状态以PUBLICATION/RECEIPT_PUBLICATION为准。
