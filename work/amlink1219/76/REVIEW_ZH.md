# 独立审阅及处理

两名子代理分别审核训练流程与筛选器数学。已处理：

1. 最新GitHub同时存在原始variable和固定8块评测，正式方案主路为variable；固定8块仅对照。
2. 强制块绕过网络并排除BCE，预算以强制块q_eff=1计算；预算batch保留完整query/head分组与有效块mask。
3. 短前缀平均目标在强制块数与有效块数之间，不要求每次精确8块。
4. V/O局部预适应在O之后比较输出，QK代理与实际V梯度分开。
5. tanh明确更新替换FFN三投影及alpha/gamma，其他参数冻结；CE/KL reduction明确。
6. 4M token仅约31个有效batch，明确为门禁，不作为收敛判定。

核对完整WT2正式SUMMARY的五个主数值，均按六位小数重现。Word正文及表格与Markdown逐块一致，已核ZIP完整性、链接与样式继承；没有作页面预览，遵从普通讨论文档检查口径。未执行模型训练、GPU作业、PPL、RTL或PPA。
