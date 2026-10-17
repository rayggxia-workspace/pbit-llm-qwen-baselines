"""Validate and compact the immutable Issue 14 Llama-2-7B execution outputs.

Only completed REAL_LLAMA2 workloads are accepted.  BF16 PPL is independent
evidence and never assigned to a sampled TLM case.  Long raw files stay on the
server; this program indexes their original bytes rather than rewriting them.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from functools import lru_cache
from pathlib import Path


REPOSITORY = 'meta-llama/Llama-2-7b-hf'
REVISION = '01c7f73d771dfac7d292323805ebc428287df4f9'
TLM_COMMIT = 'b5964b165dfead06676580029235bf5e952b5dad'
BASELINE_COMMIT = '9ee1ab47d0317430212364e75adb78abec9797fb'
CORPUS_SHA256 = '173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08'
PREFIX_SHA256 = '5c208664955a0c5e4d2fb19d1a018559bf02eccd36d6aafb2a77b0e5d8cabca8'
REAL_KIND = 'REAL_LLAMA2_7B_POST_ROPE_QK_LOGITS'
CONTEXTS = (512, 1024, 2048, 4096)
CASES = ('bf16_dense', 'int8_dense', 'sc_dense', 'sc_pv',
         'sc_screen_exact', 'sc_screen_pv', 'sc_ising', 'sc_screen_ising')
BACKENDS = ('link_Staggered', 'dramsys_Staggered', 'dramsys_NoPowerDown')
SHAPE = dict(model_type='llama', hidden_size=4096, intermediate_size=11008,
             num_hidden_layers=32, num_attention_heads=32, num_key_value_heads=32,
             max_position_embeddings=4096, vocab_size=32000, rms_norm_eps=1e-5,
             rope_theta=10000.0, tie_word_embeddings=False,
             hidden_act='silu', attention_bias=False)
SCALARS = ('backend', 'case', 'context', 'seed', 'engines', 'samples_per_head',
           'ms_per_token', 'mJ_per_token', 'area_mm2', 'area_feasible',
           'attention_ms_per_token', 'FFN_ms_per_token', 'QK_fraction',
           'K_physical_fraction', 'V_physical_fraction', 'K_MiB_per_token',
           'V_MiB_per_token', 'summary_MiB_per_token', 'weight_GiB_per_token',
           'work_peak_MiB', 'SRAM_MiB', 'SRAM_area_mm2',
           'DRAM_core_mJ_per_token', 'DRAM_interface_proxy_mJ_per_token', 'wall_seconds')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write('\n')


def artifact(path):
    path = Path(path)
    return dict(path=str(path.resolve()), bytes=path.stat().st_size, sha256=digest(path))


def finite_nonnegative(value, label):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0, 'invalid finite nonnegative ' + label)


def valid_identity(identity):
    require(identity.get('repository') == REPOSITORY and identity.get('revision') == REVISION,
            'model must be the pinned official Llama 2 7B Base checkpoint')
    require(all(identity.get('model_shape', {}).get(k) == v for k, v in SHAPE.items()),
            'model identity shape mismatch')
    files = identity.get('files', {})
    required = {'config.json', 'tokenizer.json', 'tokenizer.model', 'tokenizer_config.json',
                'model-00001-of-00002.safetensors', 'model-00002-of-00002.safetensors'}
    require(required <= files.keys(), 'incomplete model/tokenizer file identity')
    for name, record in files.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and '\\' not in name,
                'unsafe identity filename')
        require(re.fullmatch('[0-9a-f]{64}', record.get('sha256', '')) is not None
                and isinstance(record.get('bytes'), int) and record['bytes'] > 0,
                'invalid model file identity: ' + name)


def identity_at(project):
    paths = [p for p in (project/'model_identity.json', project/'outputs/model_identity.json') if p.exists()]
    require(bool(paths), 'missing model_identity.json')
    require(len({digest(p) for p in paths}) == 1, 'model identity aliases have different bytes')
    identity = read_json(paths[0])
    valid_identity(identity)
    return identity, paths[0]


def expected_keys():
    expected = set()
    for backend, contexts in [('link_Staggered', CONTEXTS),
                              ('dramsys_Staggered', (2048, 4096))]:
        for context in contexts:
            for case in CASES:
                for seed in ((0,) if case in CASES[:3] else (0, 1, 2)):
                    expected.add((backend, context, case, 8, seed))
    for context in (2048, 4096):
        for case in ('bf16_dense', 'sc_dense', 'sc_screen_pv', 'sc_screen_ising'):
            expected.add(('dramsys_NoPowerDown', context, case, 8, 0))
    require(len(expected) == 116, 'internal task matrix changed unexpectedly')
    return expected


def check_keys(rows):
    actual = [(r['backend'], r['context'], r['case'], r['engines'], r['seed']) for r in rows]
    require(len(actual) == len(set(actual)), 'duplicate scenario keys')
    missing, extra = expected_keys() - set(actual), set(actual) - expected_keys()
    require(not missing and not extra,
            'incomplete/unexpected task matrix: ' + repr(dict(missing=sorted(missing), extra=sorted(extra))))


@lru_cache(maxsize=4)
def trace_data(path):
    data = read_json(path)
    provenance = data['provenance']
    require(provenance.get('kind') == REAL_KIND, 'old/synthetic trace rejected')
    require(provenance.get('code', {}).get('commit') == TLM_COMMIT, 'wrong capture source commit')
    require(provenance.get('context') in CONTEXTS and provenance.get('decode_tokens') == 1,
            'trace context/decode mismatch')
    require(provenance.get('data', {}).get('sha256') == CORPUS_SHA256
            and provenance['data'].get('segment_start_token') == 201979
            and provenance['data'].get('first_2048_ids_sha256') == PREFIX_SHA256,
            'trace corpus/window identity mismatch')
    require(provenance.get('validation') and len(provenance['validation']) == 1
            and provenance['validation'][0].get('token') == 0
            and provenance['validation'][0].get('bitwise_equal') is True
            and provenance['validation'][0].get('max_abs_difference') == 0,
            'capture lacks unchanged BF16 bitwise reference')
    require(all(provenance.get('model_shape', {}).get(k) == v for k, v in SHAPE.items()),
            'trace shape mismatch')
    probabilities = {}
    for row in data['rows']:
        key = (row['token'], row['layer'], row['head'])
        require(key not in probabilities and key[0] == 0 and 0 <= key[1] < 32 and 0 <= key[2] < 32,
                'duplicate/out-of-range trace row')
        logits = row['logits']
        require(len(logits) == provenance['context'] and all(math.isfinite(x) for x in logits),
                'invalid trace logits')
        maximum = max(logits)
        weights = [math.exp(x - maximum) for x in logits]
        total = sum(weights)
        probabilities[key] = [value / total for value in weights]
    require(len(probabilities) == 32 * 32, 'missing trace heads')
    return dict(provenance=provenance, probabilities=probabilities, sha256=digest(path))


def baseline_evidence(project, identity, identity_path):
    directory = project/'outputs/bf16_baseline'
    summary = read_json(directory/'summary.json')
    protocol = read_json(directory/'protocol.json')
    source = read_json(directory/'source.json')
    manifest = read_json(directory/'ARTIFACT_MANIFEST.json')
    baseline_identity = read_json(directory/'identity.json')
    require(summary.get('status') == 'completed', 'BF16 full WT2 baseline is not completed')
    require(summary.get('model') == REPOSITORY and summary.get('revision') == REVISION
            and summary.get('code_commit') == source.get('commit') == BASELINE_COMMIT,
            'BF16 baseline model/source identity mismatch')
    require(summary.get('data_sha256') == protocol.get('raw_sha256') == CORPUS_SHA256,
            'BF16 corpus SHA mismatch')
    require(baseline_identity.get('repository') == REPOSITORY and baseline_identity.get('revision') == REVISION
            and baseline_identity.get('files') == {
                name:{key:record[key] for key in ('sha256', 'bytes')}
                for name, record in identity['files'].items()}
            and baseline_identity.get('manifest_sha256') == digest(identity_path),
            'BF16 model/tokenizer identity does not match TLM identity')
    require(protocol.get('name') == 'full_wikitext2_raw_sliding_window_ppl'
            and sorted(protocol.get('windows', [])) == [2048, 4096]
            and protocol.get('stride') == 512 and protocol.get('seed') == 0
            and protocol.get('batch_size') == 1 and protocol.get('add_special_tokens') is False
            and protocol.get('target_positions') == '1..N-1 exactly once',
            'unexpected BF16 PPL protocol')
    require(protocol.get('precision') == 'BF16 model; FP32 CE; FP64 NLL sum',
            'unexpected baseline precision')
    artifacts = []
    for name, record in manifest.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and '\\' not in name,
                'unsafe baseline artifact filename')
        path = directory/name
        current = artifact(path)
        require(current['bytes'] == record['bytes'] and current['sha256'] == record['sha256'],
                'BF16 artifact byte mismatch: ' + name)
        artifacts.append(current)
    required_files = {'summary.json', 'protocol.json', 'identity.json', 'source.json',
                      'environment.json', 'command.json', 'tokenization.json',
                      'ppl_2048.json', 'ppl_4096.json', 'windows_2048.jsonl', 'windows_4096.jsonl'}
    require(required_files <= manifest.keys(), 'baseline artifact manifest is incomplete')
    artifacts.append(artifact(directory/'ARTIFACT_MANIFEST.json'))
    tokenization = summary['tokenization']
    require(tokenization == read_json(directory/'tokenization.json')
            and tokenization['tokens'] > 4096
            and tokenization['expected_scored_tokens'] == tokenization['tokens'] - 1
            and re.fullmatch('[0-9a-f]{64}', tokenization['token_ids_sha256']) is not None,
            'BF16 tokenization identity/count mismatch')
    require(len(summary['ppl']) == 2 and {x['window'] for x in summary['ppl']} == {2048, 4096},
            'baseline needs both native evaluation windows')
    for record in summary['ppl']:
        require(record == read_json(directory/f"ppl_{record['window']}.json"), 'baseline PPL record mismatch')
        require(record['stride'] == 512 and record['corpus_tokens'] == tokenization['tokens']
                and record['scored_tokens'] == tokenization['tokens'] - 1, 'baseline N-1 coverage mismatch')
        for field in ('total_nll', 'mean_nll', 'ppl', 'wall_seconds', 'peak_allocated_bytes', 'peak_reserved_bytes'):
            finite_nonnegative(record[field], 'baseline ' + field)
        require(record['ppl'] > 0 and math.isclose(record['mean_nll'], record['total_nll']/record['scored_tokens'], rel_tol=1e-12)
                and math.isclose(record['ppl'], math.exp(record['mean_nll']), rel_tol=1e-12),
                'baseline NLL/PPL conservation failed')
        count, previous_end, nlls, number = 0, 1, [], 0
        with (directory/f"windows_{record['window']}.jsonl").open(encoding='utf-8') as handle:
            for number, line in enumerate(handle, 1):
                window = json.loads(line)
                begin = (number - 1)*512
                end = min(begin + record['window'], tokenization['tokens'])
                start = max(previous_end, begin + 1)
                require(window['number'] == number and window['begin'] == begin
                        and window['end'] == end and window['score_start'] == start
                        and window['count'] == end-start > 0
                        and window['logits_start'] == start-begin-1,
                        'baseline shifted-window protocol mismatch')
                count += window['count']
                require(window['scored_so_far'] == count, 'baseline cumulative token count mismatch')
                finite_nonnegative(window['nll'], 'window nll')
                nlls.append(window['nll'])
                previous_end = end
        require(previous_end == tokenization['tokens'] and count == record['scored_tokens']
                and number == record['windows']
                and math.isclose(math.fsum(nlls), record['total_nll'], rel_tol=1e-12),
                'baseline full window-log coverage/NLL mismatch')
    return dict(summary=summary, protocol=protocol, source=source,
                environment=read_json(directory/'environment.json'),
                scope='Original BF16 full WT2 sliding-window PPL only; never sampled-model quality or ASIC energy',
                artifacts=artifacts)


def compact(path, backend, identity=None, identity_sha256=None):
    d = read_json(path)
    require(d['case'] in CASES and d['context'] in CONTEXTS and backend in BACKENDS, 'unexpected scenario')
    n = d['config']['decode_tokens']
    require(n == 1, 'single-query decode contract; multi-token denominators require length summation')
    require(all(d['actual_shape'].get(k) == v for k, v in SHAPE.items()), 'not Llama 2 7B dimensions')
    workload = d['workload']
    require(workload.get('kind') == REAL_KIND and workload.get('real_model_trace') is True
            and workload.get('bf16_capture_bitwise_equal') is True, 'not verified real Llama 2 routing workload')
    valid_identity(workload['model_identity'])
    if identity is not None:
        require(workload['model_identity'] == identity, 'TLM differs from project model identity')
        require(workload.get('identity_manifest_sha256') == identity_sha256, 'TLM identity byte SHA mismatch')
    require(d.get('execution_source_commit') == TLM_COMMIT
            and re.fullmatch('[0-9a-f]{64}', d.get('execution_manifest_sha256', '')) is not None,
            'unfrozen/wrong TLM execution source')
    require(d['quality_reference_ppl'] is None and d['validation'].get('PPL_measured') is False,
            'TLM routing must not inherit baseline/model quality')
    require(d['bounds'].get('random_word_replay_bytes', 0) == 0, 'random stream SRAM is forbidden')
    require(d['config']['sc_engines'] == 8 and d['config']['samples'] == 4096, 'different SC hardware scenario')
    a, tr, e, tm = d['actions'], d['traffic'], d['energy_J'], d['time_ns']
    for group, values in [('actions', a), ('traffic', tr), ('energy', e), ('time', tm)]:
        for key, value in values.items():
            finite_nonnegative(value, group + '.' + key)
    for key in ('mean_TPOT_ms', 'scenario_mJ_per_token', 'parameterized_area_mm2', 'attention_ms_per_token'):
        finite_nonnegative(d['metrics'][key], key)
    require(math.isclose(sum(e.values())*1000/n, d['metrics']['scenario_mJ_per_token'], rel_tol=1e-10),
            'whole-system energy ledger does not close')
    require(math.isclose(sum(tm.values())/1e6/n, d['metrics']['mean_TPOT_ms'], rel_tol=1e-10),
            'whole-system serial time ledger does not close')
    full_k = 32 * 32 * d['context'] * 128 * 2 * n
    fused = tr.get('attention_KV_fused_physical_bytes', 0)
    k = tr.get('attention_K_physical_bytes', 0) + fused/2
    v = tr.get('attention_V_gather_physical_bytes', 0) + fused/2
    require(a['ATT_possible_QK_tokens'] == 32*32*d['context']*n, 'possible QK count mismatch')
    selected = a['ATT_selected_QK_tokens']/a['ATT_possible_QK_tokens']
    require(0 < selected <= 1 and math.isclose(k/full_k, selected, abs_tol=1e-12),
            'MHA physical K ratio must equal selected QK fraction')
    sampled = d['case'].endswith(('pv', 'ising'))
    samples = d['context']//16 if sampled else 0
    if sampled:
        expected = 32*32*samples*n
        require(a['ATT_V_sample_events'] == expected and a['ATT_V_additions'] == expected*128,
                'proportional PV sample/addition budget not conserved')
        require(a['ATT_V_group_union_rows'] == a['ATT_V_unique_head_indices']
                and 0 < a['ATT_V_unique_head_indices'] <= expected, 'MHA V union/unique count mismatch')
        require(v == a['ATT_V_unique_head_indices']*256 and v <= full_k,
                'V physical reads must equal unique vectors, not sample events/full KV')
    else:
        require(math.isclose(v/full_k, selected, abs_tol=1e-12), 'exact PV must read precisely candidate V')
    if 'screen' not in d['case']:
        require(selected == 1, 'unscreened scenario discarded QK')
    budgets = d['llama_attention']['budget_rows']
    require(len(budgets) == 32*n and all(x['samples_per_head'] == samples
            and x['context'] == d['context'] for x in budgets), 'per-layer sample budgets inconsistent')
    macro = d.get('ising_macro_v4')
    if 'ising' in d['case']:
        require(bool(macro) and macro['calls'] == 32*32*n and not macro['internal_rng_separately_charged'],
                'Ising calls/RNG must be accounted within the macro once')
    else:
        require(not macro, 'non-Ising scenario unexpectedly contains Ising macro')
    memory = d['memory_v5']['SRAM']
    capacity = sum(x['capacity_bytes'] for x in memory.values())
    require(capacity == 8*2**20 and 0 <= d['memory_v5']['work_peak_bytes'] <= capacity,
            'finite unified SRAM capacity/work peak violated')
    categories = defaultdict(float)
    for key, value in e.items():
        if key.startswith('external_'):
            category = 'DRAM'
        elif key.startswith('SRAM_'):
            category = 'SRAM'
        elif key.startswith(('SC_', 'weight_macro', 'weight_resident')):
            category = 'SC_core_and_residence'
        elif key.startswith(('RNG_', 'input_mask')):
            category = 'FFN_RNG_and_distribution'
        elif key.startswith('ATT_'):
            category = 'Attention_logic_and_sampler'
        else:
            category = 'Digital_projection_norm_control'
        categories[category] += value/n*1000
    external = d['external_memory_model']
    power = external.get('power_at_system_end', {})
    trace_path = Path(d['config']['attention_v3']['trace_file'])
    trace = trace_data(str(trace_path))
    require(trace['sha256'] == workload.get('trace_sha256') == d['attention_v3']['trace']['sha256'],
            'TLM trace original-byte SHA mismatch')
    require(trace['provenance']['context'] == d['context']
            and trace['provenance']['model_identity'] == workload['model_identity']
            and trace['provenance']['identity_manifest_sha256'] == workload.get('identity_manifest_sha256'),
            'trace and TLM workload identity mismatch')
    row = dict(backend=backend, case=d['case'], context=d['context'], seed=d['seed'],
        engines=d['config']['sc_engines'], samples_per_head=samples,
        ms_per_token=d['metrics']['mean_TPOT_ms'], mJ_per_token=d['metrics']['scenario_mJ_per_token'],
        area_mm2=d['metrics']['parameterized_area_mm2'], area_feasible=d['metrics']['area_budget_feasible'],
        attention_ms_per_token=d['metrics']['attention_ms_per_token'],
        FFN_ms_per_token=sum(tm.get(key, 0) for key in ('FFN_gate_up', 'FFN_SwiGLU', 'FFN_down'))/n/1e6,
        QK_fraction=selected, K_physical_fraction=k/full_k, V_physical_fraction=v/full_k,
        K_MiB_per_token=k/n/2**20, V_MiB_per_token=v/n/2**20,
        summary_MiB_per_token=sum(value for key, value in tr.items()
            if key.startswith('external_ATT_summary') and key.endswith('_burst_bytes'))/n/2**20,
        weight_GiB_per_token=tr.get('external_weights_read_burst_bytes', 0)/n/2**30,
        work_peak_MiB=d['memory_v5']['work_peak_bytes']/2**20, SRAM_MiB=capacity/2**20,
        SRAM_area_mm2=sum(x['area_mm2'] for x in memory.values()),
        DRAM_core_mJ_per_token=e.get('external_DRAMPower_core', 0)/n*1000 if power else None,
        DRAM_interface_proxy_mJ_per_token=e.get('external_DRAMPower_interface', 0)/n*1000 if power else None,
        energy_categories_mJ_per_token=dict(categories),
        time_categories_ms_per_token={key:value/n/1e6 for key, value in tm.items()},
        attention_phase_ms_per_token=d['llama_attention']['phase_ms_per_token'],
        energy_mJ_per_token={key:value/n*1000 for key, value in e.items()},
        traffic=tr, bounds=d['bounds'], rng=d.get('rng_hierarchy'), Ising=macro,
        source_commit=d['execution_source_commit'], configuration_sha256=d['configuration_sha256'],
        input_snapshot_sha256=d['execution_manifest_sha256'], workload=workload,
        trace=d['attention_v3']['trace'], wall_seconds=d['wall_seconds'],
        raw_artifact=artifact(path), source_hashes=d['source_hashes'])
    if 'screen' in d['case']:
        masses, seen = [], set()
        for selection in d['attention_v3']['rows']:
            key = selection['token'], selection['layer'], selection['head']
            require(key not in seen, 'duplicate router head')
            seen.add(key)
            p = trace['probabilities'][key]
            blocks = selection['selected_blocks']
            require(len(blocks) == len(set(blocks)) and all(0 <= block < math.ceil(len(p)/64) for block in blocks),
                    'invalid/duplicate selected blocks')
            masses.append(sum(p[i] for block in blocks for i in range(block*64, min(len(p), (block+1)*64))))
        require(len(seen) == 32*32*n, 'missing router head')
        row['offline_retained_attention_mass'] = dict(mean=statistics.mean(masses), minimum_head=min(masses),
            scope='Original BF16 routing oracle diagnostic only; not sampled-model PPL/quality')
    if backend.startswith('dramsys'):
        require(external.get('capacity_bytes') == 16*2**30 and bool(power), 'missing 16GiB closed-loop DRAM power')
        if 'final_simulation_time_ns' in external:
            require(external['final_simulation_time_ns'] >= sum(tm.values()), 'DRAM simulation ends before system')
        row['DRAM_configuration_sha256'] = external['configuration_sha256']
        row['DRAM_bursts'] = {key:external.get(key) for key in ('bursts', 'read_bursts', 'write_bursts', 'peak_pending')}
    return row


def summaries(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['backend'], row['context'], row['case'], row['engines']].append(row)
    result = []
    for key, values in sorted(groups.items()):
        row = dict(backend=key[0], context=key[1], case=key[2], engines=key[3], seeds=sorted(r['seed'] for r in values))
        for field in SCALARS[5:]:
            if field == 'area_feasible':
                row[field] = all(r[field] for r in values)
            elif all(isinstance(r[field], (float, int)) and not isinstance(r[field], bool) for r in values):
                row[field] = statistics.mean(r[field] for r in values)
                if field in ('ms_per_token', 'mJ_per_token', 'K_physical_fraction', 'V_physical_fraction'):
                    row[field+'_stdev'] = statistics.stdev(r[field] for r in values) if len(values) > 1 else 0.
            else:
                row[field] = None
        result.append(row)
    return result


def collect(args):
    require(not args.output.exists(), 'refusing to overwrite report directory')
    identity, identity_path = identity_at(args.project)
    baseline = baseline_evidence(args.project, identity, identity_path)
    rows = []
    for backend in BACKENDS:
        for path in sorted((args.project/'outputs'/backend).glob('*.json')):
            if '_dram' not in path.name:
                rows.append(compact(path, backend, identity, digest(identity_path)))
    check_keys(rows)
    require(len({r['input_snapshot_sha256'] for r in rows}) == 1, 'mixed execution snapshots')
    # Verify all source paths common to all cases, not just the entrypoint hash.
    require(all(r['source_hashes'] == rows[0]['source_hashes'] for r in rows), 'mixed engine source bytes')
    trace_paths = sorted((args.project/'outputs/traces').glob('c*.trace.json'))
    require({int(p.name.split('.')[0][1:]) for p in trace_paths} == set(CONTEXTS), 'missing/unexpected trace contexts')
    manifest = dict(project=str(args.project.resolve()), report_source_sha256=digest(Path(__file__)),
        model_identity=identity, model_identity_artifact=artifact(identity_path),
        code_commit=TLM_COMMIT, baseline_code_commit=BASELINE_COMMIT,
        results=len(rows), expected_full_results=len(expected_keys()), missing_cases=[],
        completeness_by_backend={backend:sum(r['backend'] == backend for r in rows) for backend in BACKENDS},
        scope='Full WT2 BF16 PPL independent from single real BF16 routing query/context TLM; no joint SC quality or measured ASIC energy',
        trace_artifacts=[artifact(path) for path in trace_paths],
        capture_artifacts=[artifact(path) for path in sorted((args.project/'outputs/traces').glob('*.json'))
                           if path not in trace_paths],
        result_artifacts=[r['raw_artifact'] for r in rows], baseline_artifacts=baseline['artifacts'])
    args.output.mkdir(parents=True)
    write_json(args.output/'cases.json', rows)
    with (args.output/'cases.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=SCALARS, lineterminator='\n')
        writer.writeheader()
        writer.writerows({key:row[key] for key in SCALARS} for row in rows)
    write_json(args.output/'summary.json', summaries(rows))
    write_json(args.output/'BF16_BASELINE.json', baseline)
    write_json(args.output/'ARTIFACT_INDEX.json', manifest)
    print(json.dumps(dict(count=len(rows), by_backend=manifest['completeness_by_backend'],
                         baseline_status=baseline['summary']['status'], output=str(args.output)), ensure_ascii=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    collect(parser.parse_args())
