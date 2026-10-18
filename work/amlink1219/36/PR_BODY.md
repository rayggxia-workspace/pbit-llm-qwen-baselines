完整Attention对照此前缺少明确精度、GQA复用、驻留容量和PPA证据边界，容易把占位TLM系数或Softmax局部结果当作端到端硬件比较。本变更新增BF16/FP32分块在线数字Attention参考与可执行解析账本，覆盖QKV/RoPE/KV追加/QK/Softmax/PV/Wo，并将PPL预算确立为质量验收口径。

本地10/10解析测试通过，512/2048/8192三点运行成功；独立审查确认工作量、GQA共享、两passSRAM流量和空缺PPA口径。2K结果为132120576MAC、24MiB KV读、84MiB投影权重读；16GB/s主路径搬运下界14.155776ms，非实际延迟。0.5316195528mm²及0.169958493mJ仅为SRAM局部项，完整面积/功率/能量/实际延迟均未完成。

没有新增模型PPL、RTL、综合、功率或服务器实验；原BF16 PPL11.652735仅为Issue35既有质量锚点。文献、宏表、配置、代码与结果SHA及接续步骤见work/amlink1219/36。PDF、PDK、权重和原始数据不上传。

Refs #36。当前文案是本地待发布草稿，PR尚未创建；不自动关闭Issue。依赖base：pbit-tlm-attention-details-20261016。
