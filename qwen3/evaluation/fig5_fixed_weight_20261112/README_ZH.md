# Fig.5(a)：固定 K_WH64 权重的完整 WT2 评测交接

本轮**不训练、不更换各配置权重**。使用同一份已训练的 K_WH64 Q/K/V/O 权重，保持原模型 FFN、归一化、embedding、lm_head 为原生 BF16，补齐候选预算 K 与采样次数 S 的 PPL 曲线。负责人 rayggxia，接续 Issue #198；执行人由用户安排。本文及同目录代码可独立用于远程 Linux/CUDA 环境，不需要作者本机路径或旧私有 runner。

## 1. 要回答的问题与任务矩阵

| 筛选 | S32 | S64 | S128 | S256 |
|---|---|---|---|---|
| SparQ K128 | seeds 0/1/2 | seeds 0/1/2 | seeds 0/1/2 | seeds 0/1/2 |
| SparQ K256 | seeds 0/1/2 | seeds 0/1/2 | seeds 0/1/2 | seeds 0/1/2 |
| 无 K 筛选 | seeds 0/1/2 | seeds 0/1/2 | seeds 0/1/2 | seeds 0/1/2 |

共 **12 配置 × 3 seed = 36 个完整 WT2 PPL**。无筛选用当前所有可见 token，最大窗口 2048；不是只从固定 128/256 个候选中抽样，也不运行粗 QK/TopK。每个得分查询都更新 S 次，不去重，不丢弃重复赢家。

另有 5 个控制，各跑一次即可：

| case ID | 权重与计算 | 用途 |
|---|---|---|
| `parent_bf16` | 未改动 Qwen3-4B，原生 BF16 SDPA | 重建环境和计分参考；必须先通过 |
| `overlay_bf16` | K_WH64 QKV/O + 原生 BF16 SDPA | 同权重原生准确 Attention |
| `exact_k128` | K_WH64 + 同 SparQ K128 + FP32 Softmax/加权 PV | 分离 K 筛选影响 |
| `exact_k256` | K_WH64 + 同 SparQ K256 + FP32 Softmax/加权 PV | 分离 K 筛选影响 |
| `exact_kall` | K_WH64 + 全可见 QK + FP32 Softmax/加权 PV | 同权重全上下文 FP32 数值参考 |

**共 41 项评测，不是 41 次训练。** 完整机器可并行独立 case；先控制、再 S64、再 S32/128/256。资源紧时可先每个配置 seed0，之后补齐 1/2；三种 K 不能只挑某一条完成，单 seed 不当作最终误差条。S16、S512/1024 为可选后续，不在本次 41 项执行清单内。

这轮不加入 FFN 近似、不重训 N_WH64/N_WH128/N_WH256、不改粗 QK 相加筛选、不比较不同训练权重。硬件 PPA 与 Fig.4 局部分布实验也不在本包运行范围。

## 2. 固定输入、算法与计分

- 权重来源、精确 HF revision 和文件 SHA：[ASSETS.json](ASSETS.json)、[权重说明](MODEL_AND_ALGORITHM_ZH.md)。K_WH64 是训练时 K256/S64 的同一份 overlay；部署 K128/K256/无筛选时均保持该文件。
- 新主前端：**FP32 QK → FP32 减最大值 → RNE U8/F4 地址 → floor-P8 sigmoid 阈值**。不能先把绝对分数量化成 signed12/signed8 再求最大值。
- GF64 候选随机字、独立 Bivium 公平仲裁，winner-hold，初始化候选位置 0，burn=0，spacing=1。无筛选用 11 位公平选秩字；K128/K256 保留 8 位。它是行为仿真，不宣称物理真随机或逐周期 RTL 一致。
- 完整 WT2 的具体原文、token SHA、窗口、标签位置和总 NLL 算法见 [WT2_PROTOCOL_ZH.md](WT2_PROTOCOL_ZH.md)。不要套聊天模板，也不要直接使用训练端默认 `evaluate_ppl`。

历史 K_WH64 GF64 的 K128/K256、S64 已有三 seed，但前端是 signed12 绝对分数先量化；旧父模型预算扫描又没有 K_WH64 overlay。这些不能冒充本轮“同权重、max-first”的点。本轮所有点从同一执行版本生成。历史证据与不可混用项见 [HISTORICAL_COVERAGE_ZH.md](HISTORICAL_COVERAGE_ZH.md)。

## 3. 环境与获取

从本 PR 分支检出同目录完整文件，并记录 `git rev-parse HEAD`。不要只下载 README。父分支是否合并不影响使用本分支中的自包含目录。

```bash
git clone --depth 1 --branch task/198-fig5-fixed-eval-20261112 \
  https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines.git
cd pbit-llm-qwen-baselines/qwen3/evaluation/fig5_fixed_weight_20261112
python -m venv /your/project/fig5-env
source /your/project/fig5-env/bin/activate
# 参考组合为 torch2.6.0 / triton3.2.0，适用于原 H20 环境。
pip install torch==2.6.0 triton==3.2.0
pip install -r requirements.txt
python verify.py
```

推荐单 GPU 至少 32 GiB，固定 batch32、每块32窗口。如果新 GPU 必须更换 PyTorch/CUDA 组合，记录版本，运行本包 gate 和完整父模型参考。不要静默减少 batch/改变分块：它会改变 GF 状态流及数值归约，必须作为新协议标注。

HF 权限按原模型仓库执行；如需登录，使用执行者自己的环境凭据。不要将 token 写入代码、日志或 Git。文件通过固定 revision 下载，不能换成 HF `main`。约 8 GB 父模型加约 1.89 GB overlay，并需常规 HF 缓存空间。

```bash
# 使用你们已有的原文，必须通过本包 SHA 检查。
python prepare.py --work /your/project/fig5-assets --raw /your/data/wiki.test.raw
# 或不传 --raw，脚本下载 HF parquet，恢复空行并校验同一份原文字节。
# python prepare.py --work /your/project/fig5-assets
```

`prepare.py` 输出 `assets.json`，其中记录所有模型/tokenizer 文件 SHA、模型/overlay revision、语料哈希；仅含本机路径，不含凭据。原文或 token 校验失败必须修正数据路径/复原方法，不更改预期哈希。下载脚本是本次新便携入口，本地没有下载多 GB 权重或运行 GPU；正式执行由接手者完成。

## 4. 运行顺序

工作目录必须是个人项目目录；结果放在源码目录之外。同一批 GPU 任务读取同一份 `assets.json` 和冻结源码，各 case 独立输出目录。修改源码后必须新建结果目录并重新 gate，保留失败快照。

```bash
python run_eval.py gate --assets /your/project/fig5-assets/assets.json --out /your/project/fig5-results
python run_eval.py full --case parent_bf16 --assets /your/project/fig5-assets/assets.json --out /your/project/fig5-results
python run_eval.py full --case overlay_bf16 --assets /your/project/fig5-assets/assets.json --out /your/project/fig5-results
python run_eval.py full --case exact_k128 --assets /your/project/fig5-assets/assets.json --out /your/project/fig5-results
python run_eval.py full --case exact_k256 --assets /your/project/fig5-assets/assets.json --out /your/project/fig5-results
python run_eval.py full --case exact_kall --assets /your/project/fig5-assets/assets.json --out /your/project/fig5-results
# 例：无 K 筛选、S64、seed0
python run_eval.py full --case gf_kall_s64_seed0 --assets /your/project/fig5-assets/assets.json --out /your/project/fig5-results
```

全部 case 名称由 `PLAN.json` 给出。支持按相同命令续跑：已有 part 会核对源/输入身份后复用，完整 RESULT 已存在则拒绝覆盖。不要同时启动同一个 case。Slurm 的 partition/account/time 由执行者配置，本包不包含作者服务器账号或硬编码提交资源。

Gate 会验证 GF 映射的 GPU/CPU 字、赢家、随机状态、K128/K256/2048；验证原生 SDPA 与同算子 wrapper 的 logits 一致；检查 overlay 只覆盖 144 个 QKV/O 张量；检查长 KV 和冷启动的36层实际替换。完整父模型参考完成且 NLL 与已录锚点匹配后，其他 case 才能开始。GPU gate 通过不等于完整 PPL 已完成。

运行用时请由 gate 和第一个完整控制实测后估计，不将局部采样 kernel 时间当完整 WT2 时长。本次未申请或提交新的 GPU 任务。

## 5. 收集与画图

```bash
python verify.py --results /your/project/fig5-results --output /your/project/fig5-results/SUMMARY.json
```

检查器验证每一窗口、每一目标、每层执行数和 part 字节 SHA，并重算总 NLL/PPL。主曲线每个点报告三个 seed 的**PPL 算术均值及样本标准差**；各 seed 自身的 PPL 必须先由总 NLL/299077 计算，不能先平均窗口 PPL。Fig.5(a) 横轴 S，三条曲线为 K128/K256/无筛选；完整 PV 控制用于相应参考，不与不同权重的历史 PPL 拼线。

回传要求见 [RETURN_CHECKLIST_ZH.md](RETURN_CHECKLIST_ZH.md)。可提前回报已有点，但缺失点填 pending，失败结果保留，不补假数。本轮交付是方案和待 GPU 验证的便携执行代码；没有声称新增 41 项 PPL 已完成。
