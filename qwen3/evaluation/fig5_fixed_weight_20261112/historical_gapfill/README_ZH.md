# 本轮只补历史表的5个缺项

用户2026-11-12明确：之前测过的不重跑。默认任务由先前41项新版本扫描，改成补齐用户截图中的空白；**已有10个配置/30个seed结果全部复用**。不会把不同权重/前端结果混填到这张表。

## 只跑这些采样配置

| K | S | seed |
|---|---|---|
| 256 | 16 | 0、1、2 |
| 无筛选 | 16 | 0、1、2 |
| 无筛选 | 32 | 0、1、2 |
| 128 | 256 | 0、1、2 |
| 256 | 256 | 0、1、2 |

合计 **5配置×3seed＝15项新采样PPL**。`PLAN.json`另含一个`parent_bf16`环境校验：新运行环境建立匹配参考用，不重跑已完成的随机配置或SparQ准确PV曲线。已有BF16/SparQ128/SparQ256控制及30份采样结果的逐seed数值、来源汇总SHA和结果SHA在[EXISTING_RESULTS.json](EXISTING_RESULTS.json)，后续作图直接引用。

## 固定历史口径

- 原始后训练版Qwen/Qwen3-4B，revision见[ASSETS.json](ASSETS.json)，不加载K_WH64或其他训练overlay。全部QKV/O、FFN、其他参数保持父模型BF16。
- 与截图相同：**先把绝对QK分数RNE量化到signed12/F4，饱和[-2048,2047]；再求码域max与差值；差值饱和为U8地址；读取原floor-P8 sigmoid表**。这是历史S12-first曲线，不标成最新max-first硬件的PPL。
- 候选与仲裁均沿用历史独立Philox；不是GF64/Bivium。winner位置0初始化、burn0、允许重复、空候选保持原winner，每次输出一个V地址；S次V求和除S。
- SparQ r32、四Q头共享候选、最近32包含在K内，无mean-V。无筛选使用`Config(k=2048, local=0)`，窗口≤2048使`core.select`在粗QK之前直接返回全部有效地址；不触发TopK。
- 保存旧Config字段和repr，以保持`seed:partStart / layer / call / Config`随机键；不可额外改变候选排序、块大小、batch或采样初始化。

最新K_WH64/max-first/GF扫描仍保留在父目录作为非默认备选，本轮不执行。补齐历史表不等于验收最新硬件前端；论文标注清楚即可，无需因此把所有已有点再跑一遍。

## 从这里运行

进入**本README所在的`historical_gapfill`子目录**，不要运行父目录的41项计划。完整子目录是自包含的，源自原已执行内核；此次便携路径调整仍需先过GPU门禁。

```bash
cd qwen3/evaluation/fig5_fixed_weight_20261112/historical_gapfill
pip install -r requirements.txt
# PyTorch/Triton参考环境：torch2.6.0 / triton3.2.0；按GPU先装兼容CUDA版本。
python verify.py
python prepare.py --work /your/project/fig5-gap-assets --raw /your/data/wiki.test.raw
python run_eval.py gate --assets /your/project/fig5-gap-assets/assets.json --out /your/project/fig5-gap-results
python run_eval.py full --case parent_bf16 --assets /your/project/fig5-gap-assets/assets.json --out /your/project/fig5-gap-results
python run_eval.py full --case ising_k256_s16_seed0 --assets /your/project/fig5-gap-assets/assets.json --out /your/project/fig5-gap-results
```

其余14个采样任务从`PLAN.json`读取，三个seed全部保留。同一case不可并行提交两次；完整结果已存在则拒绝覆盖，部分结果可按相同命令续跑。不要取消其他人已运行的健康作业。

## WT2必须一致

全文原文/token SHA由脚本校验，token数299078；不套聊天模板/不加BOS/EOS；窗口2048、步长1024，共292窗/299077目标。未计分前缀准确预填充、每个计分目标实际走36层单query路径；每32窗一块、batch32；总NLL除299077后取指数，不平均窗口PPL。计分算法和原文复原细节见父目录[WT2_PROTOCOL_ZH.md](../WT2_PROTOCOL_ZH.md)；其中GF相关随机源段落仅属于旧41项计划，本任务的RNG以上述Philox定义和本目录代码为准。

完成后：

```bash
python verify.py --results /your/project/fig5-gap-results --output /your/project/fig5-gap-results/SUMMARY.json
```

回传新15项的逐窗NLL/part/RESULT/GATE、输入和源SHA、命令、环境版本及SUMMARY；旧结果不要求再次生成。同目录EXISTING_RESULTS保留30条旧采样记录，SUMMARY分开返回`reused`和新`accepted`，作图时按(K,S,seed)合并且不得重复计入。原先41项计划尚未在本对话提交GPU；这次也只修正交接，无新PPL或训练。
