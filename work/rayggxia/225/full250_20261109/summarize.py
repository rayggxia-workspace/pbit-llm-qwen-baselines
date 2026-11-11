from pathlib import Path
from collections import Counter
import hashlib,json,statistics
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1]
load=lambda p:json.loads(Path(p).read_bytes())
collection=load(H/'COLLECTION.json');records=[]
for entry in collection['records']:
    if entry['case']=='pilot':continue
    paths=entry['files'];r=load(paths['RESULT.json']['local']);b=load(paths['BUDGET.json']['local'])
    for n,x in paths.items():assert hashlib.sha256(Path(x['local']).read_bytes()).hexdigest()==x['sha256']
    assert r['scope']=='full' and r['layers']==36 and r['head_probe_rows'] is None
    assert r['backend']=='native' and r['macro_config']['SRAM']['capacity_KiB']==832
    assert len({p['layer'] for p in r['phases'] if p['stage']=='NL_Wd'})==36
    assert r['kernel_active']['GU_frames']==36*6080 and r['kernel_active']['Wd_M128_frames']==36*3040
    assert r['actions']['samples']==36*2048 and r['actions']['PV_ADD']==36*262144
    assert b['gross_idle_double_counted'] is False and not b['unpriced_in_chosen_boundary']
    assert abs(sum(z['energy_mJ'] for z in b['rows'])-b['conditional_subsystem_energy_mJ'])<1e-10
    split=b['lm_head_split'];ph=Counter()
    for x in r['phases']:ph[x['stage']]+=x['duration_ns']/1e6
    records.append(dict(seed=r['seed'],job_id=entry['job_id'],time_ms=r['time_ms'],
        core_mJ=b['conditional_subsystem_energy_mJ'],total_4pJ_mJ=b['conditional_total_energy_mJ_by_external_pJbit']['4.0'],
        area_mm2=b['conditional_subsystem_area_mm2'],head_split=split,phases_ms=dict(ph),
        source=dict(code=r['code_sha256'],binding=r['bindings_sha256'],snapshot=r['snapshot_manifest_sha256'],macros=r['macro_config_sha256']),
        files=paths,energy_rows=b['rows']))
def mean(k):return statistics.mean(x[k] for x in records)
summary=dict(status='THREE_SEEDS_FULL_NATIVE_COMPLETED_VERIFIED',model='Qwen/Qwen3-4B',revision='1cfa9a7208912126459214e8b04321603b3df60c',
    clock_MHz=250,process='28nmTT0.9V25C',layers=36,vocab=151936,context=2048,batch=1,
    GU_samples=16,Wd_samples=32,K=128,S=64,SRAM_KiB=832,FFN_cores=3,
    time_ms=mean('time_ms'),time_sd_ms=statistics.stdev(x['time_ms'] for x in records),core_mJ=mean('core_mJ'),
    total_4pJ_mJ=mean('total_4pJ_mJ'),area_mm2=mean('area_mm2'),
    without_lm_head={k:statistics.mean(x['head_split']['without_lm_head_stage'][k] for x in records) for k in ('time_ms','core_energy_mJ')},
    without_lm_head_total_4pJ_mJ=statistics.mean(x['head_split']['without_lm_head_stage']['total_mJ_by_external_pJbit']['4.0'] for x in records),
    records=records,scope='fullhardwaretransactions;syntheticcapturedaddresses;notPPLorphysicalchip',
    previous_46ms_is_partial_extrapolation_superseded=True)
d=ROOT/'architecture_tlm/process_28nm/250MHz';(d/'FULL_RESULTS_20261110.json').write_bytes((json.dumps(summary,indent=2)+'\n').encode())
text=f'''# 28nm / 250MHz概率版完整三seed结果

2026-11-10，Issue225 / PR249。三项均Slurm COMPLETED/0:0，原件SEAL、RESULT/BUDGET/VALIDATION SHA及完整36层工作量已核验。不是旧一/两层外推；此前46.01856ms估计保留历史，本次结果优先。

|口径|时间ms/token|片上能量mJ/token|含外存4pJ/bit情景mJ/token|
|---|---:|---:|---:|
|包含lm_head|{summary['time_ms']:.6f}|{summary['core_mJ']:.6f}|{summary['total_4pJ_mJ']:.6f}|
|扣除lm_head阶段|{summary['without_lm_head']['time_ms']:.6f}|{summary['without_lm_head']['core_energy_mJ']:.6f}|{summary['without_lm_head_total_4pJ_mJ']:.6f}|

已覆盖核心子系统面积{summary['area_mm2']:.6f}mm²，均含同一常驻硬件；扣head只按同一次执行的final_norm前缀分账，不删除硬件或重启内存。时间标准差{summary['time_sd_ms']:.6f}ms，三seed为代表性采样地址，不是三颗芯片。

配置：Qwen3-4B后训练revision1cfa9a7208912126459214e8b04321603b3df60c，B1/2K，36层/151936词表；3核GU16/Wd32；SparQK128、Ising/PVS64、A/S12先量化分数；832KiB/178宏；共享256FMA。原生Ramulator/LPDDR5-derived8533时序保持，不是厂商8533签核。

|seed|作业ID|时间ms|片上mJ|
|---|---|---:|---:|
'''
for x in records:text+=f"|{x['seed']}|{x['job_id']}|{x['time_ms']:.6f}|{x['core_mJ']:.6f}|\n"
text+='''
能量账本按gross活动减活动idle，再加全部驻留idle；各行能量与总计闭合。存储、随机源、采样器及代理项沿冻结价卡；外存能量为4/6.6/8pJ/bit情景，非原生桥测量功耗。PHY/pads/CPU/package、完整CTS/SPEF等在边界外；面积与能耗不是完整物理芯片签核。

原始JSON本机归档project_archives/tlm28p250_full225_20261110/，远端根/public3/home/t6s011227/pbit_chimera_pipeline_20260920/tlm28p250_full225_3c811d6efe58。逐文件大小/SHA、源/配置SHA和分项见同名JSON及work/rayggxia/225/full250_20261109/COLLECTION.json。不重写任何冻结源或原封存文件；本轮没有新GPU、PPL或RTL/PT。
'''
(d/'FULL_RESULTS_20261110_ZH.md').write_bytes(text.encode())
print(json.dumps({k:v for k,v in summary.items() if k not in ('records',)}))
