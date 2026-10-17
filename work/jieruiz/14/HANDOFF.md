# Issue #14：Llama 2 7B交接

更新 2026-10-18T00:05:44+08:00（Asia/Shanghai）；负责人 @jieruiz。全部116项及完整BF16基线已推送；PR #15待审，未合并。

正式仓库 `rayggxia-workspace/pbit-llm-qwen-baselines`，分支 `task/14-llama2-baseline-tlm`，PR15 base `pbit-tlm-attention-details-20261016` @07d03385a3b16b1f81a987c031f667c13876edf1。独立目录 `C:/Users/86134/Documents/a_P_BIT/tmp/llama2-7b-issue14-20261017`。PR待审不等于合并；Issue14待验收保持open。最终交付SHA以PR头和Issue发布评论为准，不将文档自身SHA写入其内容形成循环。

## 已完成与可复现版本

| 阶段 | 不可变源码 / 服务器快照 | Slurm / 结果 |
|---|---|---|
| 镜像/原BF16评测 | 9ee1ab47d0317430212364e75adb78abec9797fb / baseline_9ee1ab47d031 | 1960下载、1961完整WT2均完成 |
| 匹配文本捕获及TLM | b5964b165dfead06676580029235bf5e952b5dad / tlm_b5964b165dfe | 1963逐bit捕获，1964 Link72，1965 Staggered36，1966 NoPowerDown8均完成 |
| 规范后处理 | 358d8b8f943f60986f86362f7bc7aacfca531adc / report_358d8b8f943f | 2069完成，reports/final_v1/，116/116项齐全 |

旧pending捕获1962在开始前取消，替换为固定start201979的1963；旧快照未修改。没有本任务运行中的作业，sacct未启用，完成以原始成果、后处理校验和squeue核查为证据。

服务器根 `/home/Hongjie_Zeng/projects/pbit-llama2-7b-20261017-issue14`，Python `/home/Hongjie_Zeng/.conda/envs/pbit_llm/bin/python`。Py3.12.14、torch2.7.1+cu128、Transformers4.45.2、RTX5090。完整命令/Slurm脚本及参数保留正式baseline/architecture目录和本目录job记录；不要修改冻结的57份输入。后处理与后续只读SHA采集不是新的性能执行版本。

## 模型、文本与成果

- 用户授权ModelScope镜像，11文件与官方revision `01c7f73d771dfac7d292323805ebc428287df4f9` 的LFS SHA或Git blob匹配。身份清单SHA `8ba3ccc3acf4b1a38a8c41a71ecafa8f4a0c1f53900a6298a32088dd57847d74`。权重单份保留 `/home/Hongjie_Zeng/pbit_llm/models/Llama-2-7b-hf`，不进入Git。
- 原始test corpus SHA `173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`；完整IDs SHA `d47afcd2762c6a3e70f50c5b7de0e4ccad565d812aee21772b7cd276b7b8626c`。无新训练/校准，不使用train语料。
- BF16完整PPL2K4.979502845218782、4K4.895831220529201；335686个target各计一次，FP32 CE/FP64汇总，stride512、无额外BOS/EOS。原始12文件＋manifest字节已验证，见 `baselines/llama2_7b/results/bf16_wt2_20261017/`。
- 捕获512/1K/2K/4K每项1024行，前后logits逐bit相同；固定start201979、前2K IDs SHA `5c208664955a0c5e4d2fb19d1a018559bf02eccd36d6aafb2a77b0e5d8cabca8` 与Llama1一致。大trace留服务器 `outputs/traces/`，SHA见capture_validation与最终索引。
- 正式表 `architecture_tlm/llama2_7b/results/current/RESULTS_ZH.md`、cases CSV/JSON、summary、ARTIFACT_INDEX。`DRAM_ARTIFACT_INDEX.json`另索引44项DRAM的88个原始gzip事务/bridge日志，及实际bridge/DRAMSys/DRAMPower运行库SHA；未下载长日志。
- 发布逐文件SHA见本目录 `manifest.json`；执行57输入SHA见正式 `EXECUTION_MANIFEST.json`。Git blob保留原始结果字节，大成果只提供位置/大小/SHA，不上传数据、权重或工艺库。

## 实际验证与边界

27项本地协议/契约检查、真实BF16基线、4上下文逐bit捕获、116个唯一key/输入来源/时间/能量/访存守恒通过。4K最大地址低于16GiB、工作区低于8MiB，MHA不发生GQA候选并集放大；比例PV32/64/128/256，本地share64随机源和有限SRAM/scatter/CDC计费。独立只读审计逐格复核主表和JSON一致。

2K/4K筛选PV读K37.16%/33.52%、V1.41%/1.15%，摘要另收费；同SC FFN准确Attention整机能量减少2.16%/4.38%。当前T4096 FFN仍使整机比BF16 ASIC情景更慢/耗能。无随机替换联合PPL，筛选max4未按Llama2质量校准；Ising用理想地址采样和宏参数，没有物理混合验证。TLM不是GPU/芯片实测，数字算子/接口/PHY等仍部分代理，也未证明最优调度。

## 接续动作与待同步

1. 读Issue14、PR15最新评审与STATUS，确认PR头和本地干净状态；不重复已完成的Slurm作业。
2. 在本任务目录运行 `python work/jieruiz/14/verify_delivery.py --staged`，核57冻结输入、13基线原字节、116项及88外部成果索引和发布Git字节。完整基线或性能重跑只在新快照进行，具体命令按已保存作业脚本复现。
3. PR15等待评审；未获本次合并授权，不自动合并/关闭Issue。新的FFN优化/联合PPL可另立Issue，保持本证据不变。
4. Projects仍缺read:project，看板待有权限成员同步；Issue、PR、STATUS分别如实标记状态，不把本地完成写成远端完成。

并行baseline-code/tlm-code/report-code工作树保留，不删除或覆盖；旧Llama1/Qwen及其他待审任务范围不变。
