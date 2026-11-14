# Fig.5：固定K_WH128权重的五项单seed补测

2026-11-14，用户明确选择“先补5个缺测点，保留已有曲线”，并要求单种子节约时间。接续Issue198，独立分支task/198-fig5-kwh128-gapfill-20261114，基线b123a8ba43d72ec863b312e35cc7f18c148ad12b；不更改PR256旧方案或父会话图稿。

## 本轮范围

|数组索引|K|S|seed|
|---:|---:|---:|---:|
|1|64|64|0|
|2|64|128|0|
|3|128|16|0|
|4|256|16|0|
|5|256|128|0|

复用trained_budget_20261107与trained_cross_20261107的七个已完成采样配置以及K64/128/256准确PV控制。补齐后形成K64/128/256 × S16/32/64/128的12点扫描；不增加S256、不重跑已有采样点、不训练。为保持同一统计口径，主曲线可以统一使用每个配置seed0；已有三seed均值/SD另保留，不为新单seed点制造误差棒。

所有点固定同一份K_WH128 Attention Q/K/V/O权重，FFN、norm、embedding和lm_head为原始准确BF16。K_WH128名称中的128是原训练采样次数，不是固定候选K。HF revision 9ab262b60915a2711caff2af2937e89aa67072ad；具体权重原字节SHA见SOURCE_ARCHIVE.json，模型/语料/分词器原始SHA由执行包config/prepared以及provenance绑定。

保持历史前端：FP32分数RNE/sat signed12/F4，再整数max-gap、U8/F4地址、冻结floor-P8 sigmoid。独立Philox赢家保持、初始slot0、burn0、spacing1、全零保持、重复赢家计入S。SparQ r32/recent32，四Q头共享候选，没有mean-V补偿。该批不是最新FP32先减最大值前端或GF64位真结果。

完整WT2：window2048/stride1024、292窗、299077目标，计分query覆盖36层；未计分prefill准确，batch32/chunk32、每任务2CPU。保留旧Config和随机键，除了K/S与任务清单不改数值内核。

## 已提交与检查

- CPU检查5708：13项PASS，包括任务矩阵、前端数制、采样重放和计分覆盖。
- GPU检查5709：PASS，覆盖五种新配置、24组采样replay、原生/封装参考、冷启动及生产形状；峰值22939786240B。
- 未改动BF16完整参考5710：2026-11-14 23:22北京时间正在运行。完成后要求PPL与11.538153433607206的绝对差小于1e-5，该容差只覆盖数值舍入，不是可接受模型质量损失。
- 五项完整PPL数组5711_[1-5%2]：已提交，afterok参考；最多2GPU，单任务48GiB主机内存、2CPU、2小时上限。尚无本轮完整PPL结果。
- 旧结果和他人健康任务未取消、未覆盖；Slurm accounting关闭，状态依据squeue、日志和密封完成文件，不能仅凭任务从队列消失认定完成。

冻结identity：1cd58b43aabbf92214f7fe65efd22d9d1234fbd69b6ba0927751c3f9170904ea。它是源码manifest身份，不是Git提交。服务器根、实际ID、全部源SHA在SUBMISSION.json；54成员冻结源ZIP已归档于SOURCE_ARCHIVE.json指定本地位置。旧父快照e17befe4cb3f保持不变。

## 恢复

在本目录所在checkout运行：

```text
python experiments/attention_trained_gapfill_20261114/ops.py status
```

只读收集结果时逐项核对RESULT/complete、源码和输入SHA、全部part SHA、292窗/299077目标/36层覆盖并复算NLL→PPL，再填图。SUBMISSION.json存在时不得再次执行stage；若门禁失败，保留原快照/任务ID，新修复另建identity，不能直接改运行中源码。

本轮仅GPU评测提交和本地证据归档，未修改PPT、PPA或TLM。图版式建议见FIGURE_PLAN_ZH.md。预计资源正常时约1—2小时，实际以参考与首个完整采样项用时修正。
