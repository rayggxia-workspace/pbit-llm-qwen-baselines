# 七组Qwen3-4B随机FFN训练模型：Hugging Face恢复入口

用户于2026-11-01告知七组模型已经上传。以后找这批模型，使用下面的**指定分支**；不要默认下载main。

- 仓库：`CyberPrometheus/p-computing4llm-models`
- 分支：`xuhaoyuan02-qwen3-4b-seven-20261031`
- [七组模型文件入口](https://huggingface.co/CyberPrometheus/p-computing4llm-models/tree/xuhaoyuan02-qwen3-4b-seven-20261031)
- 对应训练设计：[Issue159](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/159) / [PR200](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/200)，计划提交`477c5786b755b11938a7b7c0ed7993e1803a92b8`。
- 计划的原模型为后训练版`Qwen/Qwen3-4B`，revision `1cfa9a7208912126459214e8b04321603b3df60c`；不能与Qwen3-4B-Base或Qwen2.5旧模型混用。

## 七组标签如何对应

以下标签与配置已核对PR200的CASES.json。它们是寻找模型时的实验标识，**尚未核对为HF中的实际目录名**。

| 标识 | 权重位宽 | 权重尺度共享 | 目标采样T |
|---|---:|---|---:|
| B0 | 8 | 每64×64 tile独立冻结PoT | 32 |
| W6 | 6 | 每64×64 tile独立冻结PoT | 32 |
| W10 | 10 | 每64×64 tile独立冻结PoT | 32 |
| S1 | 8 | 全部FFN共一个冻结PoT尺度 | 32 |
| S3 | 8 | 按Wg/Wu/Wd三种投影角色共享冻结PoT尺度 | 32 |
| T16 | 8 | 每64×64 tile独立冻结PoT | 16 |
| T64 | 8 | 每64×64 tile独立冻结PoT | 64 |

按原计划，T同时控制输入矩阵采样及随机非线性采样；P8、x共享64、固定四档x/g/u表，三路AND事件直接进入Wd，无z重新编码、无OR分组，权重固定而非双随机。Attention保持原准确参考。上述是计划契约，不能代替检查上传权重实际使用的执行源码/配置。

## 本次检查到什么程度

**入口已记录；远端文件核验仍待访问权限或链接确认。** 用户说调整访问后已再次发起无缓存请求：

- 指定分支API：HTTP401，`Invalid username or password.`
- 同仓库根API：HTTP401。
- 同一环境公开对照`Qwen/Qwen3-4B`：HTTP200，revision与计划一致。
- 此前未登录浏览器打开指定分支显示404；权限调整后的浏览器会话不可用，未把旧404冒称新检查。

本机未检测到HF_TOKEN或默认HF token文件。本次不读取或发布凭据，也没有下载大权重、加载模型、执行训练或PPL。401无法区分私有/无权读取/仓库路径不匹配，**不据此断言模型未上传或文件不存在**。

机器索引见[HF_SEVEN_FFN_MODELS_INDEX.json](HF_SEVEN_FFN_MODELS_INDEX_20261101.json)：固定HF提交、实际子目录、模型/配置/分词器文件大小及SHA目前均为null，不能当作已验收制品。

## 恢复使用时补齐

1. 在有权限的HF账号下打开上述分支；核对恰好对应七组，另行区分BF16数字控制、训练resume状态与部署导出。
2. 先记下该分支当时的**完整HF commit SHA**，后续下载固定SHA而非可移动分支；把每组实际子目录和匹配的加载器/runner版本填入JSON。
3. 核对上传manifest与LFS SHA、文件大小；下载后对实际字节重算SHA-256。明确是完整checkpoint还是需要原模型的增量权重，不能先假定可直接用AutoModel加载。
4. 沿用执行方模型/语料/评测身份记录。聊天中收到的训练报告与本索引的访问检查分开，不把计划、用户回传成绩或训练方自验改写成本次独立模型验证。

此文件是共享制品位置备注；训练结果的正式验收继续Issue159原任务，不接管或重跑训练。无需为寻找入口复制七份大权重到本地。
