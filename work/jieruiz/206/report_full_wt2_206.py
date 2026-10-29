import json,pathlib
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';B=R/'qwen3/results/group_shared_20261028'
x=json.loads((B/'FULL_WT2_G64B4_SUMMARY.json').read_bytes());assert x['status']=='completed' and x['completed_main']==18
table='\n'.join(f"|seed {r['seed']}|{r['bf16']['perplexity']:.6f}|{r['g64b4']['perplexity']:.6f}|+{r['PPL_change_percent']:.2f}%|" for r in x['results'])
report=f'''# 64共享、四档FFN：完整WikiText-2 PPL（Issue206）

**完整WT2已完成：原BF16 PPL {x['bf16_PPL']:.6f}，64共享概率FFN三seed平均 {x['g64b4_mean']:.6f} ± {x['g64b4_sample_SD']:.6f}，相对原模型增加 {x['mean_PPL_change_percent']:.2f}%。** 这次是全测试语料滑窗，不是此前1024目标的后缀测试。PPL越低越好；没有以短后缀分数推算完整分数，也没有重新训练或按TEST调整尺度。

|完整WT2|原BF16|G64/B4概率FFN|相对同轮BF16|
|---|---:|---:|---:|
{table}
|三seed均值 ± 样本标准差|{x['bf16_PPL']:.6f}|**{x['g64b4_mean']:.6f} ± {x['g64b4_sample_SD']:.6f}**|**+{x['mean_PPL_change_percent']:.2f}%**|

三个BF16值是同一确定性参考的重复核验，不是三个独立模型。标准差表示随机seed间的变化，不是置信区间。这里只测PPL，不推断任务准确率。

## 测试范围与保持不变的配置

后训练模型`Qwen/Qwen3-4B`，revision `1cfa9a7208912126459214e8b04321603b3df60c`。原文teacher-forced PPL，无chat模板、BOS、thinking生成或KV cache。完整test分词299078个token，除第一个无前缀token外，**299077个目标各恰计一次**；窗口2048、stride1024，共{x['windows_per_seed']}窗，每窗batch1，lm_head每256目标分块以控制显存。所有窗口前缀、所有36层FFN都使用当前所选路径；Attention始终是原准确SDPA，不包含筛选、Ising或PV采样。

|部位|本轮设置|
|---|---|
|入口x|连续64项共享一档，原TRAIN冻结四档二次幂目录|
|Wg/Wu/Wd|固定有符号W8，每64×64权重块静态二次幂LSB|
|Wg/Wu随机输入矩阵|64次采样、64层阈值分层|
|g与u幅度|各自连续64项共享一档，各有独立TRAIN冻结四档；原e888 risk4重新校准结果|
|sigmoid|直接用原g、signed8步长1/8、RNE/饱和、P8 LUT；不先裁剪幅度g再送sigmoid|
|非线性与Wd|三比特流AND，4×2×4联合32层、128次采样；事件直接进入固定Wd整数计数/对齐/恢复|
|Attention、残差、词表读出|保持原准确实现|

没有测试G16候选的完整WT2，没有增加采样数，没有重新拟合目录/训练权重，没有更改CURRENT_RECOMMENDED或RTL/TLM默认。

## 完整语料与旧后缀的区别

|协议|原BF16|G64/B4三seed均值|
|---|---:|---:|
|旧1024目标后缀|13.566049|17.921546|
|本轮完整299077目标|{x['bf16_PPL']:.6f}|{x['g64b4_mean']:.6f}|

这两行的目标集合、窗口布局和随机流调度不同，**绝对PPL下降不能解释成方案改进**。应在同一行与同轮BF16比较。本轮给每个seed/全局窗口号建立SHA256随机键，避免每窗复用同一随机序列，也使分片数量不影响同一窗口的随机流；旧后缀是连续消耗RNG，因此不要求跨协议随机路径逐值一致。GPU门禁另用旧调度准确复现原后缀BF16和G64/B4seed0，证明FFN本身没变。

每seed六片，18片最多6GPU并行。每片重跑未改动BF16后运行同片G64/B4；三seed各自拼回完整目标。先把所有目标的负对数似然相加、除以总目标数、最后取exp，**不平均各片/窗口PPL**。第一窗与末尾短窗也覆盖，重复/缺失窗口会使审计失败。

## 实际验证与证据

- CPU3307：77项检查通过，10项CUDA专用检查跳过；包括全目标覆盖、首尾边界、分片、缺失/重复拒绝、随机键，以及小模型逐token损失oracle/分块一致性。
- GPU3308：旧后缀BF16=13.566049199388152、G64/B4seed0=18.20000779048508准确复现；完整首/末窗功能门禁。四份门禁计分单独保存，不冒充完整WT2。
- 正式3309_[0–17]：18片全部封存，每片BF16与G64/B4共36份分片计分；汇总成1份BF16参考和3个随机seed的完整PPL。所有36层调用及输入token数、输入/模型/代码/配置/目录/原件SHA、NLL和目标覆盖均已核验。
- 科学执行提交`{x['source']}`，86个执行文件；前一轮82文件原字节不变。提交后的执行快照未修改。
- [完整汇总与每seed NLL/目标SHA](FULL_WT2_G64B4_SUMMARY.json)；[原始门禁/分片/Slurm日志]({x['source'][:12]}/full_wt2/)；`work/jieruiz/206/FULL_WT2_SOURCE_*`、`FULL_WT2_SUBMISSION_*`、`FULL_WT2_COLLECTION_*`及收集/审计脚本可复核。

WT2 train原文SHA256=`6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57`；test=`173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08`。冻结risk4原表SHA256=`9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7`。详细模型/tokenizer文件SHA在prepared及provenance源索引。

GU累加后的恢复仍是声明过的FP32数值oracle，非全链路定点bittrue；NL概率码、比较/计数及Wd恢复边界显式实现。本次没有新电路、PT/PPA、能耗/面积/速度或训练结论。PR207交付，未合并；Issue206保持开放待审，Projects沿既有权限限制待同步。
'''
(B/'FULL_WT2_G64B4_REPORT_ZH.md').write_text(report,encoding='utf-8',newline='\n')
note=f'''## Issue206：64共享完整WT2三seed已完成（2026-10-28）

同后训练Qwen3-4B/准确SDPA，窗口2048-stride1024，每seed299077目标、{x['windows_per_seed']}窗，各恰一次；所有36层及前缀FFN替换。BF16={x['bf16_PPL']:.6f}；原G64/B4三seed={', '.join(f'{z:.6f}' for z in x['g64b4_seeds'])}，均值{x['g64b4_mean']:.6f}±{x['g64b4_sample_SD']:.6f}，相对BF16+{x['mean_PPL_change_percent']:.2f}%。x64/固定PoTW8/GU64/NLjoint32T128/正常g signed8-P8/冻结e888 risk4不变，无训练、无新拟合/RTL/PPA/TLM默认变化；GU仍FP32oracle非全链bittrue。与旧后缀17.92的绝对差异不能解释为质量改善。

科学源{x['source']}，86文件旧82不变；CPU3307共77项（10跳过）、GPU3308旧后缀准确回放及首尾窗通过；3309全部18片/36分片分数封存，1BF16+3seed完整PPL，源/配置/模型/语料/目标/36层/NLL/SHA核验。RNG按seed+窗口SHA键固定且不依赖分片数量，与旧后缀连续RNG分开标注。报告qwen3/results/group_shared_20261028/FULL_WT2_G64B4_REPORT_ZH.md及SUMMARY；W/FULL_WT2_SOURCE/SUBMISSION/COLLECTION、收集审计脚本可恢复。无本轮运行作业，不重跑、不自动回查；PR207未合并/Issue开放，实际上传以FULL_WT2_FINAL_PUBLICATION为准，Projects待既有权限同步。

'''
for p in (R/'PROJECT_MEMORY_ZH.md',R.parents[1]/'PROJECT_MEMORY_ZH.md',R/'progress/jieruiz/STATUS.md',W/'HANDOFF.md'):p.write_bytes(note.encode()+p.read_bytes())
for p,text in ((B/'REPORT_ZH.md','\n## 64共享完整WT2补测\n\n'+f'BF16 **{x["bf16_PPL"]:.6f}**，G64/B4 **{x["g64b4_mean"]:.6f} ± {x["g64b4_sample_SD"]:.6f}**，三seed、299077目标、准确SDPA。详见[FULL_WT2_G64B4_REPORT_ZH.md](FULL_WT2_G64B4_REPORT_ZH.md)。旧后缀分数保持原标注。\n'),(R/'qwen3/group_shared/README_ZH.md','\n## 64共享完整WT2已完成\n\n'+f'BF16 {x["bf16_PPL"]:.6f}；G64/B4三seed {x["g64b4_mean"]:.6f}±{x["g64b4_sample_SD"]:.6f}；2048/1024全语料299077目标，准确SDPA，原目录/采样不变。结果[完整WT2报告](../results/group_shared_20261028/FULL_WT2_G64B4_REPORT_ZH.md)，不与旧后缀混称。\n')):
 with p.open('a',encoding='utf-8',newline='\n') as f:f.write(text)
print(json.dumps(dict(report=str(B/'FULL_WT2_G64B4_REPORT_ZH.md'),BF16=x['bf16_PPL'],mean=x['g64b4_mean'],sd=x['g64b4_sample_SD'])),flush=True)
