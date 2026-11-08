"""Small measured-front sensitivity;no reprice or rerun of existing TLM."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
OUT=ROOT/'architecture_tlm/module_handoff/attention_score_front_compare_20261108/local_integration_A'
source=PROJECT/'architecture_tlm/module_handoff/attention_score_front_ppa_20261108/TLM_PROFILE.json'
profile=json.loads(source.read_bytes())
diag=PROJECT/'tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108/revision2/FAILURE_DIAG.json'
completed=json.loads(diag.read_bytes())['completed'];rows=[];queries=36*32
for clock,instances,read_pJ in [(100,8,10.0527),(250,4,12.0293)]:
 a=profile[str(clock)]['s12_max_gap']
 ref=next(x for x in completed if x['clock']==clock and x['scheme']=='SC_ising' and x['path'].endswith('s17'))
 area=instances*a['area55_mm2'];work_mJ=queries*a['gross_query_nJ']/1e6
 sram_mJ=queries*a['input_score_read_words16']*read_pJ/1e9
 serial_ms=queries*a['query_cycles']*(1000/clock)/1e6
 gated_mJ=instances*a['root_off_inputs_stable_mW']*ref['time_ms']/1000
 always_work_mJ=instances*a['active_average_mW']*ref['time_ms']/1000+sram_mJ
 rows.append(dict(clock_MHz=clock,model='Qwen3-4B',heads=32,layers=36,queries=queries,
  physical_instances_in_current_accounting=instances,reference=ref,
  full_A_area_reserve_mm2=area,area_fraction_percent=100*area/ref['area'],
  full_A_once_activity_plus_input_SRAM_mJ=work_mJ+sram_mJ,
  gated_full_A_reserve_mJ=work_mJ+sram_mJ+gated_mJ,
  gated_reserve_fraction_percent=100*(work_mJ+sram_mJ+gated_mJ)/ref['system4pJ_mJ'],
  full_A_always_work_logic_stress_mW=instances*a['active_average_mW'],
  always_work_logic_stress_mJ=always_work_mJ,
  always_work_logic_stress_fraction_percent=100*always_work_mJ/ref['system4pJ_mJ'],
  full_A_serial_service_ms=serial_ms,serial_service_fraction_percent=100*serial_ms/ref['time_ms'],
  balanced_parallel_service_ms=serial_ms/instances,
  timing_note='service scenarios only;not an integrated latency bound;existing frontend already billed',
  energy_note='whole independentA used as a deliberatelylarge proxy;not physicalupperbound;do not add again to existingledger'))
result=dict(status='PROVISIONAL_USE_ALLOWED_WITH_DECLARED_FRONTEND_APPROXIMATION',rows=rows,
 existing_jobs_may_continue=True,completed_results_kept=True,restart_for_frontend_gap=False,
 default_TLM_source_unchanged=True,integrated_PPA_ready=False,
 numeric_frontend='S12 A PPL evidence;do not claim B numericalquality from A',
 cost_policy='keep current nonzero front reserve;report sensitivity separately,not another fullA charge',
 no_new_TLM_PPL_RTL_PT=True,
 sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,diag)})
(OUT/'PROVISIONAL_BUDGET.json').write_bytes((json.dumps(result,indent=2)+'\n').encode())
text='''# 前端未闭合增量：允许先沿用现有TLM

2026-11-08，用户明确：影响不大就先用，不因这个小模块重跑大量任务。

**当前四路FP32→S12转换/握手增量PPA的缺项，不应阻塞现有架构评估。** 已完成结果保留、健康任务继续；原冻结源码和输出不改，不为这项缺口重新训练或重跑完整PPL。当前前端已有非零宏预算，并非完全漏计。

## 量级核对

下表故意用“整个独立A前端”代表尚未拆出的转换/握手，给出偏大的敏感性情景，不是物理严格上界，也不再次加到现有账本。参考为本批已封存Qwen3-4B单seed完整token，100/250约54.208/50.425ms、194.492/198.713mJ；不是36case最终汇总。前端每头每层一次，共1152query，不乘S64。

|情景|100MHz，按8实例|250MHz，按4实例|
|---|---:|---:|
|整块A全部额外预留的面积|0.131731mm²|0.076112mm²|
|占当前覆盖面积|0.396%|0.345%|
|整块A始终按实测工作功率翻转的逻辑功率情景|2.173mW|4.511mW|
|上述逻辑压力情景＋每query一次输入读，占参考整机能量|约0.061%|约0.115%|
|将整个A全部额外串行安排的服务时间|0.7488ms|0.3087ms|
|按实例均匀分摊的服务量|0.0936ms|0.0772ms|

时间不是完整握手/回压重跑，也不是严格上界；真实转换/握手只是A的一部分，原模型也已经收取前端，所以不应把这些数值当作必须追加的开销。SRAM采用既有每16B读代理，具体待校准项继续单列。机读精确计算及源SHA见PROVISIONAL_BUDGET.json。

## 先用的明确口径

1. 既有运行作为“有限存储/队列/回压＋前端宏成本”的条件TLM结果继续使用；无需因前端价卡的小修正推翻已完成矩阵/访存回放。
2. 质量路径仍明确为A：S12/F4先量化→整数max/gap→U8/P8。若冻结模型采用较宽前端服务/代理成本配S12参考地址，必须保留这个组合标签，不能写成B已获A的完整PPL或整条链位真验收。
3. 暂时沿用现有前端预留，不额外完整叠加A。后续小价卡到齐后先替换动作/驻留单价；时序用少量配对阶段回放判断是否值得整机重跑。面积小修正暂不触发重新选择整套数字阵列。
4. integrated_sampler_replacement_ready仍为false，代表完整净差额未独立表征，不代表禁止宏级评估。功能/数值、时序估计、独立前端PT、全链PPA分别标状态。

此量级判断仅针对转换/握手和分数前端成本缺项，不把A/B算法分布变化、全部存储接口或物理全片未计项一并宣布很小。最终若要宣称低于百分之一级的细小优势，再在定稿时收紧对应误差。

本轮另外发现三项Llama100 SC在旧残差地址绑定处报错，与上述成本近似无关；已保留6个完整结果和健康worker，在独立快照修复大模型地址绑定，不增加SRAM容量。该类实际执行错误按失败恢复处理，不把“先用近似成本”当作忽略错误。
'''
(OUT/'PROVISIONAL_USE_ZH.md').write_bytes(text.encode())
mirror=PROJECT/OUT.relative_to(ROOT)
for n in ('PROVISIONAL_BUDGET.json','PROVISIONAL_USE_ZH.md'):
 assert not (mirror/n).exists();(mirror/n).write_bytes((OUT/n).read_bytes())
print(json.dumps(dict(status=result['status'],rows=[{k:r[k] for k in ('clock_MHz','full_A_area_reserve_mm2','area_fraction_percent','full_A_always_work_logic_stress_mW','always_work_logic_stress_fraction_percent','full_A_serial_service_ms')} for r in rows])))
