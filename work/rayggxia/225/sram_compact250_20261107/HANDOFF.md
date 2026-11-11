# Issue225 / PR249：250MHz SRAM缩减交接

负责人rayggxia，2026-11-07。分支task/225-tlm-unified250-20261107，PR base task/225-norm-stream-20261106；工作目录为本checkout。最新模块交接SHA及原100源哈希见PREFLIGHT.json。无新模块实现需接入，短T TT250时序失败门禁保留。

本地已完成：960KiB默认，1088/1216对照；真实bank重排和角色地址译码；按实际区域计算面积/漏电。4测试、3完整冷单层、同源/动作/核帧/外存地址及字节/封存SHA检查通过。正式报告SRAM_COMPACT_ZH.md和SRAM_COMPACT_RESULTS.json。公共源码/汇总/索引可交付；原捕获输入和执行依赖仍在授权本地归档，不复制其私有源码。

执行源提交a63cf1de246fb59a6da939cacfca3b76940d4f14。封存九原件在本目录reference1216、compact1088、compact960下，summary记录SHA；不要重写原件。相同代码的区域状态与字节图样已测；完整151936词表tile形状检查通过，未执行完整head时间。不把单层乘36当新原生token结果。

从checkout运行：

```powershell
python -B architecture_tlm/sram1216_20261106/250MHz/test_sram_layout.py --runtime ../../project_archives/ffn_sram_batch204_20261106/runtime --dependencies ../../project_archives/sampling_latency225_20261106/dependencies -v
python -B work/rayggxia/225/sram_compact250_20261107/compare.py
```

三次原执行命令仅profile/out不同：

```powershell
python -B architecture_tlm/sram1216_20261106/250MHz/run.py --runtime ../../project_archives/ffn_sram_batch204_20261106/runtime --dependencies ../../project_archives/sampling_latency225_20261106/dependencies --inputs ../../project_archives/attention_integrated250_198_20261107/inputs --backend analytic --scope layer --cores 3 --seed 17 --sram-profile compact960 --out work/rayggxia/225/sram_compact250_20261107/compact960
```

已有输出目录不可覆盖；如确需复现另设out。不得修改100、owner198/204源或旧在运行快照。无需重复本轮健康回放。下一步仅待短T250时序闭合后接有效价；长上下文/候选或数字路径须新布局检查。上传与逐字回读状态以PUBLICATION.json为准，PR待审不自动合并；Projects无写工具，待维护者同步。
