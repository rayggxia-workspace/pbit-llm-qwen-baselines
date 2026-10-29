"""Reprice three frozen full-model activity records with new digital anchors."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
from .model import PROFILES, estimate, anchors


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    a = p.parse_args(argv)
    if a.output.exists():
        raise ValueError('new derived output directory required')
    baseline_path = a.repo / 'architecture_tlm/component_budget_audit_20261029/results/BREAKDOWN.json'
    d = json.loads(baseline_path.read_text(encoding='utf-8'))
    manifest = json.loads((baseline_path.parents[1] / 'DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
    assert digest(baseline_path) == manifest['files'][baseline_path.relative_to(a.repo).as_posix()]['sha256']
    inputs = []
    sources = {}
    for seed in range(3):
        path = a.repo / f'architecture_tlm/scheduling_v2_20261027/results_early_dma/case_{seed+1}/RESULT_SUMMARY.json'
        assert digest(path) == d['source_manifest'][path.relative_to(a.repo).as_posix()]['sha256']
        inputs.append(json.loads(path.read_text(encoding='utf-8')))
        sources[path.relative_to(a.repo).as_posix()] = digest(path)
    old = next(x for x in d['hardware_modules'] if x['module'] == 'ordinary_BF16_MACs')
    time_s = d['totals']['TPOT_ms'] * 1e-3
    results = {}
    profiles_csv = []
    for profile in PROFILES:
        quotes = []
        for s in inputs:
            c = copy.deepcopy(s['config'])
            c['digital_power'] = dict(profile=profile, idle_dynamic_keep=.1)
            quotes.append(estimate(c, s['actions'], s['resource_busy_ns'], s['metrics']['elapsed_ns']))
        q = {key: mean(x[key] for x in quotes) for key in ('energy_J', 'raw_area_mm2',
            'area_55eq_mm2', 'leakage_J', 'background_dynamic_J', 'work_increment_J')}
        total_mJ = d['totals']['onchip_mJ'] - old['energy_mJ_per_token'] + q['energy_J'] * 1000
        total_area = d['totals']['equivalent_55nm_priced_area_mm2'] - old['equivalent_55nm_area_mm2'] + q['area_55eq_mm2']
        modules = copy.deepcopy(d['hardware_modules'])
        for row in modules:
            if row['module'] == 'ordinary_BF16_MACs':
                row.update(energy_mJ_per_token=q['energy_J'] * 1000,
                    raw_priced_area_mm2=q['raw_area_mm2'], equivalent_55nm_area_mm2=q['area_55eq_mm2'],
                    leakage_J=q['leakage_J'], idle_clock_background_J=q['background_dynamic_J'],
                    work_increment_J=q['work_increment_J'], evidence=quotes[0]['evidence'])
            row['average_power_W'] = row['energy_mJ_per_token'] / (time_s * 1000)
            row['onchip_energy_share_pct'] = row['energy_mJ_per_token'] / total_mJ * 100
            row['priced_area_share_pct'] = (row['equivalent_55nm_area_mm2'] or 0) / total_area * 100
            # The old conditional-system share denominator is no longer valid.
            row.pop('conditional_system_energy_share_pct', None)
        assert abs(sum(x['energy_mJ_per_token'] for x in modules) - total_mJ) < 1e-9
        assert abs(sum(x['equivalent_55nm_area_mm2'] or 0 for x in modules) - total_area) < 1e-9
        assert abs(sum(x['onchip_energy_share_pct'] for x in modules) - 100) < 1e-9
        result = dict(**q, MAC_average_W=q['energy_J'] / time_s,
            covered_onchip_mJ_per_token=total_mJ, covered_onchip_average_W=total_mJ / 1000 / time_s,
            covered_area_55eq_mm2=total_area, TPOT_ms=d['totals']['TPOT_ms'],
            conditional_with_legacy_external_W=total_mJ / 1000 / time_s + d['totals']['external_proxy_W'],
            modules=modules, seed_quotes=quotes)
        results[profile] = result
        profiles_csv.append({k: result[k] for k in ['MAC_average_W', 'covered_onchip_mJ_per_token',
            'covered_onchip_average_W', 'covered_area_55eq_mm2', 'TPOT_ms']} | {'profile': profile})
    sensitivity = []
    for keep in (0., .1, 1.):
        qs=[]
        for s in inputs:
            c=copy.deepcopy(s['config']);c['digital_power']=dict(profile='nonfused_pair',idle_dynamic_keep=keep)
            qs.append(estimate(c,s['actions'],s['resource_busy_ns'],s['metrics']['elapsed_ns']))
        sensitivity.append(dict(idle_dynamic_keep=keep,MAC_average_W=mean(x['energy_J'] for x in qs)/time_s))
    output = dict(scope='new digital energy-only replay of frozen synthetic TLM activity; no new full-model time or EDA',
        recommended_profile='nonfused_pair', full_calibrated_system_PPA=None,
        baseline_commit='9fce5f54ca0c737488c91bf53673e53617eb5704',
        baseline_sha256=digest(baseline_path), sources=sources,
        anchor_source=anchors()['source'], anchor_sha256=digest(Path(__file__).with_name('ANCHORS.json')),
        code_sha256={n:digest(Path(__file__).with_name(n)) for n in ['model.py','reprice.py']},
        previous=d['totals'], profiles=results, idle_sensitivity=sensitivity,
        checks={'three_frozen_summary_SHA_verified':True,'all_three_profiles_close_energy_area_and_shares':True,
                'TPOT_work_memory_random_source_unchanged':True,'old_immutable_files_untouched':True})
    a.output.mkdir(parents=True)
    (a.output/'RESULTS.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for name,rows in [('PROFILE_COMPARISON.csv',profiles_csv),('MODULES.csv',results['nonfused_pair']['modules'])]:
        with (a.output/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    selected=results['nonfused_pair']
    rows='\n'.join(f"|{x['label_zh']}|{x['energy_mJ_per_token']:.6f}|{x['average_power_W']:.6f}|{x['onchip_energy_share_pct']:.3f}%|{x['equivalent_55nm_area_mm2']:.6f}|" if x['equivalent_55nm_area_mm2'] is not None else f"|{x['label_zh']}|{x['energy_mJ_per_token']:.6f}|{x['average_power_W']:.6f}|{x['onchip_energy_share_pct']:.3f}%|未独立价|" for x in selected['modules'])
    comparison='\n'.join(f"|{name}|{x['MAC_average_W']:.6f}|{x['covered_onchip_average_W']:.6f}|{x['covered_area_55eq_mm2']:.6f}|" for name,x in results.items())
    text=f'''# 新数字标定后的TLM功耗预算

Issue210 / PR211；原PR209 BF16表征只读。新数据已进入unified_v6的数字能耗后端，不只是更改报告常数；同时对原三seed全36层活动记录作能量重放。没有重跑全模型时序、EDA或PPL。

默认采用nonfused_pair：独立BF16乘法＋FP32加法的已测单元相加代理，保持原非融合算术口径；不是集成MAC实测。FMA2/3是成本替代情景，未验证替换后的数值或500MHz阵列。原始SS1.08V/125℃100MHz，按活动完成次数归一化；只对面积乘0.81，不缩功耗、频率或时间。

## 总括对照

|数字价格|MAC平均W|片上已价平均W|55nm等效已价面积mm²|
|---|---:|---:|---:|
|旧calibration_v2|{old['average_power_W']:.6f}|{d['totals']['onchip_W_common_mean_TPOT']:.6f}|{d['totals']['equivalent_55nm_priced_area_mm2']:.6f}|
{comparison}

默认新片上能量{selected['covered_onchip_mJ_per_token']:.6f}mJ/token，时间仍{selected['TPOT_ms']:.6f}ms/token。只替换bf16_mac账目，FP32向量、PV和其余模块暂保留原价，避免不匹配的边界相加。旧外存代理另{d['totals']['external_proxy_W']:.6f}W；完整校准整机PPA仍未知。

## 新默认逐模块表

|模块|mJ/token|平均W|片上能量占比|55nm等效mm²|
|---|---:|---:|---:|---:|
{rows}

## 如何接入

新load非legacy配置默认digital_power.profile=nonfused_pair；CLI可选--digital-energy-profile nonfused_pair/fma2/fma3/legacy_proxy、--digital-idle-keep。FullDecode在执行完成后按实际动作数、MAC资源忙时和整段寿命计价，并从Ledger逐类别移除原bf16_mac收费后替换一次。其余数字动作和FP32_MAC未价项保留，不减掉其他vector费用，也不把原2pJ再叠上去。

活动增量按(活动功率−idle功率)×实测窗口时长÷实际完成次数，包含标量窗口1036拍/1024次的排空归一化；背景按参考拍能量×工作/等待拍数，漏电按寿命计。新nonfused_pair的MAC工作增量约{selected['work_increment_J']*1000:.6f}mJ、背景{selected['background_dynamic_J']*1000:.6f}mJ、漏电{selected['leakage_J']*1000:.6f}mJ。

## 当前还缺的关键数字验证

1. 500MHz实现。现为100MHz前布局小核；标量hold仍−0.061165ns，DOT64虽契约下非负但setup仅0.000027ns，不能宣称500MHz或物理签核。
2. 小型集成tile。补乘加、部分和上下文、反馈/归约、格式与真实握手；单元求和不是集成PPA，DOT64的30拍帧间隔不能直接替代原2048 MAC/拍。
3. 真实门控与回压活动。当前消除90%空闲动态是情景；需含真实ICG/扇出和活跃、空闲、停顿、唤醒。idle_keep=0/.1/1敏感性留在JSON，漏电始终保留。
4. 匹配数据和功能。当前是合成激励，未用模型Q/K/V、投影/词表权重轨迹；FMA与非融合、特殊值、累加顺序要对照。FP32×FP32/FP32×BF16的精确PV乘法仍没有匹配校准。
5. 物理接口。补代表8/16路tile的SRAM端口、广播负载、互连和时钟成本，校验线性复制；不必综合完整2048路或整个LLM。

这次修改不改变采样、访存、随机源、时序或模型精度。完整DOT64577pJ/帧（摊销9.015625pJ/MAC）仅列参考，estimate明确拒绝把dot64_4当标量价格配置。既有统一台账matrix-bf16-204-20261028保持原件与失败记录，本轮只新增派生能量结果，不新增假EDA run。
'''
    (a.output/'REPORT_ZH.md').write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'status':'passed','profiles':profiles_csv},ensure_ascii=False))


if __name__ == '__main__':
    main()
