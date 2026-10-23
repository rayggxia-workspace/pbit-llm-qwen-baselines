# 发给权重持有者的20层 P-DNN 任务评测：依赖与协议审计

本记录仅做交接准备，不运行真实20层权重，不修改Issue145工作树、服务器或冻结收尾脚本。当前151本机专用runner依赖Weican_Chen路径及Issue145的参考原件，不能原封不动当作异地可执行入口。异地入口应单独实现可核实的个人路径和fresh BF16流程，不能伪造145参考目录或改写其冻结记录。

## 必须冻结的实验身份

- Qwen/Qwen2.5-0.5B **Base**，revision `060db6499f32faf8b98477b0a26969ef7d8b9987`。
- 原串联bipolar FullPath P-DNN v1，20层联合训练step1000；替换`[1,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22]`，保留`[0,2,3,23]`。
- 每层896→4864→896；入口和隐藏均为±1，原checkpoint浮点权重，执行BF16；每FFN平均4条完整随机路径。没有W8或随机Attention。
- 20份原始文件总697,875,430 bytes。逐文件大小、SHA、payload层号、类型、phase和step遵循`checkpoints.expected.json`与`SHA256SUMS.expected`。不要重新torch.save后冒称同一份原始文件。
- 3任务×3个P-DNN推理seed共9个完整候选case；异地另外运行3个匹配BF16基线，共12个完整case。smoke不计入正式任务准确率。

## 最小源码依赖闭包

沿用当前151入口及其import时，实际执行路径需要：

1. `experiments/pdnn20_task_accuracy_20261023/runner.py`及本目录配置/期望manifest。
2. `experiments/pdnn_task_accuracy_20261023/pdnn_score.py`：151版本，含固定20层拓扑检查。
3. `experiments/pdnn_task_accuracy_20261023/runner.py`：仅复用模型身份/加载、choice比较及独立BF16 cached oracle等函数；其原CLI固定Weican_Chen路径，不能作为portable CLI调用。
4. `experiments/pdnn_ffn/full_path_pdnn_ffn.py`：原采样算子。
5. `experiments/qwen_task_accuracy_20261019/task_data.py`：官方任务、tokenization及process_results入口，保持原样。

新的portable入口可以取代第1项的本机路径/参考数据流程，但须保留同一评分数学。若portable入口直接实现模型加载和独立BF16 oracle，第3项可从运行依赖中去掉；否则应打包原文件作为只读函数依赖。

本次固定serial/sigmoid输入编码，严格loader直接构造FullPathPBitFFN，不走continuous或multibit分支，因此执行路径不需要`continuous_input_ffn.py`、`multibit_input_ffn.py`或旧Attention依赖。不得把旧`cached_score.py`、`run_joint.py`的整棵随机Attention实现作为简化代用品。包中包含更宽的原源码目录可以，但不要说所有文件都是必需运行依赖。

测试至少携带`test_pdnn_score.py`（22项）及`test_preflight.py`（6项）。可携带原151 runner作参考；portable准备/路径/marker的新增行为仍需自己的实际入口检查。无须Apple模型、AXLearn、JAX、TensorStore、训练脚本、WT2或大模型缓存。

## 可获取的原始数据与精确身份

以下来源来自原下载manifest；本次又独立重算本地三份下载原件的长度与SHA，三项全部匹配。此核验不等于重新进行一次网络下载。

| 任务 | 官方数据仓库及固定revision | 源文件 | Bytes | SHA-256 |
|---|---|---|---:|---|
| PIQA validation | `ybisk/piqa@142c51238b3ca2bc61e9a075913871b8b600e8e1` | `plain_text/validation/0000.parquet` | 301200 | `40e1677bba609c8801deacc171d76f3e24c083f365c95a1cbda7520c923dfea2` |
| ARC-Easy test | `allenai/ai2_arc@210d026faf9955653af8916fad021475a3f00453` | `ARC-Easy/test-00000-of-00001.parquet` | 346257 | `4160597d618ae851c7eb04e281574f3f654776216ac6b6641588d64527b47177` |
| HellaSwag validation | `Rowan/hellaswag@218ec52e09a7e7462a5400043bb9a69a41d06b76` | `data/validation-00000-of-00001.parquet` | 6315951 | `899813071e1e95efafec90f856e1987d2150fa4d020fc005df6962c259f660cd` |

固定下载链接：

- [PIQA validation parquet](https://huggingface.co/datasets/ybisk/piqa/resolve/142c51238b3ca2bc61e9a075913871b8b600e8e1/plain_text/validation/0000.parquet)
- [ARC-Easy test parquet](https://huggingface.co/datasets/allenai/ai2_arc/resolve/210d026faf9955653af8916fad021475a3f00453/ARC-Easy/test-00000-of-00001.parquet)
- [HellaSwag validation parquet](https://huggingface.co/datasets/Rowan/hellaswag/resolve/218ec52e09a7e7462a5400043bb9a69a41d06b76/data/validation-00000-of-00001.parquet)

PIQA用的是官方`refs/convert/parquet`转换commit，不能误用其main `2e8ac2dffd59bac8c3c6714948f4c551a0848bb0`当作parquet文件revision。下载原字节后核SHA；不要经过`Dataset.to_parquet()`重新编码再要求上述原字节SHA。

每份文件可以在接收方独立个人目录映射为`data/<task>/0000.parquet`。PIQA使用完整1838题，ARC-Easy完整2376题，HellaSwag先从完整10042题按Python `Random(20261019).sample(range(10042),1000)`无放回抽样，再保留原文档顺序。不能替换成`--limit 1000`或前1000题。

选中doc_id列表的SHA（`json.dumps(ids,separators=(',',':')).encode()`）：

- PIQA：`4c9f51a5292e593fe5632b28f92c8405171a0102789840f42bd949b804e3a9ab`
- ARC-Easy：`922c84ada5637d14c1d1483cf8e15c828b0c6051da9be3d2543bc5ff53a26044`
- HellaSwag：`b3bedbdf96e593ddb07a08f71bb7bf5906b85af0953f798e87a517097b1abed0`

## 基模型与tokenizer

固定模型下载源为`https://huggingface.co/Qwen/Qwen2.5-0.5B/resolve/060db6499f32faf8b98477b0a26969ef7d8b9987/<filename>`。

| 文件 | Bytes | SHA-256 |
|---|---:|---|
| model.safetensors | 988097824 | `88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342` |
| config.json | 681 | `479dcf0c5286339e41ad3992cd08ae88a467c4187587936248e2b7c96283484b` |
| tokenizer.json | 7031645 | `c0382117ea329cdf097041132f6d735924b697924d6f6fc3945713e96ce87539` |
| tokenizer_config.json | 7228 | `c91efca15ceff6e9ee9424db58a6f59cd41294e550a86cbd07e3c1fb500b34f9` |
| vocab.json | 2776833 | `ca10d7e9fb3ed18575dd1e277a2579c16d108e32f27439684afa0e10b1440910` |
| merges.txt | 1671839 | `599bab54075088774b1733fde865d5bd747cbcc7a547c5bc12610e874e26f5e3` |
| generation_config.json | 138 | `8c970692323e3ea0e9b8b0a4dca79388d31226e41f83c9fd6014804280ebf6e8` |

这些模型/tokenizer pin来自原下载manifest，并与已执行145的TASK_DATA身份记录一致；本次没有重新下载或重哈希约1GB权重。portable包可携带小型下载/散列manifest，不必包含大权重。

## 环境版本与安装边界

实际145/151评测环境已记录：Python3.12.3，PyTorch2.7.1+cu128，CUDA运行时12.8，Transformers4.45.2，lm_eval0.4.8，datasets3.6.0，pyarrow19.0.1，numpy1.26.4。

原env-eval-v4安装脚本还明确约束：`peft==0.13.2`、`accelerate==1.0.1`、`huggingface-hub==0.35.3`、`safetensors==0.6.2`、`sentencepiece==0.2.0`。这些是安装来源约束，本次未重新查询所有传递依赖的实时版本。不要混用4090兼容环境的hub0.26.5/pyarrow17等版本并称为原环境；如需其它CUDA构建，登记新环境并运行fresh基线。

完整pip依赖闭包应在接收方隔离环境安装后保存`pip freeze`及关键lm_eval Python/YAML文件的SHA。本记录没有取得完整eval-freeze.txt，不能冒充完整可复装lock。原Apple安装里的zarr、numcodecs以及native AXLearn依赖对本任务非必需。

安装、缓存、数据、checkpoint、输出均放接收方经核实的个人目录，不沿用发送方账号绝对路径。共享服务器只通过已核实的scheduler/allocation计算，CPU步骤隐藏CUDA；不伪造Slurm环境变量绕过门禁。下载/依赖准备宜为CPU allocation，模型推理为GPU allocation。

## fresh BF16与145的可比性

BF16处于eval模式且没有抽样FFN，三个推理seed没有新增的采样不确定性，因此每任务运行一次完整BF16即可。真实GPU smoke应验证重复评分和独立每选项重新prefill的cached oracle；若BF16重放不稳定，应诊断算子/环境，不以三seed平均掩盖问题。

20层P-DNN必须运行seed0/1/2。seed为推理随机种子，不是三个训练初始化；报告均值与样本标准差，并分别与同机fresh BF16做百分点差，不跨任务取简单平均。

原145的BF16参考acc/acc_norm：PIQA70.511425%/69.967356%，ARC-Easy64.393939%/58.333333%，Hella1000为41.9%/52.4%。这些是来源参考，不能当作异地已复现的结果。换GPU、CUDA构建或依赖后，须保留新匹配BF16及逐题输出；如有差异应报告、定位，不能把原数字抄成当地基线。

## 交接agent必须先读的清单

交接包应有明确的单一portable入口说明，而不是要求agent自行猜改151本机脚本。执行前阅读顺序建议为：

1. 包内的任务说明/AGENTS：用户授权范围、20层身份、目录归属、调度与暂停边界、结果回传要求。
2. 任务协议：Base/0-shot/三个任务及准确范围、N4、三seed、BF16新基线及评分方式。
3. `checkpoints.expected.json`、`SHA256SUMS.expected`与配置：20份原文件逐SHA/payload核对。
4. 模型/数据来源及path-independent reference manifest：固定commit、原字节SHA、官方Harness/YAML及tokenized请求pin。
5. `pdnn_score.py`、`full_path_pdnn_ffn.py`及`task_data.py`：确认实际算子和官方计分入口。
6. portable runner及调度脚本：核实实际用户、canonical home、个人路径、allocation、缓存、CPU/GPU状态；绝不调用Weican专用旧CLI。
7. 22项评分测试、流程门禁及真实smoke的实际结果；尚未通过的真实GPU gate不可写成已通过。

## 不可省略的协议风险

- 官方0-shot模板、HellaSwag文本预处理和HFLM._encode_pair保持不变，不加chat template，不手写候选提示替代。
- acc用候选完整loglikelihood，acc_norm按官方候选字符串字符长度归一；不按token数、不自由生成、不投票、不跨seed选最好分数。
- 匹配cached评分：prefill prompt[:-1]，最后一个prompt token单独q_len1预测首答案token；共享此logits，后续选项恢复KV和全局CPU/实际GPU RNG，逐token teacher forcing。
- batch16、精确prompt长度/候选数分组、无padding、候选label-free字典序、固定task/doc IDs。变化batch组成或20层拓扑会改变全局随机流；同seed不证明与2/4层共用实际draws。
- 学生仅替换指定FFN，在prefill/decode均生效；每次前向24个decoder/FFN的覆盖均须审计。连续读出后平均4条完整路径，不把N4改成均值场或hidden-only sampling。
- 基模型加载后只移动device，不对整个模型再次`.to(dtype=BF16)`而改变原RoPE buffer；学生权重BF16与原Attention SDPA精度保持约定。关闭TF32并记录环境。
- CPU缺权重/缺完整基线/inspect-only只产生等待记录，不产生GPU-ready。通过原件、strict state、真实BF16 oracle、20层重放和选项置换后，才运行9个正式P-DNN case。
- 保存每题ID、候选logprob/greedy/tokens、官方metrics、实时progress、配置/源/模型/数据/checkpoint SHA和Slurm终态。完成case校验后才跳过；partial禁止覆盖，另建run/tag。
- 旧20层PPL约48.91仅识别历史模型，不能推导任务准确率；CPU合成测试不等于真实20层GPU通过，GPU软件耗时也不等于硬件PPA。

## 本记录的证据来源

- 本机读取的pa20 Issue151 runner/config/expected manifests及145 scorer/task_data；未修改它们。
- 原数据download manifest：`outputs/apple_sigmoid_7b_eval_20261019_side/data-staging/dataset_manifest.json`；本次已重新核验三份parquet原字节。
- 原模型download manifest：`outputs/pdnn_sigmoid/review/model-download-manifest.json`。
- 145实际TASK_DATA：`outputs/pdnn_accuracy_20261023/attempt2/evidence/TASK_DATA.json`，只读使用，不触冻结helpers。
- 已记录核心环境：`outputs/pdnn_accuracy_20261023/environment_versions_and_data_sha.txt`。
- 原安装约束：`outputs/apple_sigmoid_7b_eval_20261019_side/setup_worker_v4.py`。
