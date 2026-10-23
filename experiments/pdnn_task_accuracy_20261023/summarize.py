"""Independently audit downloaded Issue145 originals; Python standard library only.

No inference, task-label inspection, training, source mutation or remote access.
Official process_results was run/read back on the server; this auditor checks
its saved per-document outputs and numerical aggregates, not the task metric
implementation. Preserve tokenized/, smoke/ and full/ under --results.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import shutil
import statistics
import subprocess


TASKS = {
    'piqa': (1838, '4c9f51a5292e593fe5632b28f92c8405171a0102789840f42bd949b804e3a9ab',
             '40e1677bba609c8801deacc171d76f3e24c083f365c95a1cbda7520c923dfea2'),
    'arc_easy': (2376, '922c84ada5637d14c1d1483cf8e15c828b0c6051da9be3d2543bc5ff53a26044',
                 '4160597d618ae851c7eb04e281574f3f654776216ac6b6641588d64527b47177'),
    'hellaswag': (1000, 'b3bedbdf96e593ddb07a08f71bb7bf5906b85af0953f798e87a517097b1abed0',
                  '899813071e1e95efafec90f856e1987d2150fa4d020fc005df6962c259f660cd'),
}
METRICS = ('acc', 'acc_norm')
MODEL_SHA = '88c142557820ccad55bb59756bfcfcf891de9cc6202816bd346445188a0ed342'
CHECKPOINT_SHAS = {
    10: 'b4a7529fd356544df1f06c14dcb6f92e0400337f6420d013ded50868c436df8f',
    11: '584baf26865d311de53505d72451e87a49940122130427002e696f03475ff351',
    12: '43c66f3b895d3ce237a42e7cdb2cf768d0441fa83ae45c0802b41e7aaa9bab2d',
    13: '65c5cf5e389eebb3ff41ef2e697052737849f48e615fc8e1ae513962c9a1bc51',
}
METRIC_SCOPE = ('Official lm_eval 0.4.8 process_results was run and saved outputs were '
                'independently read back by the server runner. This local audit verifies '
                'saved identities, scores, binary metrics and aggregation; it does not '
                'recompute official metrics from labels or assume token-normalized acc_norm.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def expected_variants():
    shared = dict(samples=4, batch=16, context=2048)
    values = [dict(shared, name='bf16', layers=[], seed=0)]
    for prefix, indices in (('pdnn2_subset_joint4', [10, 12]), ('pdnn4_joint1000', [10, 11, 12, 13])):
        values += [dict(shared, name=f'{prefix}_s{s}', layers=indices, seed=s) for s in range(3)]
    return {v['name']: v for v in values}


class Audit:
    def __init__(self, root, source_root=None, allow_partial=False):
        self.root = Path(root).resolve(strict=True)
        self.source = Path(source_root).resolve(strict=True) if source_root else None
        self.partial = allow_partial
        self.artifacts, self.checks = {}, []
        self.meta = read(self.root / 'TASK_DATA.json')
        self.commit = self.meta.get('code_commit', '')
        require(re.fullmatch('[0-9a-f]{40}', self.commit), 'exact frozen execution commit required')
        paths = [PurePosixPath(e['path']) for e in self.meta['tokenized'].values()]
        require(paths and all(p.is_absolute() and p.parent.name == 'tokenized' for p in paths),
                'tokenized source paths must be absolute runroot/tokenized paths')
        self.remote = paths[0].parent.parent
        require(all(p.parent.parent == self.remote for p in paths), 'mixed source run roots')
        require(str(self.remote).startswith('/home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/runs/'),
                'unexpected source personal run root')

    def local(self, relative):
        rel = PurePosixPath(relative)
        require(not rel.is_absolute() and '\\' not in str(rel) and '..' not in rel.parts,
                'unsafe local relative artifact path')
        value = self.root.joinpath(*rel.parts).resolve(strict=True)
        require(value.is_relative_to(self.root) and value.is_file(), 'artifact escapes results root')
        return value

    def record(self, path):
        relative = path.relative_to(self.root).as_posix()
        self.artifacts[relative] = dict(bytes=path.stat().st_size, sha256=sha(path))
        return path

    def artifact(self, entry):
        remote = PurePosixPath(entry['path'])
        require(remote.is_absolute() and '\\' not in entry['path'] and '..' not in remote.parts,
                'invalid declared server artifact path')
        require(remote.is_relative_to(self.remote), 'unknown server artifact outside anchored run root')
        path = self.local(remote.relative_to(self.remote).as_posix())
        require(path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'],
                'declared artifact bytes/SHA mismatch: ' + str(path))
        return self.record(path)

    def checkpoint(self, entry, expected, runtime=False):
        for key in ('layer', 'path', 'bytes', 'sha256', 'phase', 'step'):
            require(entry.get(key) == expected[key], 'checkpoint field mismatch: ' + key)
        if runtime:
            require(entry['student_type'] == 'full_path_bipolar_pdnn_v1' and entry['samples'] == 4
                    and entry['parameters'] == 8722048 and entry['dtype'] == 'torch.bfloat16'
                    and entry['device'] == 'cuda:0' and entry['training_args_layer'] == expected['layer'],
                    'runtime P-DNN operator identity differs')
            cfg = entry['student_config']
            required = dict(input_size=896, hidden_sizes=[4864], output_size=896,
                            input_temperature=.25, hidden_temperature=1., coding='bipolar',
                            learnable_encoding=False, minimum_temperature=.001,
                            learnable_thresholds=True, architecture='serial', input_encoding='sigmoid', input_bits=1)
            require(cfg == required, 'runtime complete-path P-DNN configuration differs')
            source = entry['source_student_config']
            require(all(source[k] == required[k] for k in source), 'source/effective student configuration differs')

    def bindings(self, result):
        require(result['code_commit'] == self.commit and result['source_sha256'] == self.meta['source_sha256'],
                'execution source binding differs')
        require(result['task_data_sha256'] == sha(self.root / 'TASK_DATA.json'), 'TASK_DATA binding differs')
        require(result['config'] == self.meta['config'], 'config artifact binding differs')

    def source_blob(self, relative):
        """Read the execution commit, never changed working files or a remote."""
        executable = shutil.which('git')
        if executable is None:
            executable = next((p for p in ('C:/Program Files/Git/cmd/git.exe', '/usr/bin/git', '/usr/local/bin/git')
                               if Path(p).is_file()), None)
        require(executable is not None, 'source verification requires the local Git executable')
        response = subprocess.run([executable, '--no-lazy-fetch', '-C', str(self.source), 'show',
                                   self.commit + ':' + relative], capture_output=True, timeout=30,
                                  env=dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0'))
        require(response.returncode == 0, 'frozen Git object unavailable locally: ' + relative)
        return response.stdout

    def metadata(self):
        meta = self.meta
        self.record(self.local('TASK_DATA.json'))
        require(meta['status'] == 'completed' and meta['code_commit'] == self.commit,
                'TASK_DATA execution version/status differs')
        require(set(meta['tasks']) == set(TASKS) == set(meta['tokenized']) == set(meta['statistics']),
                'TASK_DATA must contain exactly the three frozen tasks')
        require(meta['num_fewshot'] == 0 and meta['chat_template'] is False, 'prompt protocol differs')
        require(meta['environment']['lm_eval'] == '0.4.8' and meta['environment']['transformers'] == '4.45.2'
                and meta['environment']['cuda_visible_devices'] == '', 'CPU task preparation environment differs')
        config = meta['configuration']
        require(config['protocol_version'] == 1 and config['model_weight_sha256'] == MODEL_SHA,
                'model/protocol differs')
        variants = expected_variants()
        require(len(config['variants']) == 7 and {v['name']: v for v in config['variants']} == variants,
                'configuration must contain the seven exact frozen variants')
        require(meta['model']['files']['model.safetensors']['sha256'] == MODEL_SHA
                and meta['model']['model_config']['num_hidden_layers'] == 24
                and meta['model']['model_config']['hidden_size'] == 896, 'base model identity differs')
        checkpoints = {e['layer']: e for e in config['checkpoints']}
        require(len(config['checkpoints']) == 4 and set(checkpoints) == set(CHECKPOINT_SHAS),
                'configuration checkpoint coverage differs')
        for index, expected in checkpoints.items():
            require(expected['sha256'] == CHECKPOINT_SHAS[index] and expected['bytes'] == 34893135
                    and expected['phase'] == 'joint_end_to_end_distillation' and expected['step'] == 1000
                    and PurePosixPath(expected['path']).name == f'best_layer{index}.pt'
                    and '/results/reference_1000/' in expected['path'], 'frozen current checkpoint identity differs')
        require(meta['checkpoints'] == config['checkpoints'], 'data/config checkpoint bindings differ')
        cfg_entry = meta['config']
        require(meta['source_sha256']['experiments/pdnn_task_accuracy_20261023/config.json'] == cfg_entry['sha256'],
                'config/source manifest SHA differs')
        remote_cfg = PurePosixPath(cfg_entry['path'])
        source_suffix = PurePosixPath('experiments/pdnn_task_accuracy_20261023/config.json')
        require(str(remote_cfg).endswith('/' + str(source_suffix)) and f'/snapshots/{self.commit}/' in str(remote_cfg),
                'config not bound to frozen snapshot')
        if self.source:
            for relative, checksum in meta['source_sha256'].items():
                rel = PurePosixPath(relative)
                require(not rel.is_absolute() and '..' not in rel.parts and '\\' not in relative, 'unsafe source path')
                path = self.source.joinpath(*rel.parts).resolve()
                require(path.is_relative_to(self.source), 'source symlink escapes source root')
                content = self.source_blob(relative)
                require(hashlib.sha256(content).hexdigest() == checksum, 'frozen source bytes differ: ' + relative)
            cfg_content = self.source_blob(str(source_suffix))
            require(len(cfg_content) == cfg_entry['bytes'] and json.loads(cfg_content) == config,
                    'frozen source config content/size differs')
            self.checks.append('all frozen execution source bytes independently checked; extra post-execution files excluded')
        else:
            self.checks.append('execution source bindings agree between saved artifacts; source bytes not independently supplied')
        manifest_path = self.root / 'SOURCE_MANIFEST.json'
        if manifest_path.exists():
            manifest = read(self.record(self.local('SOURCE_MANIFEST.json')))
            require(manifest['code_commit'] == self.commit and
                    {k: v['sha256'] for k, v in manifest['files'].items()} == meta['source_sha256'],
                    'downloaded source manifest differs from execution bindings')
        cpu = read(self.record(self.local('CPU_PREFLIGHT.json')))
        require(cpu['user'] == 'Weican_Chen' and cpu['cuda_visible_devices'] == '' and cpu['training'] is False,
                'CPU artifact preflight identity differs')
        require(len(cpu['checkpoints']) == 4 and {e['layer'] for e in cpu['checkpoints']} == set(checkpoints),
                'CPU checkpoint coverage differs')
        for entry in cpu['checkpoints']:
            self.checkpoint(entry, checkpoints[entry['layer']])
            require(entry['strict_state_loaded'] is True and entry['student_type'] == 'full_path_bipolar_pdnn_v1',
                    'CPU strict-state load not confirmed')
        docs = {}
        for task, (count, ids_sha, data_sha) in TASKS.items():
            require(meta['tasks'][task]['dataset_sha256'] == cpu['data'][task]['sha256'] == data_sha,
                    'dataset identity mismatch: ' + task)
            rows = lines(self.artifact(meta['tokenized'][task]))
            ids = [r['doc_id'] for r in rows]
            require(len(rows) == count and len({r['id'] for r in rows}) == count and len(set(ids)) == count,
                    'tokenized document count or uniqueness differs: ' + task)
            require(hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest() == ids_sha
                    == meta['statistics'][task]['selected_doc_ids_sha256'], 'selected document IDs differ: ' + task)
            expected_ids = sorted(random.Random(20261019).sample(range(10042), 1000)) if task == 'hellaswag' else list(range(count))
            require(ids == expected_ids, 'task IDs differ from predeclared sampling: ' + task)
            for row in rows:
                require(row['task'] == task and row['id'] == f"{task}:{row['doc_id']}"
                        and len(row['context_ids']) >= 3 and len(row['choices_ids']) >= 2,
                        'tokenized request identity differs')
                require(all(a and all(type(t) is int and 0 <= t < 151936 for t in a)
                            for a in [row['context_ids'], *row['choices_ids']]), 'invalid frozen token IDs')
                require(len(row['context_ids']) + max(map(len, row['choices_ids'])) - 1 <= 2048,
                        'frozen request exceeds context bound')
            s = meta['statistics'][task]
            require(s['documents'] == count and s['requests'] == sum(len(r['choices_ids']) for r in rows)
                    and s['answer_targets'] == sum(len(a) for r in rows for a in r['choices_ids']), 'request statistics mismatch')
            docs[task] = rows
        self.variants, self.checkpoints, self.docs = variants, checkpoints, docs
        self.checks.append('CPU, data, config, model/checkpoint identities, tokenized bytes and fixed IDs verified')

    def execution(self, result, requested):
        a, selected = result['execution_audit'], result['configuration']['layers']
        require(a['completed_documents'] == len(requested), 'execution document coverage differs')
        targets = sum(len(v) for row in requested for v in row['choices_ids'])
        require(a['scored_choice_tokens'] == a['original_tokenized_requests'] == targets,
                'not every declared choice token scored exactly once')
        require(a['shared_first_query_rows'] == len(requested)
                and a['shared_first_query_counted_once_for_actual_execution'] is True
                and a['every_scored_target_used_24_decoder_ffn_layers'] is True,
                'first-target/decode audit missing')
        for phase in ('prefill', 'decode'):
            count = a[f'actual_{phase}_calls']
            require(type(count) is int and count > 0, 'missing actual execution calls')
            for module in ('decoder', 'ffn'):
                require(a[f'{module}_{phase}_calls_per_layer'] == [count] * 24,
                        'not all 24 decoder/FFN layers executed every call')
            coverage = a[f'ffn_{phase}_tokens_per_layer']
            require(len(coverage) == 24 and len(set(coverage)) == 1 and coverage[0] > 0,
                    'FFN token coverage differs across layers')
            require(a[f'replaced_{phase}_calls'] == {str(i): count for i in selected},
                    'selected P-DNN module execution coverage differs')
        require(a['replaced_layers'] == selected, 'executed replacement layers differ')
        require(a['actual_decode_query_rows'] == a['shared_first_query_rows'] + a['branch_query_rows'] + a['dummy_query_rows']
                == a['ffn_decode_tokens_per_layer'][0], 'decode active/dummy row arithmetic differs')
        require(a['branch_query_rows'] == targets - sum(len(r['choices_ids']) for r in requested),
                'scored continuation target coverage differs')
        require(a['first_token_logit_reuses'] == sum(len(r['choices_ids']) - 1 for r in requested),
                'shared first-token reuse arithmetic differs')

    def case(self, path, scope, task, variant, requested):
        result = read(self.record(path))
        name = variant['name'] + '_' + task
        require(result['status'] == 'completed' and result['case'] == name and result['scope'] == scope
                and result['task'] == task and result['configuration'] == variant
                and result['variant'] == {k: v for k, v in variant.items() if k != 'name'}
                and result['n_documents'] == len(requested), 'case identity/configuration differs: ' + name)
        self.bindings(result)
        require(result['training'] is False and result['dtype'] == 'torch.bfloat16' and result['device'] == 'cuda:0'
                and result['model_identity'] == self.meta['model'], 'case model/training identity differs')
        require(result['environment']['lm_eval'] == '0.4.8' and result['environment']['transformers'] == '4.45.2',
                'evaluation environment differs')
        require(finite(result['elapsed_seconds']) and result['elapsed_seconds'] >= 0
                and type(result['peak_allocated_bytes']) is int and result['peak_allocated_bytes'] > 0,
                'invalid software timing/VRAM measurement')
        actual = result['checkpoint_identities']
        require(len(actual) == len(variant['layers']) and [e['layer'] for e in actual] == variant['layers'],
                'case checkpoint coverage differs')
        for entry in actual:
            self.checkpoint(entry, self.checkpoints[entry['layer']], runtime=True)
        rows = lines(self.artifact(result['document_artifact']))
        expected = {r['id']: r for r in requested}
        require(len(rows) == len(expected) and len({r['id'] for r in rows}) == len(rows)
                and {r['id'] for r in rows} == set(expected), 'case per-document coverage/uniqueness differs')
        for row in rows:
            original = expected[row['id']]
            require(row['task'] == task and row['doc_id'] == original['doc_id'], 'per-document identity/gold alignment differs')
            require(len(row['choices']) == len(original['choices_ids']), 'choice count differs')
            for value, tokens in zip(row['choices'], original['choices_ids']):
                require(type(value['tokens']) is int and value['tokens'] == len(tokens)
                        and type(value['is_greedy']) is bool and finite(value['logprob']) and value['logprob'] <= 1e-5,
                        'choice token alignment or logprob validity differs')
            require(set(row['metrics']) == set(METRICS) and all(
                type(v) in (int, float) and v in (0, 1) for v in row['metrics'].values()), 'metrics must be binary acc/acc_norm')
        means = {key: sum(r['metrics'][key] for r in rows) / len(rows) for key in METRICS}
        require(means == result['metrics'], 'saved aggregate differs from per-document metrics')
        progress = lines(self.artifact(result['progress_artifact']))
        require(progress and progress[0].get('event') == 'started' and progress[0]['case'] == name
                and progress[0]['code_commit'] == self.commit, 'progress must start with the declared case claim')
        completed = progress[1:]
        require(len(completed) == len(rows) and len({r['id'] for r in completed}) == len(rows)
                and {r['id']: r for r in completed} == {r['id']: r for r in rows},
                'progress documents must match final identities/choices/metrics exactly once')
        self.execution(result, requested)
        if scope == 'smoke':
            gates = result['smoke_gates']
            require(set(gates) == ({'replay', 'option_permutation', 'independent_cached_bf16'} if not variant['layers']
                                  else {'replay', 'option_permutation'}), 'smoke gate coverage differs')
            require(all(g['passed'] is True and g['tolerance'] == 1e-6
                        and finite(g['max_absolute_sum_logprob_difference'])
                        and 0 <= g['max_absolute_sum_logprob_difference'] <= g['tolerance'] for g in gates.values()),
                    'real-model smoke gate failed')
        else:
            require(result['ready_sha256'] == sha(self.root / 'READY.json'), 'full case not bound to READY')
        return dict(case=name, task=task, configuration=variant, n_documents=len(rows), metrics=means,
                    metric_counts={k: sum(r['metrics'][k] for r in rows) for k in METRICS},
                    elapsed_seconds=result['elapsed_seconds'], peak_allocated_bytes=result['peak_allocated_bytes'],
                    software_measurement_only=True, slurm_job_id=result['slurm_job_id'])

    def run(self):
        self.metadata()
        ready_path = self.root / 'READY.json'
        cases, missing = [], []
        expected_full = {v['name'] + '_' + t for t in TASKS for v in self.variants.values()}
        if ready_path.exists():
            ready = read(self.record(self.local('READY.json')))
            require(ready['status'] == 'ready', 'READY status differs')
            self.bindings(ready)
            expected_smoke = {(t, v['name']) for t in TASKS for v in self.variants.values() if v['seed'] == 0}
            require(len(ready['cases']) == 9, 'READY requires nine cases')
            seen = set()
            for entry in ready['cases']:
                path = self.artifact(entry)
                require(path.parent == self.root / 'smoke', 'READY must reference smoke directory')
                value = read(path)
                key = (value['task'], value['configuration']['name'])
                require(key in expected_smoke and key not in seen, 'duplicate or unexpected READY smoke case')
                seen.add(key)
                rows = self.docs[key[0]]
                selected = {rows[0]['id'], max(rows, key=lambda d: (len(d['context_ids']), d['id']))['id']}
                self.case(path, 'smoke', key[0], self.variants[key[1]], [r for r in rows if r['id'] in selected])
            require(seen == expected_smoke, 'incomplete nine-case smoke matrix')
            self.checks.append('nine READY-bound real-GPU smoke cases, nested original bytes, replay/permutation/BF16 oracle verified')
        else:
            require(self.partial, 'READY.json missing; complete report forbidden')
            missing.append('READY.json')
        if (self.root / 'full').exists():
            observed = {p.stem for p in (self.root / 'full').glob('*.json')}
            require(observed <= expected_full, 'unexpected full case files')
        for task in TASKS:
            for variant in self.variants.values():
                name = variant['name'] + '_' + task
                path = self.root / 'full' / (name + '.json')
                if path.exists():
                    require(ready_path.exists(), 'completed full case without READY')
                    cases.append(self.case(self.local('full/' + path.name), 'full', task, variant, self.docs[task]))
                else:
                    missing.append(name)
        complete = len(cases) == 21 and not missing
        require(complete or self.partial, '21 completed full cases required; missing: ' + ', '.join(missing))
        self.checks.append('all available full cases passed raw/progress/coverage/source/operator/numerical checks')
        groups = {}
        lookup = {r['case']: r for r in cases}
        for task in TASKS:
            baseline = lookup.get('bf16_' + task)
            item = dict(documents=TASKS[task][0], split=self.meta['tasks'][task]['split'],
                        full_split=task != 'hellaswag', baseline=baseline, groups={})
            for prefix in ('pdnn2_subset_joint4', 'pdnn4_joint1000'):
                selected = [lookup.get(f'{prefix}_s{s}_{task}') for s in range(3)]
                if all(selected) and baseline:
                    item['groups'][prefix] = {key: dict(
                        seeds=[r['metrics'][key] for r in selected],
                        mean=statistics.mean(r['metrics'][key] for r in selected),
                        inference_seed_sample_std=statistics.stdev(r['metrics'][key] for r in selected),
                        delta_vs_bf16_percentage_points=100 * (statistics.mean(r['metrics'][key] for r in selected)
                                                             - baseline['metrics'][key])) for key in METRICS}
            groups[task] = item
        return dict(status='complete' if complete else 'partial', code_commit=self.commit,
                    metric_verification=METRIC_SCOPE, completed_cases=len(cases), expected_cases=21,
                    missing=missing, cases=cases, tasks=groups, checkpoints=self.meta['checkpoints'],
                    source_bytes_independently_verified=self.source is not None,
                    no_cross_task_average=True,
                    uncertainty='Sample standard deviation across three inference seeds; not document sampling error, confidence intervals or training-seed variation.',
                    software_timing_scope='GPU software emulation only; timings/peak VRAM are not hardware latency, energy, power or area.')


def report(summary):
    text = ['# P-DNN任务准确率核验', '',
            '状态：' + ('21项完整评估均已核验。' if summary['status'] == 'complete' else
                        f"部分完成：{summary['completed_cases']}/21；不能作完整比较结论。"), '',
            '模型：两层为当前joint4权重的10/12子集，非历史6/12模型；四层为10/11/12/13的reference_1000现存权重。'
            '已逐一绑定本次SHA，不能直接套用旧四层PPL或宣称是旧checkpoint。N=4条完整随机路径，BF16浮点权重；未训练或W8量化。', '',
            'PIQA、ARC-Easy使用完整指定split；HellaSwag只用预先固定的1000/10042题，非完整HellaSwag。', '',
            '| 任务 | 模型 | acc (%) | acc_norm (%) | 相对BF16 acc / acc_norm (百分点) |',
            '|---|---|---:|---:|---:|']
    for task, values in summary['tasks'].items():
        base = values['baseline']
        if base:
            text.append(f"| {task} | BF16 | {100*base['metrics']['acc']:.3f} | {100*base['metrics']['acc_norm']:.3f} | 0 / 0 |")
        for name, metrics in values['groups'].items():
            label = 'P-DNN两层10/12' if name.startswith('pdnn2') else 'P-DNN四层10–13'
            displays = [f"{100*metrics[k]['mean']:.3f} ± {100*metrics[k]['inference_seed_sample_std']:.3f}" for k in METRICS]
            deltas = [f"{metrics[k]['delta_vs_bf16_percentage_points']:+.3f}" for k in METRICS]
            text.append(f"| {task} | {label} | {displays[0]} | {displays[1]} | {' / '.join(deltas)} |")
    text += ['', '±为三个推理seed的样本标准差，不是题目统计误差、置信区间或训练初始化差异；不对三任务简单取平均。', '',
             '官方lm_eval 0.4.8 process_results已在服务器逐题执行并对保存结果回读。此处仅审计原件、请求身份、分数、二值指标及数值聚合，'
             '没有本地重算官方指标或读取标签；acc_norm遵循官方选项字符长度归一化。', '',
             'SUMMARY.json逐case列出软件推理耗时和峰值显存，仅是GPU随机仿真参考，不代表硬件功耗、面积或延迟。', '']
    if summary['missing']:
        text += ['待完成：' + '、'.join(summary['missing']), '']
    return '\n'.join(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True)
    parser.add_argument('--output', required=True, help='new empty audit output directory')
    parser.add_argument('--source-root', help='optional execution checkout; verify only frozen manifest entries')
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    audit = Audit(args.results, args.source_root, args.allow_partial)
    output = Path(args.output).resolve()
    require(output != audit.root and not output.is_relative_to(audit.root), 'audit output must be outside raw originals')
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())), 'audit output must be new or empty')
    summary = audit.run()
    validation = dict(status='passed', completion=summary['status'], original_results_root=str(audit.root),
                      anchored_server_run_root=str(audit.remote), code_commit=audit.commit,
                      checks=audit.checks, original_artifacts=audit.artifacts, metric_scope=METRIC_SCOPE,
                      source_bytes_independently_verified=audit.source is not None,
                      created_utc=datetime.now(timezone.utc).isoformat())
    output.mkdir(parents=True, exist_ok=True)
    for name, payload in (('SUMMARY.json', summary), ('VALIDATION.json', validation)):
        with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
    with (output / 'REPORT_ZH.md').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(report(summary))
    print(json.dumps(dict(status=summary['status'], completed_cases=summary['completed_cases'],
                          output=str(output)), ensure_ascii=False))


if __name__ == '__main__':
    main()
