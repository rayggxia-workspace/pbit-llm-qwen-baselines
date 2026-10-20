# Apple 7B 配对模型：完整六任务与 WikiText-2

原始 FP32 权重与 FP32 计算，TF32 关闭；harness 0.4.8，0-shot，seed 0。
GPU Slurm2542 于北京时间2026-10-19 21:55:48完成，归档终态为COMPLETED/0:0；CPU收尾2543验证每模型19,965题、六项逐题样本行数及SHA，无缺失项。

| 任务 | 题数 | Softmax raw acc | Sigmoid raw acc | Sigmoid−Softmax（百分点） |
|---|---:|---:|---:|---:|
| BoolQ | 3270 | 71.6208% | 76.3609% | +4.7401 |
| PIQA | 1838 | 75.5713% | 76.4962% | +0.9249 |
| HellaSwag | 10042 | 53.3061% | 53.6547% | +0.3485 |
| WinoGrande | 1267 | 69.3765% | 68.6661% | -0.7103 |
| ARC-Easy | 2376 | 72.1801% | 73.2323% | +1.0522 |
| ARC-Challenge | 1172 | 40.1024% | 40.5290% | +0.4266 |
| 六项算术均值 | 每模型19,965 | 63.6929% | 64.8232% | +1.1303 |

主表全部使用raw acc，未把HellaSwag/ARC等任务的acc_norm混进均值。两种口径、每项标准误差、完整题数、提示模板和种子均保存在float32/<model>/<task>.json及PAIRED_TASKS.json；单项标准误差不是两模型训练种子间的置信区间。

| 补充长度归一化指标 | Softmax acc_norm | Sigmoid acc_norm |
|---|---:|---:|
| PIQA | 77.0403% | 77.4211% |
| HellaSwag | 71.4897% | 71.6292% |
| ARC-Easy | 68.7710% | 69.6970% |
| ARC-Challenge | 41.8942% | 42.7474% |

| 完整WT2，window2048/stride1024 | PPL | 计分token |
|---|---:|---:|
| Softmax | 5.911825276082767 | 317546 |
| Sigmoid | 5.88607319951146 | 317546 |

本组Sigmoid在六项中的五项raw acc较高，WinoGrande较低；六项均值高1.1303个百分点，PPL低约0.436%。这些是两个分别预训练的官方配对检查点的结果，不是同一权重运行时改激活的因果实验，也未验证有限p-bit采样或硬件收益。

核验：16份正式小型JSON逐字节匹配CPU收尾SHA索引；两模型六项配置/模板/版本/种子/题数一致，逐项成绩与summary一致，均值及PPL重算通过；9份本地核心源码与服务器run-v6的SHA一致。大逐题JSONL留本人服务器，finalizer已核对其行数并记录SHA。final_artifact_manifest.json共69项，含完整结果与冻结源码；其SHA由finalization_status.json锚定。服务器根/home/Weican_Chen/projects/apple-sigmoid-7b-eval-20261019，正式原件在reports/float32/{softmax,sigmoid}/。不上传权重、数据、环境或逐题题干。

BF16 GPU2538/2539未通过数值门禁，2540诊断保留；本报告只给原始FP32参考。原生CPU/GPU短前向、因果及padding门禁已通过；完整评估为无KV缓存的全前向，不把缓存一致性列为已测。stderr的not-a-git-repository来自harness可选版本查询；代码版本由Git提交与冻结源码SHA独立定位。

任务集合依据DS-CIM表II；本次冻结harness0.4.8/0-shot，不宣称严格复现DS-CIM的LLaMA表格。PR67交付，是否已上传/待审/合并以work/amlink1219/65/PUBLICATION.json和远端PR实时状态为准。Projects权限不足时单独列待同步。
