"""Validate downloaded Issue59 artifacts and summarize paired task accuracy.

CPU/stdlib only. Source SHA refers to the frozen execution, never this collector's
current Git HEAD. Progress rows are deliberately not promoted to completed tasks.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

TASKS = {
    'piqa': (1838, 1838, '40e1677bba609c8801deacc171d76f3e24c083f365c95a1cbda7520c923dfea2'),
    'arc_easy': (2376, 2376, '4160597d618ae851c7eb04e281574f3f654776216ac6b6641588d64527b47177'),
    'hellaswag': (10042, 1000, '899813071e1e95efafec90f856e1987d2150fa4d020fc005df6962c259f660cd'),
}
METRICS = ('acc', 'acc_norm')


def expected_configurations():
    """Frozen run_tasks.py configuration contract, without importing CUDA code."""
    rows = [dict(name='bf16', ffn='none', mode='sdpa', samples=128, seed=0)]
    rows += [dict(name=f'ffn_only_s{s}', ffn='b4_t32', mode='sdpa', samples=128, seed=s)
             for s in (0, 1, 2)]
    rows += [dict(name=f'joint_S{n}_s{s}', ffn='b4_t32', mode='screen_ising', samples=n, seed=s)
             for n in (64, 128, 512) for s in (0, 1, 2)]
    for row in rows:
        row.update(batch=16, burn=16., spacing=4., selection='fixed', budget_blocks=8,
                   target_fraction=.30, context=2048)
    return rows


def normalized_case(configuration):
    # _case() inherited from the finite Attention evaluator adds these dormant
    # PPL-plan defaults. MC uses cached_score's explicit document loop, not that
    # inherited suffix plan; still verify its recorded defaults byte-for-value.
    return dict(decode=128, examples=32, protocol='suffix', stride=1024,
                capture_scored_logits_sha256=False, **configuration)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'Duplicate JSON key {key!r}: {path}')
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_artifact(path, entry):
    require(path.is_file(), f'Missing sealed artifact: {path}')
    require(sha(path) == entry['sha256'], f'SHA-256 mismatch: {path}')
    if 'bytes' in entry:
        require(path.stat().st_size == entry['bytes'], f'Size mismatch: {path}')


def document_ids(task):
    full, count, _ = TASKS[task]
    if task == 'hellaswag':
        return sorted(random.Random(20261019).sample(range(full), count))
    return list(range(count))


def validate_rows(path, task, expected_ids, *, complete):
    rows, found = {}, set()
    text = path.read_text(encoding='utf-8')
    require(not text or text.endswith('\n'), f'Truncated JSONL (no final LF): {path}')
    for number, line in enumerate(text.splitlines(), 1):
        require(bool(line.strip()), f'Empty JSONL row: {path}:{number}')
        # Also reject duplicate JSON keys inside individual document rows.
        def unique(pairs):
            obj = {}
            for key, value in pairs:
                require(key not in obj, f'Duplicate row key: {path}:{number}:{key}')
                obj[key] = value
            return obj
        row = json.loads(line, object_pairs_hook=unique)
        doc_id = row.get('doc_id')
        require(type(doc_id) is int and doc_id in expected_ids, f'Unexpected document ID: {path}:{doc_id}')
        require(row.get('id') == f'{task}:{doc_id}' and row.get('task') == task,
                f'Task/document identity mismatch: {path}:{doc_id}')
        require(doc_id not in found, f'Duplicate document: {path}:{doc_id}')
        found.add(doc_id)
        require(set(row.get('metrics', {})) == set(METRICS), f'Missing/extra metric: {path}:{doc_id}')
        require(all(type(row['metrics'][m]) in (int, float) and row['metrics'][m] in (0., 1.)
                    for m in METRICS), f'Nonbinary official metric: {path}:{doc_id}')
        choices = row.get('choices')
        require(isinstance(choices, list) and len(choices) >= 2, f'Missing choices: {path}:{doc_id}')
        if task in ('piqa', 'hellaswag'):
            require(len(choices) == (2 if task == 'piqa' else 4), f'Choice count mismatch: {path}:{doc_id}')
        for choice in choices:
            require(type(choice.get('tokens')) is int and choice['tokens'] > 0,
                    f'Invalid answer token count: {path}:{doc_id}')
            ll = choice.get('logprob')
            require(type(ll) in (int, float) and math.isfinite(ll) and ll <= 1e-5,
                    f'Invalid choice likelihood: {path}:{doc_id}')
            require(type(choice.get('is_greedy')) is bool, f'Invalid greedy flag: {path}:{doc_id}')
        rows[doc_id] = row
    if complete:
        require(found == expected_ids, f'Missing/truncated completed documents: {path}: {len(found)}/{len(expected_ids)}')
    require(len(found) <= len(expected_ids), f'Too many progress documents: {path}')
    return rows


def paired(reference, variant):
    require(set(reference) == set(variant), 'Paired tasks require identical document sets')
    n = len(reference)
    output = {}
    for metric in METRICS:
        counts = dict(correct_to_wrong=0, wrong_to_correct=0, both_correct=0, both_wrong=0)
        for doc_id in reference:
            old, new = reference[doc_id]['metrics'][metric], variant[doc_id]['metrics'][metric]
            key = ('both_correct' if new else 'correct_to_wrong') if old else ('wrong_to_correct' if new else 'both_wrong')
            counts[key] += 1
        counts.update(n_documents=n, net_change_pp=100 * (counts['wrong_to_correct'] - counts['correct_to_wrong']) / n)
        output[metric] = counts
    return output


def summary_stats(values):
    return dict(mean=statistics.mean(values), std=statistics.pstdev(values), n=len(values))


def collect(root, execution_commit=None):
    root = Path(root).resolve()
    meta, ready, suite = (load_json(root / n) for n in ('TASK_DATA.json', 'READY.json', 'suite.json'))
    commit = ready['code_commit']
    require(isinstance(commit, str) and len(commit) == 40 and all(c in '0123456789abcdef' for c in commit),
            'Exact 40-character execution commit required')
    require(meta['code_commit'] == commit, 'TASK_DATA/READY execution mismatch')
    if execution_commit is not None:
        require(commit == execution_commit, 'Unexpected frozen execution commit')
    require(ready.get('baseline_gate_passed') is True and ready.get('bf16_task_bridge_passed') is True,
            'Fresh BF16 reference/task bridge did not pass')
    for key, filename in [('task_data_sha256', 'TASK_DATA.json'), ('suite_sha256', 'suite.json'),
                          ('identity_sha256', 'identity.json')]:
        require(sha(root / filename) == ready[key], f'Preparation SHA mismatch: {filename}')
    require(meta['source_sha256'] == ready['source_sha256'], 'Frozen source manifest mismatch')
    require(meta.get('harness_version') == '0.4.8' and meta.get('num_fewshot') == 0
            and meta.get('chat_template') is False, 'Unexpected official task protocol')
    configurations = expected_configurations()
    require(suite['configurations'] == configurations, 'Unexpected/missing/duplicate suite configurations')
    require(set(suite['tasks']) == set(TASKS) and len(suite['tasks']) == len(TASKS)
            and suite['count'] == len(TASKS) * len(configurations), 'Unexpected suite task count')
    require(suite['task_statistics'] == meta['statistics'], 'Suite/task statistics mismatch')
    require(set(meta['tasks']) == set(TASKS) and set(meta['statistics']) == set(TASKS), 'Unexpected prepared tasks')
    artifacts = {n: dict(path=n, sha256=sha(root/n), bytes=(root/n).stat().st_size)
                 for n in ('TASK_DATA.json', 'READY.json', 'suite.json', 'identity.json')}
    expected = {}
    for task, (full, count, checksum) in TASKS.items():
        identity, stats = meta['tasks'][task], meta['statistics'][task]
        require(identity['dataset_sha256'] == checksum and identity['documents'] == full,
                f'Prepared dataset identity mismatch: {task}')
        require(stats['documents'] == count and stats['full_split_documents'] == full,
                f'Wrong prepared document count: {task}')
        ids = document_ids(task)
        selected_sha = hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()
        require(stats['selected_doc_ids_sha256'] == selected_sha, f'Changed task selection: {task}')
        expected[task] = set(ids)
        # Downloading large token files is optional; verify every one provided.
        token_path = root / 'tokenized' / f'{task}.jsonl'
        if token_path.exists():
            verify_artifact(token_path, meta['tokenized'][task])
            artifacts[str(token_path.relative_to(root))] = dict(sha256=sha(token_path), bytes=token_path.stat().st_size)
    allowed = {f'{task}_{cfg["name"]}' for task in TASKS for cfg in configurations}
    full_dir = root / 'full'
    for path in full_dir.glob('*'):
        if not path.is_file():
            continue
        stem = path.name
        suffix = next((s for s in ('.documents.jsonl', '.progress.jsonl', '.json') if stem.endswith(s)), None)
        require(suffix is not None and stem[:-len(suffix)] in allowed, f'Unknown/duplicate case artifact: {path}')
        if suffix == '.documents.jsonl':
            require(path.with_name(stem[:-len(suffix)] + '.json').is_file(), f'Orphan completed document artifact: {path}')
    cases, partial, pending, records = [], [], [], {}
    for task in TASKS:
        for cfg in configurations:
            stem = f'{task}_{cfg["name"]}'
            path = full_dir / f'{stem}.json'
            progress_path = full_dir / f'{stem}.progress.jsonl'
            progress_rows = (validate_rows(progress_path, task, expected[task], complete=False)
                             if progress_path.exists() else {})
            if not path.exists():
                pending.append(dict(task=task, configuration=cfg, n_completed_documents=len(progress_rows),
                                    n_expected_documents=len(expected[task])))
                if progress_rows:
                    partial.append(dict(task=task, case=cfg['name'], configuration=cfg,
                        n_documents=len(progress_rows), n_expected_documents=len(expected[task]),
                        metrics={m:statistics.mean(r['metrics'][m] for r in progress_rows.values()) for m in METRICS},
                        artifact_sha256=sha(progress_path),
                        evidence='Unsealed progress only; no completed result, not a full-split score; no baseline delta'))
                    artifacts[str(progress_path.relative_to(root))] = dict(sha256=sha(progress_path), bytes=progress_path.stat().st_size)
                continue
            result = load_json(path)
            require(result.get('status') == 'completed', f'Noncompleted full result: {path}')
            require(result.get('code_commit') == commit and result.get('task') == task,
                    f'Execution/task mismatch: {path}')
            require(result.get('task_data_sha256') == ready['task_data_sha256'], f'Result task data SHA mismatch: {path}')
            require(result.get('configuration') == cfg and result.get('case') == normalized_case(cfg),
                    f'Configuration mismatch: {path}')
            cfg_sha = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
            require(result.get('configuration_sha256') == cfg_sha, f'Configuration SHA mismatch: {path}')
            require(result.get('n_documents') == len(expected[task]), f'Result document count mismatch: {path}')
            document_path = full_dir / f'{stem}.documents.jsonl'
            sealed = result['document_artifact']
            require(Path(sealed['path']).name == document_path.name, f'Document artifact name mismatch: {path}')
            verify_artifact(document_path, sealed)
            rows = validate_rows(document_path, task, expected[task], complete=True)
            require(all(rows[k] == v for k,v in progress_rows.items()), f'Completed/progress row disagreement: {path}')
            require(set(result['metrics']) == set(METRICS), f'Unexpected aggregate metrics: {path}')
            metrics = {m:statistics.mean(r['metrics'][m] for r in rows.values()) for m in METRICS}
            require(all(type(result['metrics'][m]) in (int,float) and math.isfinite(result['metrics'][m])
                        and abs(result['metrics'][m]-metrics[m]) < 1e-12 for m in METRICS),
                    f'Aggregate/document metric mismatch: {path}')
            audit = result.get('execution_audit', {})
            require(audit.get('every_scored_target_used_24_decode_layers') is True,
                    f'Missing real 24-layer decode audit: {path}')
            token_count = sum(c['tokens'] for row in rows.values() for c in row['choices'])
            require(audit.get('original_tokenized_requests') == token_count, f'Scored token audit mismatch: {path}')
            record = dict(task=task, case=cfg['name'], configuration=cfg, n_documents=len(rows), metrics=metrics,
                          code_commit=commit, elapsed_seconds=result.get('elapsed_seconds'),
                          active_sampling_stats=result.get('active_sampling_stats'),
                          result_sha256=sha(path), document_sha256=sha(document_path))
            records[(task, cfg['name'])] = rows
            cases.append(record)
            for artifact in (path, document_path):
                artifacts[str(artifact.relative_to(root))] = dict(sha256=sha(artifact), bytes=artifact.stat().st_size)
    for case in cases:
        reference = records.get((case['task'], 'bf16'))
        case['paired_vs_bf16'] = paired(reference, records[(case['task'],case['case'])]) if reference else None
        case['delta_pp_vs_bf16'] = ({m:case['paired_vs_bf16'][m]['net_change_pp'] for m in METRICS}
                                   if reference else None)
    groups = []
    for task in TASKS:
        for group in ('bf16', 'ffn_only', 'joint_S64', 'joint_S128', 'joint_S512'):
            members = [c for c in cases if c['task']==task and
                       (c['case']=='bf16' if group=='bf16' else c['case'].startswith(group+'_s'))]
            count = 1 if group=='bf16' else 3
            row = dict(task=task, group=group, expected_seeds=[0] if group=='bf16' else [0,1,2],
                       completed_seeds=[c['configuration']['seed'] for c in members],
                       state='completed' if len(members)==count else ('partial_seeds' if members else 'pending'),
                       n_documents_per_seed=TASKS[task][1],
                       split='1000题预先固定子集，非完整HellaSwag' if task=='hellaswag' else '完整评测split')
            row['metrics'] = ({m:summary_stats([c['metrics'][m] for c in members]) for m in METRICS} if members else None)
            row['delta_pp_vs_bf16'] = ({m:summary_stats([c['delta_pp_vs_bf16'][m] for c in members]) for m in METRICS}
                                      if members and all(c['delta_pp_vs_bf16'] is not None for c in members) else None)
            groups.append(row)
    return dict(schema_version=1, execution_commit=commit, status='completed' if not pending else 'pending',
        n_completed_cases=len(cases), n_expected_cases=len(TASKS)*len(configurations),
        n_pending_cases=len(pending), tasks=meta['statistics'], groups=groups, cases=cases,
        partial_task_progress=partial, pending=pending, artifacts=artifacts,
        protocol=dict(metrics='Official lm-eval 0.4.8 acc / acc_norm; acc_norm uses choice character count',
            seeds='No cross-seed ensemble; mean and population standard deviation across independent seeds',
            baseline='Fresh matched cached BF16 only, never historical native Harness scores',
            pairing='Per seed and task, identical doc IDs; report correct→wrong / wrong→correct',
            attention='Actual 24-layer single-token scoring decode; original multi-token prefix Attention',
            short_context='Prompts/answers here are short; fixed eight 64-token blocks can retain all K. Inspect active_sampling_stats; this is not a long-context pruning test',
            partial='Unsealed progress shown separately with its n; never called a complete task or compared to full baseline',
            commit='execution_commit is frozen runtime SHA, not collector Git HEAD'))


def render_chinese(report):
    lines = ['# Qwen联合随机计算：基础任务准确率', '',
             f'已完成 {report["n_completed_cases"]}/{report["n_expected_cases"]} 项；待完成 {report["n_pending_cases"]} 项。', '',
             '以下均为0-shot；百分数为准确率，±为种子总体标准差，Δ为相对本轮BF16的百分点。缺失项保留待完成，不补零。', '',
             '| 任务 | 方案 | 完整种子数 | 每种子题数 | acc（%） | acc_norm（%） | Δacc（百分点） | Δacc_norm（百分点） |',
             '|---|---|---:|---:|---:|---:|---:|---:|']
    labels = dict(bf16='原始BF16', ffn_only='仅四档32拍FFN', joint_S64='FFN＋Ising64', joint_S128='FFN＋Ising128', joint_S512='FFN＋Ising512')
    for row in report['groups']:
        def fmt(metric, delta=False):
            values = row['delta_pp_vs_bf16'] if delta else row['metrics']
            if values is None:
                return '待完成'
            x = values[metric]; scale = 1 if delta else 100
            return f'{x["mean"]*scale:.3f} ± {x["std"]*scale:.3f}'
        task = row['task'] + ('（固定1000题子集）' if row['task']=='hellaswag' else '')
        lines.append(f'| {task} | {labels[row["group"]]} | {len(row["completed_seeds"])}/{len(row["expected_seeds"])} | '
                     f'{row["n_documents_per_seed"]} | {fmt("acc")} | {fmt("acc_norm")} | {fmt("acc",True)} | {fmt("acc_norm",True)} |')
    lines += ['', 'HellaSwag是推理前按固定种子抽取的1000题子集，不能引用为完整10042题结果。', '',
              '这些题的上下文很短，当前固定8块筛选可能保留全部K；此处主要检验FFN和有限Ising采样对答题的影响，不能据此证明长上下文筛选质量。JSON逐项保留实际候选比例。', '',
              '逐种子配对记录保存在JSON的cases[].paired_vs_bf16：分别列出原对变错、原错变对、均对和均错；不使用跨种子投票。']
    if report['partial_task_progress']:
        lines += ['', '仅有进度文件的任务（不计入上表完成结果，也不与全量BF16比较）：', '', '| 任务 | 配置 | 已有题数 / 预定题数 | 当前片段acc（%） | 当前片段acc_norm（%） |', '|---|---|---:|---:|---:|']
        for row in report['partial_task_progress']:
            lines.append(f'| {row["task"]} | {row["case"]} | {row["n_documents"]}/{row["n_expected_documents"]} | '
                         f'{100*row["metrics"]["acc"]:.3f} | {100*row["metrics"]["acc_norm"]:.3f} |')
        lines += ['', '进度文件尚无运行端完成封印；这里记录本地SHA，仅作为可恢复进度，不代表正式完成。']
    lines += ['', f'冻结执行源码：`{report["execution_commit"]}`。汇总代码可以晚于该版本，不改变已执行源码。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Downloaded output root preserving full/ layout')
    parser.add_argument('--output', required=True, help='JSON summary path')
    parser.add_argument('--report', help='Chinese Markdown report path')
    parser.add_argument('--execution-commit', help='Expected exact frozen source SHA (optional additional guard)')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    report = collect(args.input, args.execution_commit)
    if args.require_complete and report['n_pending_cases']:
        raise ValueError(f'{report["n_pending_cases"]} cases still pending')
    for name, text in [(args.output, json.dumps(report, ensure_ascii=False, indent=2)+'\n'),
                       (args.report, render_chinese(report))]:
        if name:
            path = Path(name); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps(dict(status=report['status'], completed=report['n_completed_cases'], pending=report['n_pending_cases'])))


if __name__ == '__main__':
    main()
