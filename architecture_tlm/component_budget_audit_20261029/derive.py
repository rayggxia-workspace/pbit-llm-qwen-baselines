"""Issue210: audit existing immutable budgets; no new TLM or hardware run."""
import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics as stats

BASE = '787489192ebfcdb61ad72edde406818f450aa3dc'
SOURCE = '91f68416acad0e8306b920b1b8ac779f3d24ad98'
SCENARIO = 'counter_ICG_plus_digital_gate_candidate'
AREA_SCALE = .81

LABELS = {
 'FFN_counter':'FFN权重门控 符号 档位对齐 合并计数',
 'FFN_postscale_restore_proxy':'FFN公共系数与数值恢复代理',
 'ordinary_BF16_MACs':'共享数字MAC阵列 QKV Wo QK 筛选 lm_head',
 'PV_vector_adders':'PV选择后的向量累加器',
 'wide_partial_activity_proxy':'FFN跨tile宽部分和活动代理',
 'shared_SRAM':'共享SRAM 8MiB',
 'local_CIM_SRAM_base':'FFN本地驻留权重SRAM 双bank',
 'digital_local_buffers':'数字本地权重与激活缓冲',
 'DMA_response_buffers':'DMA响应缓冲 数字与FFN共同使用',
 'FFN_shared64_input_frontend':'FFN入口共享随机源 比较器与分发',
 'FFN_nonlinear_10_local_PRNG_endpoints':'FFN非线性10个Bivium比较端点',
 'Attention_existing_PRNG_endpoints':'Attention原有8个Bivium端点',
 'FFN_and_selector_sigmoid_tables':'FFN及筛选器sigmoid查表',
 'other_vector_and_nonlinear_proxy':'其余向量与非线性旧单价代理',
}

def load(p):
 return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 return hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b):
 return math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-14)
def mean(xs):
 return stats.mean(xs)
def save_json(p,v):
 p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def save_csv(p,rows):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def md_table(headers,rows):
 def cell(x):return str(x).replace('|','／').replace('\n','；')
 return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+
                  ['| '+' | '.join(cell(x) for x in r)+' |' for r in rows])

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--repo',type=Path,required=True)
 ap.add_argument('--out',type=Path,required=True)
 args=ap.parse_args();repo=args.repo.resolve();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
 root=repo/'architecture_tlm';src=root/'ppa_recalibration_20261027'
 r=load(src/'RESULTS.json');anchors=load(src/'ANCHORS.json')
 assert sha(src/'ANCHORS.json')==r['anchors_sha256']
 assert sha(src/'rebudget.py')==r['code_sha256']
 spec=importlib.util.spec_from_file_location('original_rebudget',src/'rebudget.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 evidence={};checks=[]
 def register(p):
  evidence[p.relative_to(repo).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
 for p in [src/'RESULTS.json',src/'ANCHORS.json',src/'rebudget.py',src/'RESULTS_ZH.md']:
  register(p)
 all_summaries={}
 for item in r['inputs']:
  p=repo/item['path'];manifest=load(p.with_name('MANIFEST.json'));execution=load(p.with_name('EXECUTION.json'))
  assert manifest['status']=='completed'
  assert sha(p)==item['sha256']==manifest['files']['RESULT_SUMMARY.json']['sha256']
  assert execution['config_sha256']==item['config_sha256']
  s=load(p);assert s['raw_result_sha256']==item['raw_result_sha256']
  assert s['execution_commit']==item['execution']
  all_summaries[item['path']]=s
  for q in [p,p.with_name('MANIFEST.json'),p.with_name('EXECUTION.json')]:register(q)
 checks.append({'check':'six_completed_summaries_and_manifest_configuration_references','passed':len(all_summaries)==6})
 for case in r['cases']:
  s=all_summaries[case['input']['path']]
  for key,cg,dg in [('new_counter_CE',False,False),('counter_real_ICG',True,False),(SCENARIO,True,True)]:
   assert module.estimate(s,anchors,counter_gate=cg,digital_gate=dg)==case['rows'][key]
 checks.append({'check':'all_4_cases_times_3_original_budget_scenarios_reproduced_exactly','passed':True})
 cases=r['cases'][1:]
 summaries=[all_summaries[c['input']['path']] for c in cases]
 assert [s['config']['seed'] for s in summaries]==[0,1,2]
 for s in summaries:
  assert s['model']['num_hidden_layers']==36 and s['config']['context_tokens']==2048
  assert s['config']['decode_tokens']==1 and s['config']['core_hz']==500_000_000
  assert s['config']['attention']['mode']=='screen_pv'
  assert s['config']['ffn']['samples']==64 and s['config']['ffn']['nonlinear_samples']==128
 rows=[c['rows'][SCENARIO] for c in cases]
 t=mean(x['elapsed_s'] for x in rows)
 total=mean(x['covered_onchip_J'] for x in rows)
 external=mean(x['legacy_external_budget_J'] for x in rows)
 area_raw=mean(x['covered_area_mm2'] for x in rows)
 ms=t*1e3
 module_rows=[]
 for name,label in LABELS.items():
  orig=[next(v for v in x['modules'] if v['module']==name) for x in rows]
  e=mean(v['energy_J'] for v in orig)
  area=mean(v.get('area_mm2',0) for v in orig) if all('area_mm2' in v for v in orig) else None
  d={'module':name,'label_zh':label,'energy_mJ_per_token':e*1e3,'average_power_W':e/t,
     'onchip_energy_share_pct':100*e/total,'conditional_system_energy_share_pct':100*e/(total+external),
     'raw_priced_area_mm2':area,'equivalent_55nm_area_mm2':None if area is None else area*.81,
     'priced_area_share_pct':None if area is None else 100*area/area_raw,
     'evidence':orig[0]['evidence']}
  for k in ['leakage_J','idle_clock_background_J','work_increment_J','internal_dynamic_J']:
   d[k]=mean(v[k] for v in orig) if all(k in v for v in orig) else None
  module_rows.append(d)
 assert close(sum(x['energy_mJ_per_token'] for x in module_rows),total*1e3)
 assert close(sum(x['raw_priced_area_mm2'] or 0 for x in module_rows),area_raw)
 assert close(sum(x['onchip_energy_share_pct'] for x in module_rows),100)
 assert close(sum(x['priced_area_share_pct'] or 0 for x in module_rows),100)
 checks.append({'check':'14_physical_account_rows_close_energy_area_and_percent_to_original_totals','passed':True})
 m=module_rows
 groups=[('FFN计数与恢复',[0,1,4]),('共享普通数字MAC',[2]),('PV累加器',[3]),('所有片上SRAM和缓冲',[5,6,7,8]),('FFN随机前端和NL端点',[9,10]),('Attention随机端点',[11]),('sigmoid与其余向量代理',[12,13])]
 group_rows=[]
 for label,idx in groups:
  e=sum(m[i]['energy_mJ_per_token'] for i in idx);a=sum(m[i]['equivalent_55nm_area_mm2'] or 0 for i in idx)
  group_rows.append(dict(group=label,energy_mJ_per_token=e,average_power_W=e/ms,onchip_energy_share_pct=e/(total*10),
      equivalent_55nm_area_mm2=a,priced_area_share_pct=100*a/(area_raw*.81)))
 phase_names=list(summaries[0]['phase_ns'])
 phase_rows=[]
 for name in phase_names:
  value=mean(s['phase_ns'][name] for s in summaries)
  phase_rows.append(dict(phase=name,elapsed_ms=value/1e6,elapsed_share_pct=value/(t*1e7)))
 assert close(sum(x['elapsed_ms'] for x in phase_rows),ms)
 checks.append({'check':'sequential_phases_sum_to_3_seed_mean_TPOT','passed':True})
 pmap={x['phase']:x['elapsed_ms'] for x in phase_rows}
 coarse=[('FFN含输出转换与残差',['FFN_gate_up','FFN_nonlinear_encoding','FFN_AND_direct_down','ffn_output_conversion','ffn_residual']),
         ('QKV与O投影',['QKV_projection','O_projection']),('Attention核心',['attention_core']),('lm_head与argmax',['lm_head_and_argmax'])]
 phase_groups=[];used=set()
 for label,names in coarse:
  v=sum(pmap[n] for n in names);used.update(names)
  phase_groups.append(dict(phase=label,elapsed_ms=v,elapsed_share_pct=v/ms*100))
 v=sum(v for k,v in pmap.items() if k not in used)
 phase_groups.append(dict(phase='其余归一化 RoPE 残差和显式存储',elapsed_ms=v,elapsed_share_pct=v/ms*100))
 service_groups={
  '外存DMA总资源':['@dram_dma'],'共享SRAM fabric':['@sram_fabric'],'普通数字MAC总资源':['@mac'],
  'FFN入口编码':['SC_fixed4_P8_encode'],'FFN GU采样与计数':['SC_locality_gu'],
  'FFN非线性编码与查表':['SC_fixed4_GU_P8_encode','SC_true_g_signed8','SC_sigmoid_ROM9','SC_sign_and_exponent_sum'],
  'FFN AND直连Wd采样与计数':['SC_locality_down'],
  'FFN权重与系数编程':['SC_local_weight_program','SC_local_coefficient_program'],
  'FFN旧恢复宏':['SC_bucket_shift_reduce','SC_coefficient16_restore'],
  'FFN宽部分和更新':['locality_partial_clear','locality_accumulator_update'],
  '数制转换 数字矩阵输出及FFN输出':['matrix_FP32_to_BF16','SC_wide_RNE_BF16'],
  'Attention QKV投影算术':['matrix_qkv'],'Attention O投影算术':['matrix_o'],
  'RoPE算术':['RoPE_bias'],
  '摘要筛选算术':['summary_update','summary_mean','screen_Q_summary','screen_max4_normalize_sigmoid','fixed_candidate_budget_repair'],
  '筛选摘要存取':['dram_summary_update','dram_summary_read','sram_summary_fill','sram_summary_operand','sram_candidate_maps'],
  'K读入与片存搬运':['dram_K_selected','sram_KV_fill','sram_KV_operand'],
  'QK打分与缩放':['attention_QK','attention_score_scale'],
  '准确Softmax含输入输出SRAM':['accurate_softmax','sram_score_input','sram_probabilities'],
  'PV采样选址与GQA合并':['CDF_prefix','systematic_CDF_counts','sram_CDF_scan','sample_histogram_remap','sram_index_remap','sram_V_worklist','sram_GQA_worklist_merge','GQA_sorted_union'],
  'V外存读取 片存装载与广播':['dram_V_sparse_union','sram_V_fill','sram_V_broadcast'],
  'V选择累加与平均':['V_repeated_add','sample_average','sram_attention_output'],
  'Attention随机服务真实响应':['rng_selector_real_response','rng_PV_real_uniform32'],
  'lm_head算术与argmax':['matrix_lm_head','stream_argmax'],
 }
 service_rows=[]
 for label,names in service_groups.items():
  ns=mean(sum(s['resource_busy_ns'].get(n[1:],0) if n.startswith('@') else s['stage_busy_ns'].get(n,0) for n in names) for s in summaries)
  service_rows.append(dict(service=label,service_busy_ms=ns/1e6,over_TPOT_pct=ns/(t*1e7),
      interpretation='resource busy time' if names[0].startswith('@') else 'sum of named stage reservations; may overlap other rows',source_stages=';'.join(names)))
 assert all(x['service_busy_ms']>=0 for x in service_rows)
 # Exact projection arithmetic follows the recorded shape and candidate counts.
 shape=summaries[0]['model'];L=shape['num_hidden_layers'];H=shape['num_attention_heads'];D=shape['head_dim'];KV=shape['num_key_value_heads'];hidden=shape['hidden_size']
 counts={'QKV投影':L*hidden*(H+2*KV)*D,'O投影':L*H*D*hidden,'lm_head':hidden*shape['vocab_size'],
         '候选QK点积':mean(s['attention_activity']['QK_logical_positions']*D for s in summaries),
         'Q与K摘要点积':L*H*math.ceil(2048/16)*D}
 assert all(close(sum(counts.values()),s['actions']['bf16_mac']) for s in summaries)
 macrow=next(x for x in m if x['module']=='ordinary_BF16_MACs')
 mac_work=macrow['work_increment_J'];mac_background=macrow['energy_mJ_per_token']/1e3-mac_work
 functional_mac=[dict(function=k,MACs=v,work_increment_mJ=mac_work*v/sum(counts.values())*1e3,
                     area='共享2048路MAC，不独立累加面积',background='共享MAC背景单列，未分摊到本行') for k,v in counts.items()]
 checks.append({'check':'5_semantic_MAC_counts_close_to_exact_recorded_bf16_MAC_total','passed':True})
 # Attribute original external-byte proxy by existing tagged transactions.
 traffic_keys=[k for k in summaries[0]['DRAM']['traffic'] if k.endswith('_physical_bytes')]
 traffic=[]
 for k in traffic_keys:
  n=mean(s['DRAM']['traffic'].get(k,0) for s in summaries)
  traffic.append(dict(kind=k,physical_bytes=n,MiB=n/(2**20),legacy_proxy_mJ=n*64e-9))
 total_bytes=mean(s['actions']['dram_read']+s['actions'].get('dram_write',0) for s in summaries)
 assert close(sum(x['physical_bytes'] for x in traffic),total_bytes)
 assert close(sum(x['legacy_proxy_mJ'] for x in traffic)+.05*ms,external*1e3)
 checks.append({'check':'external_tagged_physical_bytes_close_to_64pJ_per_byte_plus_50mW_proxy','passed':True})
 mem_rows=[]
 for label,capacity in [('共享SRAM',summaries[0]['SRAM']['configured_bytes']),('FFN权重双bank',summaries[0]['FFN_contract']['local_state']['weight_hold_bytes']),('数字本地operand与激活',summaries[0]['digital_operand_contract']['operand_capacity_bytes']+summaries[0]['digital_operand_contract']['activation_peak_bytes']),('DMA响应缓冲',summaries[0]['tile_pipeline']['shared_response_capacity_bytes'])]:
  mem_rows.append(dict(memory=label,capacity_bytes=capacity,capacity_KiB=capacity/1024))
 actual_service={x['service']:x['service_busy_ms'] for x in service_rows}
 gap_rows=[
  dict(function='FFN入口随机源与64比较器',status='合并计价',energy_account='FFN_shared64_input_frontend',area_account='同一合并模块',time_ms=actual_service['FFN GU采样与计数'],note='原价含LFSR、比较器及分发；不能凭纯比较器价格强行减拆。GU服务时间与计数器重叠。'),
  dict(function='FFN非线性随机源与192路比较',status='合并计价',energy_account='FFN_nonlinear_10_local_PRNG_endpoints',area_account='10端点共享',time_ms=actual_service['FFN AND直连Wd采样与计数'],note='每端点20比较器，200路容量覆盖192路；含随机与比较不再叠加三路比较费用。与Wd采样重叠。'),
  dict(function='FFN输入与g/u定点编码',status='有动作和时间，独立PPA缺失',energy_account=None,area_account=None,time_ms=actual_service['FFN入口编码']+mean(s['stage_busy_ns']['SC_fixed4_GU_P8_encode'] for s in summaries)/1e6,note='x 92160值，g/u 700416值；不能因已计比较器就认为编码也收费。'),
  dict(function='真正g的signed8编码',status='有时间，独立PPA缺失',energy_account=None,area_account=None,time_ms=mean(s['stage_busy_ns']['SC_true_g_signed8'] for s in summaries)/1e6,note='350208值；真实g驱动sigmoid，不等于分档后的概率码直接入sigmoid。'),
  dict(function='FP32或宽定点转BF16',status='有时间，独立PPA缺失',energy_account=None,area_account=None,time_ms=actual_service['数制转换 数字矩阵输出及FFN输出'],note='数字矩阵313344值，FFN最终92160值；原表未为这两类转换独立定价。'),
  dict(function='三路AND本体与符号指数恢复',status='部分并入计算核，未独立闭合',energy_account='counter及restore已含部分门控；额外AND控制缺独立PPA',area_account=None,time_ms=None,note='179306496次两输入AND仅为动作；不能把整个非线性视为只付sigmoid LUT的能量。'),
  dict(function='RoPE与RMSNorm',status='旧向量非线性代理',energy_account='other_vector_and_nonlinear_proxy',area_account=None,time_ms=actual_service['RoPE算术'],note='RoPE、范数、指数与倒数没有完整同工艺阵列PPA。'),
  dict(function='筛选器',status='摘要点积加概率保留与固定预算修整',energy_account='MAC增量+Attention随机端+旧向量代理',area_account='共享MAC及随机端',time_ms=actual_service['摘要筛选算术'],note='不是耦合Ising退火；candidate_compact等控制未独立定价。'),
  dict(function='Ising Softmax',status='本锚点未启用',energy_account=None,area_account=None,time_ms=None,note='screen_pv实际执行准确Softmax；不能从原2.516W拆出Ising，也不能把未启用理解为物理电路零成本。'),
  dict(function='V读取',status='字节与时间已记录，HBM能量仅粗预算',energy_account='外存64pJ/B代理+共享SRAM',area_account='共享存储；HBM控制器和PHY未价',time_ms=actual_service['V外存读取 片存装载与广播'],note='GQA去重后真实物理读取，不能按每头样本数重复读或把面积重复分摊。'),
 ]
 uncertainty=[
  '数字门控90%空闲动态消除是情景，不是实测2048路门控阵列。',
  '100MHz电路动态能量/参考拍固定，向500MHz外推；未证明500MHz完整STA。',
  'B7计数按B4位数比例，宽部分和和旧恢复为代理；并非完整集成测量。',
  '定制CIM全并行读出、广播、mux、端口、CTS和控制未闭合。',
  '外存采用HBM时序，但64pJ/B+50mW来自旧粗预算，不是有效HBM DRAMPower表征。',
  '部分数制转换和控制有时间/动作而未独立定价，已计价小计不等于完整芯片总能耗或面积。',
 ]
 result=dict(schema_version=1,issue=210,base_commit=BASE,source_tlm_branch_head=SOURCE,
   scenario=SCENARIO,scope='已有36层Qwen3-4B形状/B1/2K单token decode三seed预算派生，无新时序/PPL/EDA',
   totals=dict(TPOT_ms=ms,onchip_mJ=total*1e3,onchip_W_common_mean_TPOT=total/t,
      old_mean_of_seed_onchip_W=mean(x['covered_onchip_W'] for x in rows),raw_priced_area_mm2=area_raw,
      equivalent_55nm_priced_area_mm2=area_raw*.81,area_scale_once=.81,
      external_proxy_mJ=external*1e3,external_proxy_W=external/t,
      conditional_system_proxy_mJ=(total+external)*1e3,conditional_system_proxy_W=(total+external)/t,
      full_calibrated_system_power=None,full_calibrated_system_area=None),
   original_scenarios=r['optimized_three_seed_means'],hardware_modules=m,coarse_groups=group_rows,
   sequential_phases=phase_rows,sequential_phase_groups=phase_groups,overlapping_service_busy_times=service_rows,
   functional_MAC_work=functional_mac,shared_MAC_background_mJ=mac_background*1e3,
   shared_MAC_utilization_pct=sum(counts.values())/(2048*500_000_000*t)*100,
   external_traffic_proxy=traffic,memory_capacity=mem_rows,
   shared_SRAM_explicit_reserved_peak_bytes=summaries[0]['SRAM']['reserved_peak_bytes'],
   requested_function_accounting_gaps=gap_rows,
   attention_activity_mean={k:mean(s['attention_activity'][k] for s in summaries) for k in summaries[0]['attention_activity']},
   original_unpriced_action_counts_mean={k:mean(s['unpriced_actions'].get(k,0) for s in summaries) for k in summaries[0]['unpriced_actions']},
   bounds=uncertainty,source_manifest=evidence,checks=checks,
   models_and_corpus_sha='不适用：形状与合成事务预算，未载入真实权重或进行PPL')
 save_json(out/'BREAKDOWN.json',result)
 save_json(out/'SOURCE_MANIFEST.json',dict(base_commit=BASE,source_commit=SOURCE,inputs=evidence,checks=checks))
 for filename,table in [('MODULES.csv',m),('PHASES.csv',phase_rows),('SERVICE_BUSY.csv',service_rows),('FUNCTIONAL_MAC.csv',functional_mac),('DRAM_TRAFFIC.csv',traffic),('ACCOUNTING_GAPS.csv',gap_rows)]:save_csv(out/filename,table)
 lines=['# 原整机TLM功耗 面积与时间分项审计','',
  f'Issue210；主线基线 `{BASE}`；科学锚点PR192@`{SOURCE}`。不修改原模型、调度或电路结果。',
  '', '## 一眼看结果','',
  f'本报告对应后训练Qwen3-4B形状、36层、batch1、2K上下文、单个decode token、500MHz目标、32个64×64随机阵列、2048 MAC/拍、GU64/NL128、8MiB SRAM与HBM时序。Attention为筛选＋准确Softmax＋PV系统采样，**不是Ising**。不含prefill，不加载真实模型权重，不继承PPL。',
  '',f'三seed平均时间 **{ms:.6f}ms/token**；已计价片上能量 **{total*1e3:.6f}mJ/token**、平均 **{total/t:.6f}W**；已计价面积原值 **{area_raw:.6f}mm²**、按0.81折算 **{area_raw*.81:.6f}mm²**。完整物理总值仍未知。',
  '',f'外存旧粗预算另外为 **{external*1e3:.6f}mJ/token、{external/t:.6f}W**；加总 **{(total+external)*1e3:.6f}mJ/token、{(total+external)/t:.6f}W**。这是64pJ/B＋50mW情景，不能称HBM实测。',
  '',md_table(['片上类别','mJ/token','平均W','片上能耗占比','55nm面积mm²','已价面积占比'],[[g['group'],f"{g['energy_mJ_per_token']:.4f}",f"{g['average_power_W']:.6f}",f"{g['onchip_energy_share_pct']:.3f}%",f"{g['equivalent_55nm_area_mm2']:.6f}",f"{g['priced_area_share_pct']:.3f}%"] for g in group_rows]),
  '', '功率一律用同一三seed平均TPOT换算，故功率占比等于能量占比。不能把局部工作期间活动功率除整机平均功率来算占比。面积按共享硬件计一次，不按36层重复复制。',
  '', '## 原始预算的三个门控情景','',
  md_table(['情景','片上W','片上mJ/token','含旧外存代理W'],[[k,f"{v['covered_onchip_W']:.6f}",f"{v['covered_onchip_J']*1e3:.6f}",f"{v['conditional_budget_with_legacy_external_W']:.6f}"] for k,v in r['optimized_three_seed_means'].items()]),
  '', '2.516W这一列已经采用数字单元减少90%空闲动态的假设。原封存时序没有重新加入数字门控唤醒延迟；它是保持原时间的能耗敏感性，不是新门控整机执行。',
  '', '## 每个物理计价模块','',
  md_table(['模块','mJ/token','平均W','片上占比','raw面积mm²','55nm面积mm²'],[[x['label_zh'],f"{x['energy_mJ_per_token']:.6f}",f"{x['average_power_W']:.9f}",f"{x['onchip_energy_share_pct']:.5f}%",'未独立价' if x['raw_priced_area_mm2'] is None else f"{x['raw_priced_area_mm2']:.8f}",'未独立价' if x['equivalent_55nm_area_mm2'] is None else f"{x['equivalent_55nm_area_mm2']:.8f}"] for x in m]),
  '', '以上14行能量和已价面积分别闭合到原结果。CSV另含面积占比与“含外存代理”分母下的占比。未独立计价不等于面积为零；不能据小计排除缺项。',
  '', '## 时间占比与可重叠忙时','',
  md_table(['串行阶段','ms/token','总时间占比'],[[x['phase'],f"{x['elapsed_ms']:.6f}",f"{x['elapsed_share_pct']:.3f}%"] for x in phase_groups]),
  '', '这一张阶段表可以相加得到整token时间；它包含供数、排队与存储等待。下一张是实际预约的服务忙时，跨行存在重叠，**不可相加成TPOT，也不是减少该项就能同比减少的关键路径时间**。',
  '',md_table(['模块服务或资源','忙时ms','相对TPOT','说明'],[[x['service'],f"{x['service_busy_ms']:.6f}",f"{x['over_TPOT_pct']:.3f}%",x['interpretation']] for x in service_rows]),
  '', '原时间模型仍保留旧分桶归约与系数恢复宏，而能量后处理已经换用合并计数器并排除重复的七桶能量。因此旧恢复忙时不能再用于追加一套七桶面积或能量；这是下一轮集成需要对齐的边界。',
  '', '## 用户关心的功能逐项对应','',
  md_table(['功能','原预算状态','时间或费用对应','说明'],[[x['function'],x['status'],str(x['energy_account'] or '独立能量未知')+(f"；忙时{x['time_ms']:.6f}ms" if x['time_ms'] is not None else ''),x['note']] for x in gap_rows]),
  '', '### FFN随机源与比较器','',
  'GU入口是一个共享64路前端，原价同时包含本地LFSR、64比较器和分发。NL按10个Bivium完整端点收费，200个原生比较通道覆盖192路消费。两个合并价格无法从旧整机账本精确拆出PRNG与比较器各自占比；已测纯比较器价格只能作为独立优化参考，不能强行相减产生“实测分项”。本锚点固定W8，不包含新双随机W侧SNG。',
  '', '非线性g/u编码、真实g驱动、sigmoid查表、三路比较/AND和Wd计数构成一条路径。不能把LUT一行的微小能量当作整个随机SwiGLU能量。FFN计数核含权重门控、符号、档位对齐、归约和时间累计，不再追加同功能门费。',
  '', '### QKV O投影 QK与lm_head','',
  md_table(['功能','MAC次数','仅有效计算增量mJ','面积与背景'],[[x['function'],f"{x['MACs']:,.0f}",f"{x['work_increment_mJ']:.6f}",'共享MAC，背景另列'] for x in functional_mac]),
  '',f'五项精确合计到原记录的{sum(counts.values()):,.0f}次MAC。共享MAC有效增量仅 **{mac_work*1e3:.6f}mJ**，其余背景动态和漏电 **{mac_background*1e3:.6f}mJ**；背景动态也包含工作期间基底。实际MAC利用率约 **{result["shared_MAC_utilization_pct"]:.3f}%**。面积不能分别给QKV、O和lm_head各加一套。',
  '', '### 筛选 Softmax和V读取','',
  '筛选流程是16token子摘要读取/平均、Q与摘要点积、max4归一化和sigmoid保留、固定候选预算修整。它不是真正耦合p-bit网络退火。本锚点之后准确Softmax，再用系统采样偏移、CDF计数、重复次数保持与GQA地址并集读取V。',
  '', '准确Softmax的exp/倒数等仍是旧向量/非线性动作代理，完整物理PPA没有闭环。Ising在该整机结果中未启用，原2.516W和57.445ms不能提供Ising占比。Issue198的新阈值/RNG/拒绝控制只能独立列增量，不能和这组原时序直接拼成已验证新整机。',
  '', '## 存储容量与外存粗预算','',
  md_table(['物理存储','容量KiB'],[[x['memory'],f"{x['capacity_KiB']:.1f}"] for x in mem_rows]),
  '',f'共享SRAM配置8MiB，原表显式地址空间保留峰值为{summaries[0]["SRAM"]["reserved_peak_bytes"]:,}B（约{summaries[0]["SRAM"]["reserved_peak_bytes"]/(2**20):.3f}MiB）；这不包含上表单独计价的本地和响应缓冲。缩小容量可能同时影响bank数与带宽，不能免费保留原供数能力。FFN权重只按编程写入和保持计，未按每个采样拍重新收取完整普通SRAM读费；CIM全并行读出外围仍缺价。',
  '',md_table(['外存事务','物理MiB/token','旧64pJ/B代理mJ'],[[x['kind'],f"{x['MiB']:.4f}",f"{x['legacy_proxy_mJ']:.5f}"] for x in traffic]),
  '',f'上述外存动作之和另加50mW×TPOT={.05*ms:.6f}mJ，闭合到旧外存代理{external*1e3:.6f}mJ。weights行同时含普通投影和FFN权重；FFN权重约{summaries[0]["actions"]["SC_local_weight_program_byte"]/(2**30):.3f}GiB，普通矩阵权重约{summaries[0]["actions"]["digital_local_operand_write_byte"]/(2**30):.3f}GiB。HBM控制器、PHY和封装面积没有计入片上面积表。',
  '', '## 优化时优先看什么','',
  '1. 能量先看共享MAC背景、FFN计数器和外存模型；先确认数字门控、500MHz及HBM单价，避免优化一个已被低估的小项却忽略主项。',
  '2. 面积先看计数器和共享SRAM；以原位宽/并行度/吞吐为对照，不能把新OR4或双随机小核无条件替代旧多档精确计数。',
  '3. 时间先看供数和FFN全阶段：普通MAC实际忙时远小于投影阶段总时间，单纯增加MAC未必减少等待；DMA、SRAM与计算忙时不可直接相加。',
  '4. 编码和格式转换虽然不是旧表大项，但其中部分没有独立价格，应先补齐再谈占比；随机源与比较器拆价也需要匹配集成边界。',
  '', '## 未闭合项与复算入口','']+['- '+x for x in uncertainty]+[
  '', '`BREAKDOWN.json`保存完整数值；`MODULES.csv`是物理模块能量/面积表，`PHASES.csv`是可相加的阶段时间，`SERVICE_BUSY.csv`是不可相加的资源忙时。`FUNCTIONAL_MAC.csv`、`DRAM_TRAFFIC.csv`、`ACCOUNTING_GAPS.csv`分别对应功能增量、外存和缺项。',
  '', f'复算：`python derive.py --repo <本任务checkout> --out <新目录>`。六个completed摘要原字节SHA及其manifest、配置引用、定价代码和anchors均已核对；raw结果SHA仅核对封存引用一致，未重新下载大轨迹或门级原件。四配置×三情景逐字典复算一致。文件证据见`SOURCE_MANIFEST.json`。模型/语料SHA不适用，因为没有执行数值模型。',
  '', '当前主线仍为PR190共同调度默认；本报告采用PR192扩容候选的已有预算，不能把其资源、门控或HBM假设说成默认。后续本地端口优化仅有单层＋词表结果，不冒称已经重跑36层新PPA。',
  '', '[原预算](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/'+SOURCE+'/architecture_tlm/ppa_recalibration_20261027/RESULTS_ZH.md) · [原调度](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/blob/'+SOURCE+'/architecture_tlm/scheduling_v2_20261027/FINAL_RESULTS_ZH.md) · [Issue210](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/210)',
 ]
 (out/'REPORT_ZH.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({'status':'passed','totals':result['totals'],'checks':checks,'output':str(out)},ensure_ascii=False))

if __name__=='__main__':main()
