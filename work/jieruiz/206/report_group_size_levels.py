import datetime,json,pathlib,statistics
R=pathlib.Path('C:/Users/86134/Documents/a_P_BIT/tmp/group64-scale-issue206-20261028');W=R/'work/jieruiz/206';B=R/'qwen3/results/group_shared_20261028'
x=json.loads((B/'GROUP_SIZE_LEVELS_SUMMARY.json').read_bytes());assert x['status']=='completed'
rows=x['rows'];best=min(rows,key=lambda r:r['finite_mean'])
table='\n'.join(f"|{r['group']}|{r['levels']}|{r['finite_mean']:.4f} ± {r['finite_sd']:.4f}|{100*r['relative_to_g64b4']:+.2f}%|{r['conditional_mean_seed0']:.4f}|{r['scale_index_bits_per_active_FFN']//8} B|" for r in rows)
detail='\n'.join(f"|G{r['group']}/B{r['levels']}|{100*r['mean_AND_probability']:.3f}%|{100*r['zero_AND_fraction']:.2f}%|{100*r['g_clip']:.2f}%|{100*r['u_clip']:.2f}%|{r['worst_accumulator_bound_bits']}|" for r in rows)
text=f'''# g/u非线性共享组16/32/64与四/八档：受控扫描

本轮最好为 **G{best['group']}/B{best['levels']}，PPL {best['finite_mean']:.4f} ± {best['finite_sd']:.4f}**，相对原G64/B4 {100*best['relative_to_g64b4']:+.2f}%。这只是同协议1024目标后缀结果，不是完整WT2、任务准确率、芯片实测或无损验收。

|g/u每组元素数|可选PoT档数|有限NL128三seed PPL，均值±样本SD|相对G64/B4|条件NL均值诊断，seed0|单个活动FFN的g/u档号位数折合字节|
|---:|---:|---:|---:|---:|---:|
{table}

同轮未改动BF16 PPL **13.566049**。G64/B4三个seed逐值复现18.20000779048508、17.89494970067286、17.669679075660085。小幅三seed差异不作为普适显著性证明；候选未自动替换TLM/RTL默认。

本轮G16/B4三个seed均低于同seed G64/B4，降幅约5.15%；G32/B4只改善均值，seed2反而较差。增加档数没有单调收益：G64/G32下B8仅小幅变化，G16下B8均值反而比B4差约2.19%。因此当前更值得保留的是G16/B4质量候选，不能把八档或重新校准当作必然改进。它仍比BF16高约25.3%，尚未解决全部质量损失。

G64/B4→G16/B4条件NL均值seed0基本不变（15.8621→15.8825），有限采样结果改善；同时平均AND事件概率2.1904%→2.7039%、零事件比例34.65%→30.79%。这与缩组减轻有限采样损失一致，但不是唯一原因证明，均值诊断仍不是严格PPL下界。

## 只改哪些边界

- 入口x保持冻结四档、每64项共享；固定Wg/Wu/Wd仍有符号W8，每64×64一个静态PoT权重LSB，权重量化算子不改。
- GU投影仍64次/64层门限分层；sigmoid仍由幅度编码前正常g经signed8、步长1/8、RNE饱和进入既有P8 LUT。
- 三路AND非线性仍联合4×2×4分层、128次，输出比特事件直接进入固定Wd后再准确整数累加统计。没有OR近似，没有增加采样。
- g与u分别选档，组大小相同，尺度不必相同；只把共享组改为64/32/16，或档数4→8。Attention保持准确SDPA，36层及所有前缀FFN均替换。

四档直接使用成功e888 risk4目录。32/16组继承各自parent64的目录，不重新拟合。八档为原最大指数结尾的8个连续PoT，严格包含旧四档、最大尺度不变；不是上轮失败的大样本重新校准表，不改变x/权重目录。这样隔离组大小/档数影响，但也意味着没有为子组专门优化尺度，不能把当前结果当作其最终极限。目录仅源自原TRAIN拟合，不按TEST选择。

## 概率与饱和诊断

|方案|平均AND概率|零事件比例|g幅度饱和|u幅度饱和|原整数归约最坏安全边界位数|
|---|---:|---:|---:|---:|---:|
{detail}

条件NL均值只删除当前非线性计数噪声，GU仍有限随机。它不是整随机LLM期望或严格PPL下界，不可对PPL差做线性误差分解。概率、零事件和饱和仅帮助解释，不能代替PPL。最坏位数是当前数学上界，不是已选择/综合的硬件位宽。

## 对电路的影响

采样帧长度保持GU64/NL128。每组缩小，组内仍统一尺度，可先组内归约再跨组PoT对齐；需要更多组索引、选择及部分和路径，不能默认面积/能量免费或关键路径不变。上表字节数只算9728维g/u各一个档号：2×(9728/G)×log2(B)/8，每活动FFN一次；不含概率码、累加状态、尺度表、带宽或物理广播，也不表示36层必须同时驻留。

子组目录与parent64相同，物理实现可共享静态表，无需因组数增加重复复制目录。四→八档使每组档号2→3位、候选阈值比较3→7、静态目录翻倍；对齐跨度也可能增加。此处没有新RTL/PT/PPA，未从这些结构计数宣称能耗收益。

## 复现与验证

执行源`{x['source']}`，82源文件；原e888的75执行blob保持原字节。CPU71项（10项CUDA跳过），GPU71项全部通过，包含旧G64/B4数值回放、CPU/CUDA编码、各组严格同尺度、所有形状/符号/饱和/零值、独立解码Wd均值参考及权重不变。

Slurm3291 CPU→3292 GPU门禁→3293_[0-5]，全部封存。主36物理计分/28唯一标签/25唯一配置seed；旧risk4控制三标签是G64/B4有限三seed的别名，未冒称额外独立结果。另门禁3计分：BF16、旧控制和8目标pilot，pilot不混入主表。主数据8窗×128=1024目标、context2048、每窗2175输入；全36层各8次/17400输入token覆盖，目标位置、NLL、模型/tokenizer/语料/配置/prepared/source/documents/sidecar SHA核验。无聊天模板、无训练。

配置SHA246f41e73a114b08e2cf787ca7335df1dd0b1bceee091c88026141a830aff2dc；prepared SHA f8c6c0a754f5c7fff4a5afa0d054b4ca59493efde6ef5b742515d9ed58f054db；原目录SHA9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7。模型Qwen/Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c。源码/提交/收集/核验入口`work/jieruiz/206/GROUP_SWEEP_*`及`audit_group_size_levels.py`；原件远端`/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206/results/{x['source'][:12]}/group_size_levels/`。

GU恢复继续是FP32数值oracle，非全链有限宽bittrue；比较器码和末端计数是显式整数边界。大JSON如压缩，以COMPRESSED_ARTIFACTS索引保留原字节SHA及可恢复gzip；未改冻结执行快照。仅本次质量扫描，无新电路台账run、PPA/TLM默认改动。通过同PR207交付，未自动合并或关闭Issue，Projects沿既有权限限制待同步。
'''
(B/'GROUP_SIZE_LEVELS_REPORT_ZH.md').write_text(text,encoding='utf-8',newline='\n')
candidate=dict(status='suffix_only_quality_candidate_pending_fullWT2_and_PPA',model='Qwen/Qwen3-4B',revision='1cfa9a7208912126459214e8b04321603b3df60c',
 source=x['source'],module='qwen3.group_shared.group_sweep_core.GroupSweepFFN',scheme=best['scheme'],input_shared_group=64,input_levels=4,
 nonlinear_shared_group=best['group'],nonlinear_levels=best['levels'],GU_samples=64,NL_samples=128,weight_tile=[64,64],weight_policy='signedPoTW8',
 parent_calibration_sha256='9a26ddde7c2ed935e652cefbadd5bf63b9f5b4f23a269775f47d38f0963987f7',catalog_policy='inherit parent64 risk4;B8 nested contiguous ending at same maximum',
 suffix_PPL_mean=best['finite_mean'],suffix_PPL_sd=best['finite_sd'],no_TLM_or_RTL_default_change=True,GU_restore='FP32 numerical oracle,not fullchain bittrue')
(R/'qwen3/group_shared/GROUP_SWEEP_BEST_CANDIDATE.json').write_text(json.dumps(candidate,indent=2)+'\n',encoding='utf-8',newline='\n')
note=f'''## Issue206：g/u共享数量/档数扫描完成（2026-10-28）

用户要求x保持64共享；六组G64/32/16×B4/8全部三seed完成。最好G{best['group']}/B{best['levels']} PPL{best['finite_mean']:.6f}±{best['finite_sd']:.6f}，原G64/B4为17.921546；同轮BF1613.566049。各组均值：'''+', '.join(f"{r['scheme']}={r['finite_mean']:.6f}" for r in rows)+f'''。均仅1024后缀目标，不是完整WT2或任务准确率；不能宣称无损。输入x四档/共享64、PoTW8每64x64、GU64、正常g signed8-P8、NLjoint32T128、准确SDPA、所有36层/前缀均不变。

执行源{x['source']}，82源/旧75字节不变。四档继承成功e888；缩小子组复制parent64目录，八档嵌套补齐且最高尺度不变，无新TRAIN拟合或TEST选表。CPU71（10跳过）/GPU71通过；3291/3292/3293全部完成，主36物理/28标签/25唯一配置seed，另3门禁独立列。SHA、36层/目标/NLL/档号同组核验通过。报告GROUP_SIZE_LEVELS_REPORT_ZH/JSON，候选GROUP_SWEEP_BEST_CANDIDATE.json；原CURRENT_RECOMMENDED和TLM/RTL默认不自动替换。每活动FFN标签状态从G64/B4的76B变化到最佳{best['scale_index_bits_per_active_FFN']//8}B，仅结构计数，无新PPA；GU仍FP32oracle非全链bittrue。

无本轮运行作业；准确上传状态以后续GROUP_SWEEP_FINAL_PUBLICATION为准，未合并/不关闭Issue，Projects待既有权限同步。下方保留历史。

'''
for p in (R/'PROJECT_MEMORY_ZH.md',R.parents[1]/'PROJECT_MEMORY_ZH.md',R/'progress/jieruiz/STATUS.md',W/'HANDOFF.md'):p.write_bytes(note.encode()+p.read_bytes())
with (R/'qwen3/group_shared/README_ZH.md').open('a',encoding='utf-8',newline='\n') as f:f.write('\n'+note.rstrip()+'\n')
with (B/'REPORT_ZH.md').open('a',encoding='utf-8',newline='\n') as f:f.write('\n'+note.rstrip()+'\n')
print(json.dumps(candidate))
