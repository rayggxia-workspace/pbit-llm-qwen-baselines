# Qwen3-4B 非Base替换（Issue158）

用户2026-10-23明确改用`Qwen/Qwen3-4B`。固定官方revision `1cfa9a7208912126459214e8b04321603b3df60c`，4,022,468,096参数BF16。来源[官方模型页](https://huggingface.co/Qwen/Qwen3-4B)、[固定config](https://huggingface.co/Qwen/Qwen3-4B/blob/1cfa9a7208912126459214e8b04321603b3df60c/config.json)。不替换成Base、FP8或2507另一个模型。

结构与原4B适配一致：36层、hidden2560、FFN9728、Q32/KV8/head128，Q宽4096；QK-Norm→RoPE、GQA/cache/QKV/Wo保留。权重和聊天模板不同，必须重新下载/核验、建立新BF16、重新TRAIN校准，不能用Base数值代替。

## 范围与口径

只换4B权重，复用PR147的已验证概率代码，源码参考357db588/执行算法8c35145。FFN仍是动态B4幅度、W8固定64×64、A8共享64、T32/K32，gate/up共享x、z独立重编码；不悄悄换成另一个Issue150固定幅度实验。Attention为max4/64token/8块/强制首末2，TRAIN16拟合+16独立holdout/temp1；校正拒绝128接受，赢家1024更新/argmax/burn0/spacing1，ideal FP32 Philox，非物理RNG/PPA。FFN覆盖prefill/decode所有36层，Attention仅所有单token计分decode。

先原生BF16完整WT2 2048/1024，随后同源码同权重再跑并要求NLL完全一致。之后4096目标后缀：BF16一次，FFN-only、screen-exact+FFN、rejection128+FFN、winner1024+FFN各seed0/1/2，共13项。batch2、32×128，匹配cached BF16，不减完整WT2或Base PPL。只跑原文teacher-forced PPL，不加聊天模板、不生成思考链；模型支持thinking/non-thinking不代表本评测是聊天能力测试。

保持既有train/test原文SHA；token hash从新tokenizer独立生成、落入prepared manifest并与两次完整BF16和每个后缀核对。不假定它必等于Base的token hash。legacy args burn16/spacing4仍不被新kernel消费，真实winner burn0/spacing1。

## 部署与保护

本人ROOT限定`/home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-nonbase-20261023-issue158`；复用只读Issue136 venv，不安装/升级旧环境。新权重经hf-mirror，SHA/上游blob/LFS校验，网络阶段最多3次有限重试，数值/数据校验失败不重试。所有运行Slurm：CPU下载及tiny预检→afterok GPU（1卡/4CPU/48G/6h）执行门槛/完整BF16及13项。没有完整概率WT2、1.7B重做、模型训练、RTL/PPA或任务准确率。

baseline/evaluate.py、support.py和test_baseline.py与Issue136源码原字节相同，配置只指向新模型；prepare新增新token绑定，runner建立新基线后再精确重放。旧qwen3/stochastic和qwen3/baselines不改。`package.py`从提交Git对象打包，生成根与baseline子目录execution manifest，源码444只读；不在提交后补丁运行目录。

本地`python -m qwen3.posttrained.test_contract`仅静态/配置合同，不冒称GPU门槛已过。实际阶段、作业ID/源SHA/结果见work/jieruiz/158/HANDOFF.md和本人STATUS。对其他成员Issue157仅提供只读模型manifest/基线接口，不实现SparQ/不接管作业。
