"""Read only sealed runs, verify byte hashes, render task summary."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[3]
BASE=ROOT/'architecture_tlm/unified_v6/results/current_ffn_20261024_v2'
NAMES=['qwen3_full_bf16_exact','qwen3_full_oldsc_exact','qwen3_full_latest64_exact','qwen3_full_latest128_exact','qwen3_full_latest64_screen_pv','qwen3_full_latest64_screen_rejection','qwen3_full_latest64_8k_pv']

def sealed(folder):
 manifest=json.loads((folder/'MANIFEST.json').read_text(encoding='utf-8'))
 assert manifest['status']=='completed'
 for name,sha in manifest['files'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==sha,(folder,name)
 return json.loads((folder/'RESULT.json').read_text(encoding='utf-8'))

rows=[]
for name in NAMES:
 r=sealed(BASE/name);assert r['model']['num_hidden_layers']==36
 assert len([p for p in r['phases'] if p['name']=='ffn_residual'])==36
 assert abs(sum(r['phase_ns'].values())-r['metrics']['elapsed_ns'])<.01
 if name.endswith('screen_rejection'):
  audits=r['sampler_audit'];assert len(audits)==36*32
  assert {(a['token'],a['layer'],a['head']) for a in audits}=={(0,l,h) for l in range(36) for h in range(32)}
  for a in audits:
   assert a['outputs']==a['requested_samples']==128
   assert a['valid_candidates']==512
   assert a['proposal_frames']==a['outputs']+a['rejected_multi']+a['rejected_empty']
   assert a['proposal_frames']<=128*128
   assert abs(a['elapsed_cycles']-sum(a['stage_cycles'].values()))<.001
   assert abs(a['elapsed_cycles']-(a['end_ns']-a['start_ns'])/a['clock_ns'])<.001
  total=sum(a['proposal_frames'] for a in audits)
  assert r['attention_activity']['sampler_outputs']==147456
  counts=r['random_interface']['source_counts']
  assert counts['biased_frames']==total+288
  assert counts['biased_bits_delivered']==total*511+36864
 row=dict(case=name,total_ms=r['metrics']['TPOT_ms'],core_equivalent_cycles=r['metrics']['elapsed_ns']/10,
     ffn_ms=sum(v for k,v in r['phase_ns'].items() if k.startswith('FFN_') or k=='ffn_output_conversion')/1e6,
     attention_core_ms=r['phase_ns']['attention_core']/1e6,
     lm_head_ms=r['phase_ns']['lm_head_and_argmax']/1e6,
     sram_peak_bytes=r['SRAM']['reserved_peak_bytes'],dram=r['DRAM']['traffic'],
     ffn_contract=r['FFN_contract'],execution_commit=r['execution_commit'],full_energy_J=None,full_area_mm2=None)
 rows.append(row)
sensitivity=sealed(BASE/'sensitivity')
summary=dict(scope='7 complete 36-layer Qwen3-4B synthetic decode schedules; 8 one-FFN sensitivities; 15 tiny three-seed fixtures',rows=rows,sensitivity=sensitivity['rows'])
(BASE/'SUMMARY.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode())
text='''# 本版完整TLM验证与周期结果（Issue179）

已执行7组完整36层Qwen3-4B decode、8组完整形状单FFN敏感性、15组三seed小形状整机检查。另有74项单元/机制检查通过。全部是新运行的合成事务模型，非PPL、非GPU实测、非RTL/PT。默认100MHz计算、80MHz SRAM、8个64×64 SC阵列、512 MAC/拍数字阵列、8MiB SRAM；这不是同面积优化后的两种芯片比较。

第一轮结果使用1152拍的保守新增源warmup参数，保留在current_ffn_20261024/。第二轮改为与现有160bit展开Bivium配置相符的5拍（800步）warmup条件宏；默认参数及本表均用第二轮。新三轴源仍是接口宏，不等于已验证其独立性/真实RTL实现。

## 完整decode

| 方案 | 上下文 | 整机 ms/token | 核等效周期 | FFN合计 ms | Attention核心 ms |
|---|---:|---:|---:|---:|---:|
'''
labels=['BF16 FFN＋准确Attention','旧随机FFN T32＋准确Attention','新FFN NL T64＋准确Attention','新FFN NL T128＋准确Attention','新FFN NL T64＋筛选/PV','新FFN NL T64＋筛选/校正拒绝','新FFN NL T64＋PV']
for label,r in zip(labels,rows):
 text+=f"| {label} | {'8K' if '8k' in r['case'] else '2K'} | {r['total_ms']:.3f} | {r['core_equivalent_cycles']:,.0f} | {r['ffn_ms']:.3f} | {r['attention_core_ms']:.3f} |\n"
text+='''
“核等效周期”是总ns÷10ns，包含80MHz SRAM及跨域等待，不是声明所有模块在一个逐拍RTL模型中执行。FFN合计含编码、GU、恢复、AND/Wd及最终转换，残差仍保留原整机阶段。仅decode，预先已有上下文KV；不含prefill。

数字基准与SC使用同一外存/片存/非FFN配置，但计算阵列不是已证明同面积或同能量的配置；表中差异不能直接当作同面积加速比。新旧FFN采样法、数值边界亦不同，不保证同质量。

## 单FFN瓶颈敏感性

以下都是D2560→F9728→D2560的一次完整FFN，不含Attention、lm_head和其他35层。

| 条件 | FFN ms | GU ms | 编码 ms | AND/Wd ms |
|---|---:|---:|---:|---:|
'''
for r in sensitivity['rows']:
 text+=f"| {r['case']} | {r['elapsed_ms']:.3f} | {r['gu_ms']:.3f} | {r['encoding_ms']:.3f} | {r['down_ms']:.3f} |\n"
text+='''
可以看到：计数流长度并不等于整层时间；固定权重每层71.25MiB的搬运、反复波次和宽部分和事务都保留。减少源吞吐会直接拉长Wd阶段；增加恢复并行路数的收益须与这些成本共同判断。8MiB只是可调配置，未完成最优SRAM容量搜索。

## 已验证与仍未知

- 验证：输入固定四档、零在线absmax、无z落盘/再编码；所有Wd输出波次重放同一事件；有限局部权重容量；新随机源按三轴独立需求而非共享64统计；不同T不改变resident权重载荷；资源不重叠、片存区域合法、完整36层/阶段时间守恒。
- 兼容：旧Attention候选、采样地址、K/V流量回归；现有实际Issue95源仍保留；Qwen3 head_dim128/Q宽4096/QK norm正确。
- 拒绝采样：逐一核对1152个头/层的128个有效输出，proposal=有效＋多1拒绝＋全零拒绝，逐行周期和阶段周期守恒；随机端点实际交付次数/bit与采样及筛选账本一致。并未把一次算法更新当作一个硬件周期。
- 不确定：GU定点系数/舍入与FP32参考的数值对齐；新增NL源及全局seed接合；全宽权重保持电路；4/7桶完整阵列、恢复、ROM、64bit转换等STA/PPA。均标宏并列未知动作，没有按零成本处理。
- DRAM：本次使用明确标注的link后端，并非新DRAMSys/DRAMPower命令级结果。原bridge接口未改。
- 完整能耗和面积仍为null。已有价格小计覆盖范围不同，不能比较它来宣布节能倍数；不新增或继承PPL。

源码/配置：各run的EXECUTION.json固定代码提交与逐文件SHA；RESULT.json含精确配置、阶段、活动、流量和局部状态；MANIFEST.json封存原字节。make_report.py重新验证这些SHA后生成本表。第一次精简checkout遗漏rng_reference测试依赖导致1项失败，补齐后74项通过，失败日志UNITTEST.txt保留。
'''
(ROOT/'architecture_tlm/unified_v6/RESULTS_CURRENT_ZH.md').write_bytes(text.encode())
print('verified',len(rows),'complete decoders;',len(sensitivity['rows']),'FFNs;',len(sensitivity['seed_checks']),'seed fixtures')
