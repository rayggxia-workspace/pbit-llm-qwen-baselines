"""Summarize all12 sealed Qwen cases, keeping head boundary and power explicit."""
from pathlib import Path
from collections import defaultdict
import csv,hashlib,json,math,statistics

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
INPUT=ROOT/'work/rayggxia/245/mainline_20261108/qwen_comparison_20261109/DERIVED_INPUT.json'
x=json.loads(INPUT.read_bytes());assert x['status']=='QWEN12_FULL_CASES_SEALED_AND_VERIFIED'
groups=defaultdict(list)
for r in x['rows']:groups[r['clock_MHz'],r['scheme']].append(r)
rows=[];raw_phases=[]
for (clock,scheme),cases in sorted(groups.items()):
    n=3 if scheme=='SC_ising' else 1;assert len(cases)==n
    assert {r['seed'] for r in cases}==({17,503,1009} if n==3 else {17})
    assert len({r['area55_mm2'] for r in cases})==1
    mean=lambda f:statistics.mean(f(r) for r in cases)
    base=dict(clock_MHz=clock,scheme=scheme,deployment_seeds=n,area55_mm2=cases[0]['area55_mm2'],
        FMA_lanes=(640 if clock==100 else 256) if scheme=='SC_ising' else cases[0]['area_allocation']['lanes'])
    for name,key in [('including_head','including_head'),('excluding_head_stage','excluding_head')]:
        T=mean(lambda r:r[key]['time_ms']);E=mean(lambda r:r[key]['system_mJ_by_pJbit']['4.0']);C=mean(lambda r:r[key]['onchip_mJ'])
        base[name]=dict(time_ms=T,tokens_per_s=1000/T,onchip_mJ=C,system4pJ_mJ=E,
            onchip_average_W=C/T,system_average_W=E/T,
            time_sample_SD_ms=statistics.stdev(r[key]['time_ms'] for r in cases) if n==3 else None,
            energy_sample_SD_mJ=statistics.stdev(r[key]['system_mJ_by_pJbit']['4.0'] for r in cases) if n==3 else None,
            system6p6_mJ=mean(lambda r:r[key]['system_mJ_by_pJbit']['6.6']),
            system8_mJ=mean(lambda r:r[key]['system_mJ_by_pJbit']['8.0']))
    base['lm_head_stage_ms']=mean(lambda r:r['lm_head_stage_ms'])
    assert math.isclose(base['including_head']['time_ms']-base['excluding_head_stage']['time_ms'],base['lm_head_stage_ms'],abs_tol=1e-9)
    base['phase_ms']={k:mean(lambda r:r['phase_totals_ns'].get(k,0))/1e6 for k in cases[0]['phase_totals_ns']}
    for r in cases:
        for k,v in r['phase_totals_ns'].items():raw_phases.append(dict(clock_MHz=clock,scheme=scheme,seed=r['seed'],stage=k,duration_ms=v/1e6))
    rows.append(base)
assert len(rows)==8
by={(r['clock_MHz'],r['scheme']):r for r in rows};ratios=[]
for clock in (100,250):
    sc=by[clock,'SC_ising']
    for control in ('BF16_dense','W8_dense','W8_screen'):
        d=by[clock,control]
        for boundary in ('including_head','excluding_head_stage'):
            a=sc[boundary];b=d[boundary]
            ratios.append(dict(clock_MHz=clock,control=control,boundary=boundary,
                speedup=b['time_ms']/a['time_ms'],onchip_energy_reduction_percent=100*(1-a['onchip_mJ']/b['onchip_mJ']),
                total_energy_reduction_percent=100*(1-a['system4pJ_mJ']/b['system4pJ_mJ']),
                average_power_change_percent=100*(a['system_average_W']/b['system_average_W']-1),
                digital_area_gap_percent=100*(d['area55_mm2']/sc['area55_mm2']-1)))
result=dict(status='QWEN_COMPLETED_SUBSET_ONLY_8_CONFIGS_12_EXECUTIONS',rows=rows,ratios=ratios,
    model=x['shape'],source_manifest_sha256=x['input_snapshot_manifest_sha256'],input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
    protocol='55nm-equivalent;nativeLPDDR-derived8533,B1,N2048;SC GU16/Wd32,K128/S64;W8 means FFN only',
    area='same upper budget;discreteFMA16allocations leave digital0.75--2.48%smaller;not exactarea or chipdie',
    head_exclusion='time/energy snapshot beforelmhead,reprice;keeps embedding,finalnorm,headprefetch already overlapped;physicalareaunchanged',
    quality='hardware workloads/reference addresses,not PPL/accuracy verification',
    price_limits=x['rows'][0]['boundary'],all36_complete_not_claimed=True,no_new_simulation=True)
def save(n,z):(HERE/n).write_bytes((json.dumps(z,ensure_ascii=False,indent=2)+'\n').encode())
save('SUMMARY.json',result)
flat=[]
for r in rows:
    for key in ('including_head','excluding_head_stage'):flat.append(dict(clock_MHz=r['clock_MHz'],scheme=r['scheme'],boundary=key,area55_mm2=r['area55_mm2'],deployment_seeds=r['deployment_seeds'],**r[key]))
for name,data in [('SUMMARY.csv',flat),('RATIOS.csv',ratios),('PHASE_TIME.csv',raw_phases)]:
    with (HERE/name).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)
lines=['# Qwen3-4B：55nm概率方案与近似等面积数字对照','',
 '2026-11-09，Issue245 / PR247，rayggxia。Qwen12/12已完整封存并核验；此处只汇总已完成Qwen，不宣称整个三模型36项全部结束。','',
 '**此前50.419ms/token包含lm_head。** 本对照批使用同一胶合源，概率250MHz三seed均值50.428ms；与225独立批的0.009ms及约0.343mJ差异主要来自显式动态数制访存/计价，不能混seed。','',
 '## 配置和比较边界','',
 'Qwen/Qwen3-4B，B1，2048上下文，36层和151936词表。SC随机FFN GU16/Wd32，SparQ r32/K128、Ising/PV S64；FFN W8。三个数字方案：全BF16＋稠密注意力、FFN W8＋稠密注意力、FFN W8＋相同SparQ候选后准确QK/Softmax/PV。W8的QKVO/lm_head仍BF16，非线性确定性；W8screen没有PV概率采样。','',
 '同频率使用相同外存/物理SRAM和总面积上限，按FMA16整切片分配数字池；数字实际小0.75%–2.48%，不强行补无效逻辑使面积完全相等。面积指声明覆盖的核心资源，非含PHY/pad/完整CTS/NoC的die。原工艺面积已按0.81折算一次。','',
 '100MHz采用SS角，250MHz FFN主要TT角、部分数字标量仍保留SS代理，不把跨频能量差归因于频率本身；新TT数字补测可后续重计价。native LPDDR-derived8533给出时序，外存能量另用4pJ/bit主情景，并列6.6/8敏感性，不是已标定DRAM状态功耗。','',
 '## 含lm_head：完整decode','',
 '|MHz|方案|面积mm²|ms/token|token/s|片上mJ/token|核心＋外存mJ/token|平均总W|','|---:|---|---:|---:|---:|---:|---:|---:|']
order=('SC_ising','BF16_dense','W8_dense','W8_screen');labels=dict(SC_ising='概率FFN＋概率Attention',BF16_dense='BF16稠密数字',W8_dense='W8稠密数字',W8_screen='W8＋SparQ准确PV')
for c in (100,250):
 for s in order:
    r=by[c,s];z=r['including_head'];lines.append('|%d|%s|%.3f|%.3f|%.2f|%.3f|%.3f|%.3f|'%(c,labels[s],r['area55_mm2'],z['time_ms'],z['tokens_per_s'],z['onchip_mJ'],z['system4pJ_mJ'],z['system_average_W']))
lines+=['','## 去掉lm_head阶段','',
 '直接使用运行期间final_norm完成瞬间保存的时间、动作和存储计数，再按同价卡计能量；不是按权重占比估算。**保留embedding、final norm和此前已与FFN重叠发出的少量head预取，不是重新运行“删除head硬件”的系统。物理面积保持不变。**','',
 '|MHz|方案|去head ms/token|去head片上mJ|去head核心＋外存mJ|去head平均总W|','|---:|---|---:|---:|---:|---:|']
for c in (100,250):
 for s in order:
    r=by[c,s];z=r['excluding_head_stage'];lines.append('|%d|%s|%.3f|%.3f|%.3f|%.3f|'%(c,labels[s],z['time_ms'],z['onchip_mJ'],z['system4pJ_mJ'],z['system_average_W']))
lines+=['','## 概率方案相对数字对照','',
 '|MHz|对照|边界|速度倍率|片上能量降低|含外存能量降低|数字面积差|','|---:|---|---|---:|---:|---:|---:|']
for r in ratios:lines.append('|%d|%s|%s|%.3f×|%.2f%%|%.2f%%|%.2f%%|'%(r['clock_MHz'],labels[r['control']],'含head' if r['boundary']=='including_head' else '去head',r['speedup'],r['onchip_energy_reduction_percent'],r['total_energy_reduction_percent'],r['digital_area_gap_percent']))
lines+=['','## 差距主要在哪里','',
 '|MHz|方案|QKV＋O ms|FFN阶段ms|Attention阶段ms|head ms|','|---:|---|---:|---:|---:|---:|']
for c in (100,250):
 for s in order:
    r=by[c,s];p=r['phase_ms'];f=p.get('digital_FFN',p.get('GU',0)+p.get('NL_Wd',0));lines.append('|%d|%s|%.3f|%.3f|%.3f|%.3f|'%(c,labels[s],p.get('QKV',0)+p.get('O',0),f,p.get('attention',0),p.get('lm_head',0)))
lines+=['',
 '本模型中，FFN阶段是速度差距主要来源；对稠密Attention另有采样/筛选收益。各阶段包含其访存等待，不能当纯算术活动时间。QKVO没有统一加速，有些数字配置投影反而更快；数字池与FFN/Attention/FIFO分配的差别已保留，不按相同算子名假设完全相同时延。','',
 '概率方案的平均总功率W可高于较慢数字配置，但每token能量更低：E=P平均×T，较快完成时外存传输更集中。不能把较低mJ/token写成始终较低平均/峰值W。外存未改且占比大，因此片上约30%–60%的节能，包含外存后可能只有约5%–40%。','',
 '这是当前有限bank/DMA/共享池与已声明代理成本下的条件架构比较，不是对所有最优数字ASIC的普遍结论，也没有本次对应PPL/准确率对等验证。数字250标量/转换部分仍待同PVT补测，物理接口和全片后布局未闭合。三SC seed为部署参考地址seed，不是三训练seed或真实文本开关活动统计。','',
 '## 证据与恢复','',
 'DERIVED_INPUT保存12项远端文件路径、原字节SHA、分阶段与价卡边界；输入snapshot manifest为'+x['input_snapshot_manifest_sha256']+'。SUMMARY/CSV和RATIOS可复算，PHASE_TIME保留各seed原阶段。收集器只读远端封存，不改任何运行源或启动新TLM/PPL。完整36汇总仍由原严格聚合器验收，不因Qwen完成而绕过其余模型门禁。','',
 '运行summarize.py与verify.py；发布见本任务qwen_comparison_20261109/PUBLICATION.json。PR247未合并，Projects待维护者同步。']
(HERE/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
save('SOURCE_INDEX.json',dict(input_path=str(INPUT),input_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_manifest_sha256=x['input_snapshot_manifest_sha256'],
    remote_results=[dict(index=r['index'],remote=r['remote_folder'],files_sha256=r['files_sha256']) for r in x['rows']]))
print(json.dumps(dict(configurations=len(rows),executions=len(x['rows']),comparisons=len(ratios))))
