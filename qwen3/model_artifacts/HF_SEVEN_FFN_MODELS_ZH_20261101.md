# 七组Qwen3-4B随机FFN训练模型：已核对的恢复入口

**2026-11-01通过用户已登录的内置浏览器，确认私有仓库及七组部署目录存在。** 先前匿名HTTP401/未登录404是历史访问记录，已不再阻塞本次目录与交接核对。本次未下载37.49GB权重，也未重新执行模型加载或PPL。

## 模型从哪里找

- 仓库：`CyberPrometheus/p-computing4llm-models`，类型`model`，**私有，需有读取权限的HF账号**。
- 分支：`xuhaoyuan02-qwen3-4b-seven-20261031`；不要默认取main。
- 已核对固定提交：`fa0a9e4a7ad394ffb60e8175cb0d1e34dff93caf`。
- [用户提供的分支入口](https://huggingface.co/CyberPrometheus/p-computing4llm-models/tree/xuhaoyuan02-qwen3-4b-seven-20261031)
- [固定版本的本批交付根目录](https://huggingface.co/CyberPrometheus/p-computing4llm-models/tree/fa0a9e4a7ad394ffb60e8175cb0d1e34dff93caf/submissions/20261031T115253Z-xhy12309-seven-case-weights)
- 相对根目录：`submissions/20261031T115253Z-xhy12309-seven-case-weights/`。

本提交API元数据列出276个文件，合计**37,494,721,776字节**（约37.495GB，按文件逻辑大小相加，不等同本地缓存/后端去重占用）。本批模型在`models/`，有`HANDOFF.md`、`manifest.json`、`tests/transfer_checks.json`及`configs/code_reference.json`。

| 实验 | 实际模型子目录 | 权重位宽 | 权重尺度 | T | 文件数 | 目录逻辑字节数 |
|---|---|---:|---|---:|---:|---:|
| B0 | `models/b0/` | 8 | tile64冻结PoT | 32 | 38 | 5,356,363,514 |
| W6 | `models/w6/` | 6 | tile64冻结PoT | 32 | 38 | 4,683,964,165 |
| W10 | `models/w10/` | 10 | tile64冻结PoT | 32 | 38 | 6,028,762,888 |
| S1 | `models/s1/` | 8 | 全FFN共享冻结PoT | 32 | 38 | 5,356,363,534 |
| S3 | `models/s3/` | 8 | Wg/Wu/Wd三角色冻结PoT | 32 | 38 | 5,356,365,846 |
| T16 | `models/t16/` | 8 | tile64冻结PoT | 16 | 38 | 5,356,363,522 |
| T64 | `models/t64/` | 8 | tile64冻结PoT | 64 | 38 | 5,356,363,523 |

每组38文件由**36个`ffn_XX.pt`＋`non_ffn.pt`＋`export_complete.json`**组成。位宽/尺度/T已对照PR200计划和本批HANDOFF；实际文件名、大小、Git blob/LFS元数据来自固定提交的已登录API页面。

## 代码、配置、分词器和报告在另一个库

本批`configs/code_reference.json`固定引用：

- 仓库：`CyberPrometheus/p-computing4LLM`，类型 **dataset**；注意与模型库名称和类型不同。
- 固定revision：`a7c029901637bab6caf5b79a9563697e8bbf77d6`。
- 交付目录：`submissions/20261031T115253Z-xhy12309-seven-case-code-results/`。
- [配套代码和报告固定入口](https://huggingface.co/datasets/CyberPrometheus/p-computing4LLM/tree/a7c029901637bab6caf5b79a9563697e8bbf77d6/submissions/20261031T115253Z-xhy12309-seven-case-code-results)
- 代码引用记录的源manifest SHA-256：`eb23a172efbd18e3e56060a6b10d2bfcde33fc7a014c5b10949038921ffb9076`。

此dataset位置和SHA已从模型库中的引用文件读到；本次没有进一步遍历该dataset或独立重算其文件SHA。原模型为后训练版`Qwen/Qwen3-4B`，revision `1cfa9a7208912126459214e8b04321603b3df60c`。

## 怎样恢复，避免加载错权重

**这是自定义部署格式，不是adapter，也不是普通的Transformers/safetensors目录。必须加载同一组的FFN和`non_ffn.pt`：训练更新全模型，不能用原BF16模型的其他权重随意替代该组非FFN状态。**

交接说明要求从上述固定dataset交付目录取得代码，先运行`src/restore_sources.py`恢复`seven_runtime_v9_resource8`，再用`src/load_seven_deployment.py`；原先实际执行的重载规则在`src/final_deployment_eval_v1.py`。metadata/config和tokenizer位于配套交付的`configs/model_metadata`，交接说明称无需再下载原始父模型权重。恢复时先按manifest核对来源和SHA。

```sh
python src/load_seven_deployment.py --code-submission /path/to/code-submission --runtime /path/to/restored-runtime --model-submission /path/to/20261031T115253Z-xhy12309-seven-case-weights --case t64 --device cuda --seed 101
```

命令转述自本批HANDOFF，路径需要按实际下载位置填写；本次未运行。交付方注明新helper只做过语法检查，尚未用该新helper跑完整4B推理；原环境的36层导出重载/完整WT2验证属于既有执行记录，不能冒充本机复测。预期检查有限logits与`covered_ffn_layers=36`，不预填next_token。

## 本次核验边界与后续入口

- 已核对：私有属性、准确分支及提交、七个实际目录、每组文件数/FFN分片数/字节数、非FFN文件的Hub LFS SHA和导出清单Git blob、HANDOFF及配套代码引用。
- 尚未做：下载全部模型后重算SHA-256、逐文件比较上传manifest、实际加载张量/运行helper、新PPL或训练验证。Git/LFS元数据存在不等于本次已经重读37.49GB文件。
- 交付方状态仍为`submitted`、管理员`review_result=pending`，不改写成已验收accepted。
- 机器索引：[HF_SEVEN_FFN_MODELS_INDEX_20261101.json](HF_SEVEN_FFN_MODELS_INDEX_20261101.json)。训练设计源为[Issue159](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/159)/[PR200](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/200)，本位置备注在PR229维护。

以后优先使用本页固定提交与目录；只下载需要的case，沿用项目共享存储，避免本地重复保存七套大权重。
