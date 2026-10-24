"""Verify sealed raw bytes before deriving pilot summaries; never infer completion."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    raw, out = Path(args.raw), Path(args.out)
    complete = json.loads((raw / 'complete.json').read_text())
    assert complete['status'] == 'completed' and complete['cases'] == 18
    for name, sha in complete['documents'].items():
        assert digest(raw / name) == sha, name
    for path in raw.glob('*.json'):
        if path.name.endswith('.sha256.json'):
            continue
        signed = json.loads(path.with_suffix('.sha256.json').read_text())
        assert signed['sha256'] == digest(path), path.name
    provenance = json.loads((raw / 'provenance.json').read_text())
    assert provenance['model']['id'] == 'Qwen/Qwen3-4B'
    assert provenance['model']['revision'] == '1cfa9a7208912126459214e8b04321603b3df60c'
    expected = {'bf16.json': ('bf16', None), 'w8_only_s0.json': ('w8_only', 0),
                'fixed_mean_s0.json': ('fixed_mean', 0)}
    for label in ['dynamic32', 'fixed32', 'dynamic64', 'fixed64', 'fixed_x32']:
        for seed in range(3):
            expected[label + '_s' + str(seed) + '.json'] = (label, seed)
    by_label, records, plan_hash = {}, [], None
    for name, (label, seed) in expected.items():
        r = json.loads((raw / name).read_text())
        assert r['status'] == 'completed' and r['case'] == label
        assert r.get('seed') == seed and r['scored_tokens'] == 4096
        assert len(r['rows']) == 32
        assert r['all_layer_calls'] == [32] * 36
        assert r['all_layer_input_tokens'] == [69600] * 36
        assert math.isclose(r['nll_sum'], math.fsum(x['nll_sum'] for x in r['rows']), rel_tol=1e-14)
        assert math.isclose(r['perplexity'], math.exp(r['nll_sum'] / 4096), rel_tol=1e-14)
        assert r['provenance_sha256'] == digest(raw / 'provenance.json')
        if plan_hash is None:
            plan_hash = r['target_positions_sha256']
        assert r['target_positions_sha256'] == plan_hash
        metrics = {}
        if label != 'bf16':
            assert r['calibration_sha256'] == digest(raw / 'calibration.json')
            assert len(r['diagnostics']) == 36
            for signal in ('x', 'z'):
                items = [r['diagnostics'][str(i)] for i in range(36)]
                total = sum(d[signal + '_values'] for d in items)
                metrics[signal] = dict(clip_fraction=sum(d[signal + '_clip_fraction'] * d[signal + '_values'] for d in items) / total,
                    mean_probability=sum(d[signal + '_mean_probability'] * d[signal + '_values'] for d in items) / total,
                    bin_occupancy=[sum(d[signal + '_bin_counts'][b] for d in items) / total for b in range(4)])
                for d in items:
                    assert d['calls'] == 32 and d['cycles'] == r['cycles'] and d['strata'] == r['strata']
                    is_static = r['fixed_x'] if signal == 'x' else r['fixed_z']
                    assert (d['encoding_policy'][signal] == 'static_four_pot') == is_static
                    assert d['scales_sha256'][signal] is not None if is_static else d['scales_sha256'][signal] is None
                    if r['mode'] != 'w8_only':
                        assert (signal in d['online_absmax_signals']) != is_static
        record = dict(file=name, sha256=digest(raw / name), label=label, seed=seed,
                      ppl=r['perplexity'], nll=r['nll_sum'], seconds=r['seconds'], metrics=metrics)
        records.append(record)
        by_label.setdefault(label, []).append(record)
    baseline = by_label['bf16'][0]['ppl']
    groups = []
    for label, items in by_label.items():
        ppls = [r['ppl'] for r in items]
        mean = statistics.mean(ppls)
        groups.append(dict(label=label, seeds=[r['seed'] for r in items], mean_ppl=mean,
                           population_sd=statistics.pstdev(ppls), delta_bf16_pct=(mean / baseline - 1) * 100))
    result = dict(status='verified_completed', cases=18, scored_tokens_per_case=4096,
        protocol='vectorized suffix, batch1, 32x128 targets; not full WT2',
        source=provenance['source'], model=provenance['model'], data=provenance['data'],
        provenance_sha256=digest(raw / 'provenance.json'), calibration_sha256=digest(raw / 'calibration.json'),
        target_positions_sha256=plan_hash, groups=groups, records=records)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'SUMMARY.json').write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    lines = ['# Qwen3-4B 后训练版：固定四档尺度小规模PPL', '',
        '18项全部封存并通过SHA、模型版本、4096目标与36层输入覆盖核验。Slurm2879；无训练，Attention保持原准确SDPA。', '',
        '**这是32段×128目标的向量化后缀PPL，不是完整WT2。** batch1；每段2048前缀上下文，所有2175输入都经过所选FFN。不得与旧cached/batch2数值直接相减。', '',
        '| 方案 | PPL均值 | 三seed总体标准差 | 相对本轮BF16 |',
        '|---|---:|---:|---:|']
    names = dict(bf16='原BF16', w8_only='W8连续输入', fixed_mean='固定四档编码均值（无采样）',
                 dynamic32='动态四档，32次', fixed32='固定四档，32次', dynamic64='动态四档，64次',
                 fixed64='固定四档，64次', fixed_x32='固定x、动态z，32次')
    for g in groups:
        deviation = f"{g['population_sd']:.6f}" if len(g['seeds']) == 3 else '—'
        lines.append(f"| {names[g['label']]} | {g['mean_ppl']:.6f} | {deviation} | {g['delta_bf16_pct']:+.3f}% |")
    mapping = {g['label']: g['mean_ppl'] for g in groups}
    lines += ['', f"相同采样预算：固定32相对动态32变化 {(mapping['fixed32']/mapping['dynamic32']-1)*100:+.3f}%；固定64相对动态64变化 {(mapping['fixed64']/mapping['dynamic64']-1)*100:+.3f}%。",
        '', '固定尺度在这组小样本中没有明显失效；不能用三seed的均值排序证明固定优于动态或模型整体改善。随机seed波动与语料抽样不确定性不同，尚无完整WT2或任务准确率确认。',
        '', 'BF16与W8参考还存在FFN算术精度差异：原FFN为BF16，替换FFN保留FP32线性与SiLU/乘积、BF16边界。部分PPL下降不能单独归因为量化/固定尺度。判断静态尺度应优先用同算术动态对照。',
        '', '固定表：TRAIN均匀16段×512token；W8连续与动态T32/seed917两条传播路径覆盖，各层x/z各64通道组最大值上取二次幂，四档S/S4/S16/S64；无额外余量。校准合计两条路径各8192token，未用测试文本选表。测试只选档、超顶档截断，不在线扩档。诊断统计含归约，但不驱动尺度且不是硬件成本模拟。',
        '', '本轮仅四档、固定W8、A8幅度与独立符号、共享64门限、T=K随机分层。尚未比较固定2/8档、自然IID、W4/W6、训练适配或联合随机Attention。',
        '', '## 截断与占档诊断', '', '| 方案 | x截断元素比例 | z截断元素比例 |', '|---|---:|---:|']
    for label in ['fixed32', 'fixed64', 'fixed_x32']:
        items = by_label[label]
        fractions = {s: statistics.mean(r['metrics'][s]['clip_fraction'] for r in items) for s in ('x', 'z')}
        lines.append(f"| {names[label]} | {fractions['x']:.6%} | {fractions['z']:.6%} |")
    lines += ['', '完整各层编码误差/截断能量/档位统计保留在原始结果；SUMMARY.json含汇总、逐seed及代码/配置/数据/目标SHA。原件归档位置见RAW_INDEX.json；固定表CALIBRATION.json保持原字节。',
              '', '执行源码：`' + provenance['source']['commit'] + '`。Issue168 / PR169；后处理与发布提交可能晚于执行，冻结快照未修改。']
    (out / 'REPORT_ZH.md').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))
    print(json.dumps(groups, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
