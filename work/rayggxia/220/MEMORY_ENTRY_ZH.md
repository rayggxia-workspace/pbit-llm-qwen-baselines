## 2026-10-31 Issue220：Attention十组训练交接

用户确定N族：无K筛选、赢家S128基线、赢家S64/S256、校正拒绝S128、传统稠密逐节点Gibbs S128；K族逐一复制并加SparQ r32/k128/local32，共10种概率方案。用户要求P8阈值与8位sigmoid输入，不采用此前建议的P12默认。方案建议内部signed12/F4分数→整数max/差值→非正U8/F4地址→冻结P8 LUT；不是signed8/F4绝对分数。P8小概率归零真实保留。

用户委托判断训练参数：首轮建议仅36层Q/K/V/O共943718400权重更新，其余算子准确且权重冻结，反向图不detach；固定BF16教师、CE+0.5KL、100M上限、seed0/部署101-103。两条准确数字控制分别无筛选/SparQ；不能直接继承前轮全模型BF16继续训练7.895811。训练准确前缀1792+概率后缀256，固定目标S，不套FFN预热课程，不共享已训前缀。

赢家burn32/spacing1；拒绝S个接受地址与实际尝试分开；传统N-1参考空态编码、kappa24、random-scan单节点，sweep-equivalent=N-1更新，N2048/S128含预热为327520单节点更新，不是160周期。允许oracle验证后的离散几何事件压缩，不允许旧CTMC替代。三类地址直接V累加，无第二次PV抽样。

正式方案qwen3/training/attention_ten_case_20261031，工作交接work/rayggxia/220；实际发布以PUBLICATION.json为准。此任务只交设计与数值表/校验器，未启动训练/GPU/Slurm/EDA，无新PPL/PPA；实际runner和数据/optimizer源配置仍待执行Agent接合，不把方案当已可直接训练代码。
