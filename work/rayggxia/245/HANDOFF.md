# Issue245：固定硬件跨模型初步预算

2026-11-06；负责人 rayggxia。Issue245；分支 task/245-cross-model-estimate；base main@8cd4fba009598184bce4f1c806f038299b011ea0。独立最小工作目录 C:/Users/86134/Documents/a_P_BIT/tmp/cross-model245-20261106。实际提交、PR和远端读取回执以 PUBLICATION.json 及 Issue 为准，尚无该文件时只表示本地完成。

## 已完成与范围

正式实现 architecture_tlm/model_scaling_20261106/：estimate.py、六项CPU合同检查、CALIBRATION/ESTIMATE/SUMMARY.json、模型身份 evidence/ 及 REPORT_ZH.md。按当前固定100MHz/2.5MiB/12核C20 T64/共享1024 FMA、8物理KV组、LPDDR-derived8533、B1/2K、SparQ r32/K128、赢家保持S64估算；含embedding及完整lm_head。面积已单次乘0.81，功率/能量/时间不随此系数缩放。

中央Llama-3.2-3B-Instruct约39.92ms/159.50mJ/3.995W；DeepSeek-LLM-7B-Chat约83.45ms/333.76mJ/3.999W；固定覆盖面积均67.541446mm²。外存4pJ/bit；另外提供6.6/8pJ及65/90%峰值效率敏感性。中央继承Qwen有效带宽，不能当作新模型已跑原生TLM。模型质量尚未验证，不能宣称相对数字整机节能比例。

Llama匿名HF原始config不可读，使用官方公开Meta SKU及精确总参数数核验架构；明确保存派生配置。准确模型revision、公开来源、配置SHA在 evidence/MODEL_IDENTITIES.json；DeepSeek/Qwen原始配置已固定revision。没有权重/tokenizer文件和训练/评测数据SHA，因为本次没有下载或执行它们；后续PPL必须补齐授权权重及匹配参考。

## 验证与证据

命令：`python -B architecture_tlm/model_scaling_20261106/estimate.py`；`python -B -m unittest architecture_tlm.model_scaling_20261106.test_estimate -v`。六项全部通过；原Qwen三seed封存的16个能量分项、字节、时间和面积重建一致，这是对账检查，不是新预测精度验证。SOURCE_MANIFEST.json列12份正式文件原字节SHA-256及长度，CALIBRATION.json绑定已有封存和价格来源。根 architecture_tlm/model_scaling_20261106/ 为逐字阅读镜像。

无新RTL/PT/PPA、GPU/PPL、训练或原生Slurm任务；不改变Issue236健康任务、既有代码/默认值，不登记虚构电路run。未复制原始模型/大事务/网表/库。部分价格仍有C20 PT窗口/idle代理等历史边界，报告已保留；67.5mm²不是完整die，4W不是实测整板。

## 完整TLM下一步（本轮未执行）

1. 参数化现有构造器和owner adapter的Qwen硬编码。Llama为24Q/8KV，3Q每KV；DeepSeek为32Q/32KV，1Q每KV，复用8物理KV组分4波，不复制32组硬件。
2. DeepSeek尺度元数据需33024B/层而旧固定32768B；重排旧g/u offset=20000，避免与权重尺度重叠。FFN所有tile边界核验，不静默截断。
3. DeepSeek全norm驻留会造成192个bank超深度。初估提出32KiB逐层双缓冲并已收费约0.50MB额外读取；原生模型要落实预取、仲裁和生命周期。Llama原分区容量通过。容量通过不等于端口时序通过。
4. 单层先检查容量、动作/字节和有限物理头复用，再做完整28/30层EDA CPU任务。不要在未改硬编码前直接变model名提交。
5. 新模型捕获真实候选/赢家保持/唯一V轨迹和x/g/u/S12-gap-P8分布，建立匹配PPL参考；现有均匀V占用、Qwen调度效率和局部重装比例均只是显式代理。

## 发布与待同步

通过独立任务分支和PR交付；PR待审不等于已合并，Issue保持open。Projects连接器无更新接口，待有权限维护者同步；不因此省略Issue/PR/STATUS。保持原始估算及负面检查，不覆盖其他成员的STATUS或Issue28并发备忘录内容。

实际发布：PR247 ready/open待审、未合并；主体1335f69da2a3d014773adecb685ba6bdcfd37400，20文件远端逐内容一致。6项CPU通过；长期备忘录根/Issue28阅读镜像已更新同字节，未混入发布其他任务的备忘录改动。精确回执见PUBLICATION.json。
