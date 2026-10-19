"""Summarize collected Issue46 originals without copying long run JSON to Git.

Example: python analyze_results.py --input COLLECTED --output RESULTS
    --remote-root /home/USER/projects/PROJECT/outputs/EXECUTION_SHA
No model, torch, network access, or calibration files are needed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def configuration_hash(cfg):
    # Match the immutable runner's actual hashing convention, including spaces.
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()


def aggregate_diagnostics(records):
    """Value-count weights, not an unweighted average of 24 layer rates."""
    result = {}
    for signal in ('x', 'z'):
        count = sum(r.get(signal + '_values', 0) for r in records)
        part = dict(values=int(count), layer_summary_records=len(records))
        for metric in ('mean_probability', 'zero_fraction', 'clip_fraction', 'p1_fraction'):
            part[metric] = sum(r.get(signal + '_values', 0) * r.get(signal + '_' + metric, 0.)
                               for r in records) / max(count, 1)
        bins = [r.get(signal + '_bin_counts', []) for r in records]
        part['bin_counts'] = [sum(b[i] if i < len(b) else 0 for b in bins)
                              for i in range(max((len(b) for b in bins), default=0))]
        part['bin_occupancy'] = [b / max(count, 1) for b in part['bin_counts']]
        result[signal] = part
    return result


def summarize(source, destination, remote_root):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination == source or source in destination.parents:
        raise ValueError('Keep summaries outside the immutable collected-original directory')
    identity, suite, ready = (read(source / name) for name in
                              ('identity.json', 'suite.json', 'READY.json'))
    if ready.get('baseline_gate_passed') is not True:
        raise ValueError('READY baseline gate did not pass')
    for name in ('identity', 'suite'):
        if digest(source / (name + '.json')) != ready[name + '_sha256']:
            raise ValueError('READY checksum mismatch: ' + name)
    commit = ready['code_commit']
    if suite['code_commit'] != commit or identity['execution_commit'] != commit:
        raise ValueError('Mixed execution commits in metadata')
    planned = [dict(name='bf16_full', mode='baseline', full=True),
               dict(name='bf16_n512', mode='baseline', full=False)]
    planned += suite['screen'] + suite['full']
    expected = {c['name']: c for c in planned}
    if len(expected) != len(planned):
        raise ValueError('Duplicate planned configuration names')
    rows, diagnostics = [], {}
    for path in sorted((source / 'runs').glob('*.json')):
        raw = read(path)
        cfg = raw['configuration']
        name = cfg['name']
        if name not in expected or path.stem != name or cfg != expected[name]:
            raise ValueError('Unplanned or changed configuration: ' + name)
        if raw.get('code_commit') != commit:
            raise ValueError('Run execution commit mismatch: ' + name)
        if raw.get('configuration_sha256', configuration_hash(cfg)) != configuration_hash(cfg):
            raise ValueError('Run configuration checksum mismatch: ' + name)
        skipped = raw.get('status', '').startswith('skipped')
        if not skipped:
            wanted = 299077 if cfg['full'] else 511
            protocol = 'full_WT2_sliding_window' if cfg['full'] else 'WT2_fixed_test_prefix'
            if raw.get('scored_tokens') != wanted or raw.get('protocol') != protocol:
                raise ValueError('Scoring protocol/count mismatch: ' + name)
            if cfg['mode'] == 'baseline' and raw.get('baseline_gate_passed') is not True:
                raise ValueError('BF16 baseline gate failed: ' + name)
            if cfg['full'] and raw.get('token_ids_sha256') != identity['tokens']['test']['ids_sha256']:
                raise ValueError('Full test token hash mismatch: ' + name)
            if cfg['mode'] != 'baseline':
                if raw.get('identity_sha256') != ready['identity_sha256']:
                    raise ValueError('Run identity checksum mismatch: ' + name)
                if raw.get('full_test_token_ids_sha256') != identity['tokens']['test']['ids_sha256']:
                    raise ValueError('Run full corpus token hash mismatch: ' + name)
                if raw.get('model_revision') != identity['model_revision']:
                    raise ValueError('Run model revision mismatch: ' + name)
        row = dict(configuration=cfg, configuration_sha256=configuration_hash(cfg),
                   status='skipped' if skipped else 'completed',
                   skip_reason=raw.get('status') if skipped else None,
                   protocol=raw.get('protocol'), scored_tokens=raw.get('scored_tokens'),
                   perplexity=raw.get('perplexity'), nll=raw.get('nll'),
                   forward_seconds=raw.get('forward_seconds'),
                   token_ids_sha256=raw.get('token_ids_sha256'),
                   full_test_token_ids_sha256=raw.get('full_test_token_ids_sha256'),
                   identity_sha256=raw.get('identity_sha256'),
                   environment=raw.get('environment'), slurm_job_id=raw.get('slurm_job_id'),
                   remote_original=remote_root.rstrip('/') + '/runs/' + path.name,
                   original_bytes=path.stat().st_size, original_sha256=digest(path))
        if skipped:
            row.update(screen_mean_ppl=raw.get('screen_mean_ppl'),
                       screen_reference=raw.get('screen_reference'))
        layers = raw.get('diagnostics', {})
        if layers:
            diagnostics[name] = list(layers.values())
            row['diagnostics'] = aggregate_diagnostics(diagnostics[name])
        rows.append(row)
    by_name = {r['configuration']['name']: r for r in rows}
    pending = [c['name'] for c in planned if c['name'] not in by_name]
    references = {r['configuration']['full']: r for r in rows
                  if r['configuration']['mode'] == 'baseline' and r['status'] == 'completed'}
    if False in references:
        prefix_hash = references[False]['token_ids_sha256']
        for row in rows:
            if not row['configuration']['full'] and row['status'] == 'completed' and row['token_ids_sha256'] != prefix_hash:
                raise ValueError('Mixed prefix token hashes')
    keys = sorted({(c['full'], c.get('policy', 'BF16'), c['mode'], c.get('cycles', 0))
                   for c in planned})
    groups = []
    for full, policy, mode, cycles in keys:
        configs = [c for c in planned if (c['full'], c.get('policy', 'BF16'), c['mode'],
                    c.get('cycles', 0)) == (full, policy, mode, cycles)]
        present = [by_name[c['name']] for c in configs if c['name'] in by_name]
        completed = [r for r in present if r['status'] == 'completed']
        values = [r['perplexity'] for r in completed]
        finite = bool(values) and all(v is not None for v in values)
        average = statistics.mean(values) if finite else None
        ref = references.get(full, {}).get('perplexity')
        group = dict(full=full, policy=policy, mode=mode, cycles=cycles,
                     expected=len(configs), completed=len(completed),
                     skipped=sum(r['status'] == 'skipped' for r in present),
                     pending=len(configs)-len(present),
                     seeds=[r['configuration'].get('seed') for r in completed],
                     scored_tokens=299077 if full else 511,
                     scored_tokens_observed=sorted({r['scored_tokens'] for r in completed}),
                     ppl_mean=average, ppl_population_std=statistics.pstdev(values) if finite else None,
                     ppl_overflow_runs=sum(v is None for v in values),
                     relative_to_BF16_percent=(average/ref-1)*100 if average is not None and ref else None,
                     mean_forward_seconds=statistics.mean(r['forward_seconds'] for r in completed)
                        if completed else None,
                     diagnostics=aggregate_diagnostics([d for r in completed for d in
                         diagnostics.get(r['configuration']['name'], [])]))
        groups.append(group)
    artifacts = [dict(relative_path=str(p.relative_to(source)).replace('\\', '/'),
                       bytes=p.stat().st_size, sha256=digest(p),
                       remote_path=remote_root.rstrip('/') + '/' + str(p.relative_to(source)).replace('\\', '/'))
                 for p in sorted(source.rglob('*'))
                 if p.is_file() and p.name != 'COLLECTION_INDEX.json']
    collection = source / 'COLLECTION_INDEX.json'
    collection_record = None
    if collection.exists():
        collected = read(collection)
        if collected.get('execution_commit') != commit or collected.get('remote_output') != remote_root:
            raise ValueError('Collector receipt execution/location mismatch')
        actual = {a['relative_path']: {'bytes': a['bytes'], 'sha256': a['sha256']} for a in artifacts}
        if collected.get('files') != actual:
            raise ValueError('Collected originals do not match the collector byte/SHA receipt')
        collection_record = dict(relative_path=collection.name, bytes=collection.stat().st_size,
                                 sha256=digest(collection), location='local collector receipt; not a server original')
    now = datetime.now(timezone.utc).isoformat()
    status = dict(expected=len(planned), completed=sum(r['status']=='completed' for r in rows),
                  skipped=sum(r['status']=='skipped' for r in rows), pending=len(pending),
                  pending_names=pending, all_planned_accounted_for=not pending,
                  all_planned_scored=not pending and all(r['status']=='completed' for r in rows))
    summary = dict(issue=46, generated_utc=now, execution_commit=commit,
                   status=status, remote_root=remote_root,
                   identity={k: identity.get(k) for k in ('status', 'model_repository',
                     'model_revision', 'revision_evidence', 'files', 'tokens', 'source_sha256',
                     'frozen_manifest_sha256', 'multiscale_sources', 'randomness', 'physical_rng_replay')},
                   identity_sha256=digest(source/'identity.json'), suite_sha256=digest(source/'suite.json'),
                   ready_sha256=digest(source/'READY.json'), suite=suite, groups=groups, rows=rows,
                   diagnostic_aggregation='Rates weighted by each layer x/z_values; propagation-path values include overlapping sliding windows and repeated seeds, not unique corpus activations. Bin occupancy uses summed raw bin counts. No global energy-weighted encoding NMSE inferred.',
                   limitations=['mean is a deterministic encoded-path control, not the expectation of the complete nonlinear stochastic network',
                     'prefix scores are not full WT2 PPL; compare only matching protocol and scored-token count',
                     'all 24 FFNs replaced; original BF16 SDPA attention unchanged; no training',
                     'same historical fixed symmetric INT8 64x64 weights; no stochastic-W reencoding',
                     'natural IID shared64 R8 joint count law; exact FP32 restoration, not finite-width RTL',
                     'no new PPA/PT/TLM or measured hardware energy; GPU forward time is not ASIC latency'])
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination/'SUMMARY.json', summary)
    write_json(destination/'ARTIFACT_INDEX.json', dict(issue=46, execution_commit=commit,
       generated_utc=now, remote_root=remote_root, status=status, artifacts=artifacts,
       local_collection_receipt=collection_record,
       access='Original run diagnostics remain in authorized personal server storage; Git contains summaries and byte/SHA indexes only. No model weights, text, activation arrays, or calibration data are copied.'))
    lines = ['# 固定INT8权重＋输入多尺度随机编码', '',
             'Issue46；执行源 `' + commit + '`。', '',
             f"预注册 {status['expected']} 项：已计分 {status['completed']}，明确跳过 {status['skipped']}，待收回/待完成 {status['pending']}。", '',
             '所有24个FFN替换，Attention保持原BF16 SDPA；固定历史64×64 INT8解码权重，不做权重概率重编码。输入每64通道共享自然IID R8，跨尺度档仍共享；g/u共用输入计数，准确连续FP32 SiLU(g)×u后独立重编码z。', '',
             'mean是无采样的确定性编码控制，**不是非线性随机网络整体输出的数学期望**。w8_only不编码激活，包含固定W8和中间FP32算术。', '']
    for full, title in ((True, '完整WT2滑窗'), (False, '512-token测试前缀')):
        lines += ['## ' + title, '',
                  ('每次计分511个目标；不是完整WT2。' if not full else
                   'context=2048、stride=1024；按总NLL/总目标数取exp，每次计分299077个目标。'), '',
                  '| 编码 | 模式 | T | PPL均值±总体标准差 | 相对同协议BF16 | 已计分/计划 | 跳过 | 待完成 |',
                  '|---|---|---:|---:|---:|---:|---:|---:|']
        for g in [g for g in groups if g['full'] == full]:
            if g['ppl_mean'] is not None:
                value = f"{g['ppl_mean']:.6f}"
                if g['completed'] > 1:
                    value += f" ± {g['ppl_population_std']:.6f}"
            else:
                value = '溢出/无有限PPL' if g['ppl_overflow_runs'] else ('跳过' if g['skipped'] else '待完成')
            relative = f"{g['relative_to_BF16_percent']:+.3f}%" if g['relative_to_BF16_percent'] is not None else '—'
            lines.append(f"| {g['policy']} | {g['mode']} | {g['cycles'] or '—'} | {value} | {relative} | {g['completed']}/{g['expected']} | {g['skipped']} | {g['pending']} |")
        lines.append('')
    lines += ['## 编码诊断与证据', '',
       'SUMMARY.json逐项保留配置、种子、计分目标、PPL/NLL、耗时及原件SHA；分组采用各seed PPL的均值和总体标准差，不把窗口PPL平均当整库PPL。少于3seed或尚有pending时，表中数字仅代表已收回项。', '',
       '各层x/z概率、零码率、真实裁剪率、恒1率按实际values加权，档占用按bin_counts求和。它们来自各自传播路径；完整滑窗包含重叠窗口，跨seed也重复，不能称为原BF16 teacher或不重复语料的激活分布。', '',
       '元数据含执行commit、配置SHA、模型revision、模型/分词器/原文/token和源文件SHA。ARTIFACT_INDEX.json列出服务器原件位置、bytes、SHA-256；原始长JSON不复制进Git。', '',
       '这是理想IID联合分布与FP32线性恢复的数值评估，不是有限位宽RTL、物理随机源回放或新PPA/PT/TLM结果。GPU前向秒数不能作为ASIC周期。']
    lines += ['', 'T表示每次x/z采样阶段的流长度，不等于整层或整token总周期。旧W8量化步长未改、未保证为二次幂；输入PoT不代表所有尺度恢复都只需移位。若再限制权重步长为PoT，需独立验证PPL。']
    if pending:
        lines += ['', '## 未完成项', ''] + ['- `' + name + '`' for name in pending]
    with (destination/'RESULTS_ZH.md').open('w', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines) + '\n')
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', '--evidence-dir', dest='source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--remote-root', required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(args.source, args.output, args.remote_root), ensure_ascii=False))


if __name__ == '__main__':
    main()
