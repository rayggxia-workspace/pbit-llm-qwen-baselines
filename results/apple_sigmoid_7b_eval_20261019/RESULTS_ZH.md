# Apple 7B 配对模型：完整 WT2 结果

| 原始检查点，FP32参数/计算 | 完整WT2 PPL | 计分token |
|---|---:|---:|
| Softmax Attention | 5.911825276082767 | 317546 |
| Sigmoid Attention | 5.88607319951146 | 317546 |

两者完整语料token为317547，首token无前文不计分，其余每个target恰好一次；window2048/stride1024、同一原始文本和原SentencePiece及换行预处理。逐窗计分覆盖、NLL总和及PPL指数关系均已核对；精确文本/token/结果SHA见PAIRED_PPL.json与float32/<model>/ppl.json。Sigmoid的本组PPL比Softmax低约0.436%，属于这两个配对训练检查点在该协议的结果，不能推出所有模型的质量优势或p-bit硬件收益。

GPU作业2542仍在运行六项完整准确率；两模型各六项两题试跑已经通过，不能将它们当正式准确率。六项数据固定版本、19,965题/67,106请求的分词审计、原始FP32 CPU/GPU18-token对齐均通过，详见原始JSON。权重/原分词器下载2865对象、50.17GB的来源MD5与SHA索引、完整WT2文本SHA也已校验。

BF16 GPU2538/2539在预检处失败，未执行正式PPL/准确率；2540诊断未解决全部差异。当前表仅为官方原始未量化FP32权重/计算，BF16数值一致性仍待修复，不将FP32验证继承为BF16部署通过。FP32软件执行时间不是数字/P-bit硬件PPA数据。全部历史快照、失败状态和版本索引保留。

六任务集合来自Zotero DS-CIM表II：BoolQ、PIQA、HellaSwag、WinoGrande、ARC-e、ARC-c。本次明确使用harness0.4.8/0-shot，不声称重现该论文未固定所有模板细节的LLaMA数字。代码/结果已推任务Draft PR67，未合并；看板因缺read:project待同步。大权重、数据及逐题原始样本留本人服务器。
