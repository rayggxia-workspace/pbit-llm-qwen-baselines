"""Standard-library audit/summary of Issue150 sealed JSON, without inference.

Usage: python collect_static.py --input RESULT_ROOT --output SUMMARY_ROOT
Add --allow-partial to permit missing artifacts (invalid evidence still fails).
This verifies checksums/record consistency, not cryptographic authorship and
not the remote model/data bytes absent from the collection. No Torch import.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import struct


MODEL_REVISION = '060db6499f32faf8b98477b0a26969ef7d8b9987'
TEST_SHA = '8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e'
FIT_SHA = '52765211c4e14b32bb7fe44f5790c77370764454de7dc6c735f759538e5cd472'
SPLITS = {'fit': [0, 8192], 'selection': [16384, 24576], 'holdout': [32768, 40960]}
CANDIDATES = [{'name': 'd%d_h%d' % (d, h), 'gap': d, 'headroom': h}
              for d in (1, 2, 3) for h in (0, 1)]
TEST_PROTOCOL = 'full_WT2_test_sliding_window_2048_1024'
LAYERS = [str(i) for i in range(24)]
WIDTHS = {'x': 896, 'z': 4864}


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def check(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def is_sha(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{%d}' % length, value) is not None


def close(actual, expected, message):
    check(finite(actual) and finite(expected) and
          math.isclose(actual, expected, rel_tol=2e-10, abs_tol=1e-10), message)


def cfg(name, scope='both', mode='sampled', cycles=32, seed=0):
    return dict(name=name, scope=scope, mode=mode, cycles=cycles, strata=cycles, seed=seed,
                bins=4, group=64, probability_bits=8, weight='fixed historical W8/64x64')


def cases():
    rows = [cfg('w8_only', mode='w8_only'), cfg('fixed_mean', mode='mean')]
    for scope, cycles in (('dynamic', 32), ('both', 32), ('x', 32), ('z', 32),
                          ('dynamic', 64), ('both', 64)):
        rows.extend(cfg('%s_T%d_s%d' % (scope, cycles, seed), scope=scope,
                        cycles=cycles, seed=seed) for seed in (0, 1, 2))
    return rows


def score_shape(length):
    sizes = []
    for begin in range(0, length, 1024):
        sizes.append(min(2048, length - begin))
        if begin + sizes[-1] == length:
            break
    return len(sizes), sum(sizes)


def validate_score(row, length):
    windows, forwarded = score_shape(length)
    check(row['input_tokens'] == length and row['scored_tokens'] == length - 1,
          'Input/target token coverage mismatch')
    check(row['windows'] == windows, 'Window coverage mismatch')
    check(finite(row['nll']) and row['nll'] >= 0, 'Invalid NLL')
    close(row['nll_sum'] / (length - 1), row['nll'], 'NLL sum/mean mismatch')
    check(finite(row['forward_seconds']) and row['forward_seconds'] >= 0, 'Invalid runtime')
    if row['nll'] > math.log(float.fromhex('0x1.fffffffffffffp+1023')):
        check(row['perplexity'] is None and
              row['perplexity_status'] == 'FP64_exp_overflow_NLL_retained',
              'PPL overflow must retain NLL explicitly')
    else:
        close(row['perplexity'], math.exp(row['nll']), 'PPL != exp(NLL)')
        check(row['perplexity_status'] == 'finite', 'Wrong finite PPL status')
    return windows, forwarded


def validate_tables(tables, gap=None):
    check(set(tables) == set(LAYERS), 'Scale tables must contain all 24 layers')
    for layer in LAYERS:
        check(set(tables[layer]) == {'x', 'z'}, 'x/z tables required')
        for signal, width in WIDTHS.items():
            rows = tables[layer][signal]
            check(len(rows) == width // 64, 'Wrong group count: ' + layer + '/' + signal)
            for row in rows:
                check(len(row) == 4, 'Exactly four scales required')
                exponents = []
                for value in row:
                    check(finite(value) and value > 0 and math.frexp(value)[0] == .5,
                          'Scale is not a finite positive power of two')
                    exponent = math.frexp(value)[1] - 1
                    check(-149 <= exponent <= 127, 'Scale not representable in FP32')
                    exponents.append(exponent)
                check(all(exponents[i] > exponents[i+1] for i in range(3)),
                      'Scale table not strictly descending')
                if gap is not None:
                    check(all(exponents[i]-exponents[i+1] == gap for i in range(3)),
                          'Scale exponent gap mismatch')


def table_sha(rows):
    values = [value for row in rows for value in row]
    return hashlib.sha256(struct.pack('<%df' % len(values), *values)).hexdigest()


def validate_coverage(row, configuration, tables):
    windows, forwarded = score_shape(row['input_tokens'])
    check(row['all_token_ffn_coverage_verified'] is True, 'Missing FFN coverage assertion')
    check(row['ffn_layers'] == list(range(24)), 'Missing FFN layers')
    check(row['ffn_calls_per_layer'] == windows and row['forwarded_tokens'] == forwarded,
          'Recorded FFN forwarding counts mismatch')
    diagnostics = row['diagnostics']
    check(set(diagnostics) == set(LAYERS), 'Diagnostics must cover 24 unique FFN layers')
    expected_static = {
        'x': configuration['scope'] in ('both', 'x'),
        'z': configuration['scope'] in ('both', 'z')}
    for layer in LAYERS:
        d = diagnostics[layer]
        check(d['layer'] == int(layer) and d['calls'] == windows, 'Layer/call mismatch')
        check(d['mode'] == configuration['mode'] and d['cycles'] == configuration['cycles']
              and d['strata'] == configuration['strata'], 'Diagnostic configuration mismatch')
        check(d['sharing'] == 64 and d['probability_bits'] == 8 and d['scale_bin_count'] == 4,
              'Wrong encoding/sharing diagnostic')
        check(d['weight_stochastic'] is False and d['weight_probability_reencoded'] is False
              and d['finite_width_bittrue'] is False, 'Wrong numerical model boundary')
        expected_dynamic = [] if configuration['mode'] == 'w8_only' else [
            name for name in ('x', 'z') if not expected_static[name]]
        check(d['online_absmax_signals'] == expected_dynamic, 'Wrong dynamic/fixed scope')
        check(d['diagnostic_reductions_drive_scales'] is False, 'Diagnostics drive deployed scales')
        for signal, width in WIDTHS.items():
            check(d[signal + '_values'] == forwarded * width, 'Wrong all-token signal coverage')
            expected_sha = table_sha(tables[layer][signal]) if expected_static[signal] else None
            check(d[signal + '_scales_sha256'] == expected_sha and
                  d['scales_sha256'][signal] == expected_sha and
                  d['scale_tables'][signal]['sha256'] == expected_sha,
                  'Per-layer scale checksum mismatch')
            for suffix in ('encoding_nmse', 'clip_fraction', 'clip_sse', 'clip_sse_over_power',
                           'clipped_value_power', 'clipped_value_power_over_power',
                           'max_overflow_ratio', 'max_overflow_excess'):
                value = d[signal + '_' + suffix]
                check(finite(value) and value >= 0, 'Nonfinite/negative diagnostic ' + suffix)
            check(d[signal + '_clip_fraction'] <= 1 and
                  d[signal + '_clipped_value_power_over_power'] <= 1.0000001,
                  'Clipping fraction exceeds one')


class Collector:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.documents = {}
        self.evidence = []
        self.missing = []
        self.invalid = []

    def read(self, rel, validator=None, sealed=True):
        path = self.root / rel
        marker_path = path.with_suffix('.sha256.json')
        if not path.is_file() or (sealed and not marker_path.is_file()):
            self.missing.append({'file': rel, 'missing': 'payload' if not path.is_file() else 'sha256_sidecar'})
            return None
        try:
            checksum = digest(path)
            if sealed:
                marker = json.loads(marker_path.read_text(encoding='utf-8'))
                check(marker['file'] == path.name and marker['sha256'] == checksum,
                      'Sidecar filename/hash mismatch')
            value = json.loads(path.read_text(encoding='utf-8'),
                               parse_constant=lambda s: (_ for _ in ()).throw(ValueError('Nonfinite JSON: '+s)))
            if validator is not None:
                validator(value)
            self.documents[rel] = value
            self.evidence.append({'file': rel, 'sha256': checksum, 'bytes': path.stat().st_size,
                                  'sidecar_sha256': digest(marker_path) if sealed else None})
            return value
        except (ValueError, KeyError, TypeError, IndexError, OverflowError, OSError) as error:
            self.invalid.append({'file': rel, 'error': str(error)})
            return None

    def sha(self, rel):
        check(rel in self.documents, 'Missing/invalid prerequisite: ' + rel)
        return digest(self.root / rel)

    def require(self, rel):
        check(rel in self.documents, 'Missing/invalid prerequisite: ' + rel)
        return self.documents[rel]

    def common(self, row):
        identity = self.require('identity.json')
        check(row['status'] == 'completed', 'Result is not completed')
        check(row['code_commit'] == identity['execution_commit'], 'Execution commit mismatch')

    def identity(self, row):
        check(row['status'] == 'verified' and row['model_revision'] == MODEL_REVISION,
              'Wrong model identity/status')
        check(is_sha(row['execution_commit'], 40), 'Malformed execution SHA')
        check(row['model_repository'] == 'Qwen/Qwen2.5-0.5B', 'Wrong model repository')
        check(row['tokens']['test']['tokens'] == 299078 and
              row['tokens']['test']['ids_sha256'] == TEST_SHA, 'Wrong TEST token identity')
        check(row['tokens']['train']['first8192_ids_sha256'] == FIT_SHA and
              is_sha(row['tokens']['train']['ids_sha256']), 'Wrong TRAIN token identity')
        check(row['splits'] == SPLITS, 'Frozen split mismatch')
        check(bool(row['files']) and bool(row['executed_source']), 'Empty model/data/source manifest')
        check(all(is_sha(v) for v in row['executed_source'].values()), 'Invalid source SHA')
        for entry in row['files'].values():
            check(is_sha(entry['sha256']) and isinstance(entry['bytes'], int) and entry['bytes'] >= 0,
                  'Invalid input artifact identity')

    def cpu_ready(self, row):
        self.common(row)
        check(row['identity_sha256'] == self.sha('identity.json'), 'CPU identity binding mismatch')
        check(row['source'] == self.require('identity.json')['executed_source'], 'Source binding mismatch')

    def calibration(self, row):
        self.common(row)
        self.require('CPU_READY.json')
        check(row['identity_sha256'] == self.sha('identity.json'), 'Calibration identity mismatch')
        check(row['candidate_definitions'] == CANDIDATES, 'Candidate definitions changed')
        check(row['selection_rule'] == 'minimum mean TRAIN-selection NLL over seeds101,102; tie by candidate name',
              'Selection rule changed')
        check(row['capture_paths'] == ['W8-only', 'dynamic_B4_T32_K32_seed917'], 'Capture path mismatch')
        check(row['online_max'] is False and row['test_used_for_calibration_or_selection'] is False,
              'Calibration protocol changed')
        check(set(row['splits']) == set(SPLITS), 'Calibration split keys changed')
        for key, span in SPLITS.items():
            check(row['splits'][key]['range'] == span and is_sha(row['splits'][key]['token_sha256']),
                  'Calibration split/hash mismatch')
        check(row['splits']['fit']['token_sha256'] == FIT_SHA, 'Fit tokens do not match identity')
        check(set(row['tables']) == {c['name'] for c in CANDIDATES}, 'Missing/extra candidate tables')
        maxima = row['observed_maxima']
        check(set(maxima) == {layer + ':' + signal for layer in LAYERS for signal in WIDTHS},
              'Observed maximum coverage mismatch')
        for candidate in CANDIDATES:
            tables = row['tables'][candidate['name']]
            validate_tables(tables, candidate['gap'])
            for layer in LAYERS:
                for signal, width in WIDTHS.items():
                    values = maxima[layer + ':' + signal]
                    check(len(values) == width // 64, 'Observed maximum group count mismatch')
                    for maximum, scales in zip(values, tables[layer][signal]):
                        check(finite(maximum) and maximum >= 0, 'Invalid observed maximum')
                        m, e = math.frexp(maximum)
                        top = (0 if maximum == 0 else e - int(m == .5)) + candidate['headroom']
                        check(scales == [math.ldexp(1., top-candidate['gap']*i) for i in range(4)],
                              'Scale table does not follow frozen maximum/gap/headroom rule')

    def baseline(self, row):
        self.common(row)
        self.require('CPU_READY.json')
        check(row['identity_sha256'] == self.sha('identity.json'), 'Baseline identity mismatch')
        check(row['configuration'] == {'name': 'bf16_full', 'mode': 'baseline'} and
              row['baseline_gate_passed'] is True and row['ffn_layers'] == [], 'Baseline gate/config mismatch')
        check(row['token_ids_sha256'] == TEST_SHA and row['protocol'] == TEST_PROTOCOL,
              'Baseline score protocol mismatch')
        validate_score(row, 299078)
        check(abs(row['perplexity'] - 11.652735047455899) < .02, 'Baseline drift gate failed')

    def selection(self, row, candidate, seed):
        self.common(row)
        cal = self.require('CALIBRATION.json')
        expected = cfg(candidate + '_select_s' + str(seed), seed=seed)
        check(row['configuration'] == expected and row['candidate'] == candidate,
              'Selection configuration mismatch')
        check(row['calibration_sha256'] == self.sha('CALIBRATION.json') and
              row['token_ids_sha256'] == cal['splits']['selection']['token_sha256'] and
              row['protocol'] == 'WT2_TRAIN_selection_8192_tokens', 'Selection input binding mismatch')
        validate_score(row, 8192)
        validate_coverage(row, expected, cal['tables'][candidate])

    def selected(self, row):
        self.common(row)
        cal = self.require('CALIBRATION.json')
        check(row['calibration_sha256'] == self.sha('CALIBRATION.json'), 'SELECTED calibration mismatch')
        check(row['name'] in cal['tables'] and row['tables'] == cal['tables'][row['name']] and
              row['tables_sha256'] == canonical_sha(row['tables']), 'Selected table/hash mismatch')
        check(row['selection_seeds'] == [101, 102] and row['fit_seed'] == 917 and
              row['online_max'] is False and row['test_used_for_selection'] is False,
              'Selected protocol mismatch')
        actual = []
        for candidate in CANDIDATES:
            for seed in (101, 102):
                name = candidate['name']
                result = self.require('selection/%s_select_s%d.json' % (name, seed))
                actual.append({'candidate': name, 'seed': seed, 'nll': result['nll'],
                               'perplexity': result['perplexity']})
        check(row['selection_rows'] == actual, 'Selection evidence rows mismatch')
        ranked = sorted([sum(r['nll'] for r in actual if r['candidate'] == c['name']) / 2., c['name']]
                        for c in CANDIDATES)
        check(row['ranking'] == ranked and row['name'] == ranked[0][1], 'Wrong frozen selection winner')

    def holdout(self, row, scope, seed):
        self.common(row)
        cal, selected = self.require('CALIBRATION.json'), self.require('SELECTED.json')
        expected = cfg('holdout_%s_s%d' % (scope, seed), scope=scope, seed=seed)
        check(row['configuration'] == expected and row['selected_sha256'] == self.sha('SELECTED.json'),
              'Holdout selection/config binding mismatch')
        check(row['token_ids_sha256'] == cal['splits']['holdout']['token_sha256'] and
              row['protocol'] == 'WT2_TRAIN_holdout_8192_tokens', 'Holdout input mismatch')
        validate_score(row, 8192)
        validate_coverage(row, expected, selected['tables'])

    def ready(self, row):
        self.common(row)
        for field, rel in (('identity_sha256', 'identity.json'), ('selected_sha256', 'SELECTED.json'),
                           ('calibration_sha256', 'CALIBRATION.json'), ('bf16_full_sha256', 'runs/bf16_full.json')):
            check(row[field] == self.sha(rel), 'READY binding mismatch: ' + rel)
        check(row['cases'] == cases() and row['cases_sha256'] == canonical_sha(cases()),
              'READY configuration set changed')
        for scope in ('dynamic', 'both'):
            for seed in (201, 202):
                self.require('holdout/holdout_%s_s%d.json' % (scope, seed))

    def full_result(self, row, expected):
        self.common(row)
        self.require('READY.json')
        selected = self.require('SELECTED.json')
        check(row['configuration'] == expected and row['configuration_sha256'] == canonical_sha(expected),
              'Full result configuration/SHA mismatch')
        for field, rel in (('identity_sha256', 'identity.json'), ('selected_sha256', 'SELECTED.json'),
                           ('calibration_sha256', 'CALIBRATION.json')):
            check(row[field] == self.sha(rel), 'Full result binding mismatch: ' + rel)
        check(row['fixed_ladder'] == selected['name'] and
              row['scale_tables_sha256'] == selected['tables_sha256'], 'Full result selected table mismatch')
        check(row['model_revision'] == MODEL_REVISION and row['token_ids_sha256'] == TEST_SHA and
              row['context'] == 2048 and row['stride'] == 1024 and row['protocol'] == TEST_PROTOCOL,
              'Full result scoring/model/token identity mismatch')
        check(row['attention'] == 'unchanged original BF16 SDPA; no screening, Ising or PV sampling',
              'Attention changed')
        check(row['physical_rng_replay'] is False and row['finite_width_bittrue'] is False and
              row['trained'] is False, 'Numerical scope mismatch')
        validate_score(row, 299078)
        validate_coverage(row, expected, selected['tables'])

    def collect(self):
        self.read('identity.json', self.identity, sealed=False)
        self.read('CPU_READY.json', self.cpu_ready)
        self.read('runs/bf16_full.json', self.baseline)
        self.read('CALIBRATION.json', self.calibration)
        for c in CANDIDATES:
            for seed in (101, 102):
                name = c['name']
                self.read('selection/%s_select_s%d.json' % (name, seed),
                          lambda row, n=name, s=seed: self.selection(row, n, s))
        self.read('SELECTED.json', self.selected)
        for scope in ('dynamic', 'both'):
            for seed in (201, 202):
                self.read('holdout/holdout_%s_s%d.json' % (scope, seed),
                          lambda row, p=scope, s=seed: self.holdout(row, p, s))
        self.read('READY.json', self.ready)
        for expected in cases():
            self.read('runs/' + expected['name'] + '.json',
                      lambda row, c=expected: self.full_result(row, c))
        expected_files = {'bf16_full.json'} | {c['name'] + '.json' for c in cases()}
        extra = sorted(p.name for p in (self.root / 'runs').glob('*.json')
                       if not p.name.endswith('.sha256.json') and p.name not in expected_files)
        for name in extra:
            self.invalid.append({'file': 'runs/' + name, 'error': 'Unexpected test result; not in frozen 21 cases'})
        return build_summary(self)


def diagnostic_summary(rows):
    output = {}
    for signal in WIDTHS:
        for suffix in ('encoding_nmse', 'clip_fraction', 'clip_sse_over_power',
                       'clipped_value_power_over_power', 'max_overflow_ratio'):
            values = [d[signal + '_' + suffix] for row in rows
                      for d in row.get('diagnostics', {}).values()]
            output[signal + '_' + suffix] = {'layer_seed_mean': statistics.mean(values),
                                             'worst_layer_seed': max(values)} if values else None
    return output


def build_summary(collector):
    docs = collector.documents
    baseline = docs.get('runs/bf16_full.json')
    groups = []
    configurations = cases()
    keys = [('w8_only', 'both', 32), ('mean', 'both', 32)] + [
        ('sampled', scope, t) for scope, t in
        (('dynamic', 32), ('both', 32), ('x', 32), ('z', 32), ('dynamic', 64), ('both', 64))]
    for mode, scope, cycles in keys:
        expected = [c for c in configurations if (c['mode'], c['scope'], c['cycles']) == (mode, scope, cycles)]
        rows = [docs['runs/' + c['name'] + '.json'] for c in expected if 'runs/' + c['name'] + '.json' in docs]
        finite_rows = [r for r in rows if r['perplexity'] is not None]
        mean = statistics.mean(r['perplexity'] for r in finite_rows) if len(finite_rows) == len(rows) and rows else None
        groups.append({'mode': mode, 'scope': scope, 'cycles': cycles, 'strata': cycles,
                       'expected': len(expected), 'completed': len(rows),
                       'seeds': [r['configuration']['seed'] for r in rows],
                       'complete': len(rows) == len(expected), 'perplexity_mean': mean,
                       'perplexity_sample_sd': statistics.stdev(r['perplexity'] for r in finite_rows)
                       if len(finite_rows) == len(rows) and len(rows) > 1 else None,
                       'mean_nll': statistics.mean(r['nll'] for r in rows) if rows else None,
                       'relative_ppl_percent': (mean / baseline['perplexity'] - 1.) * 100.
                       if mean is not None and baseline else None,
                       'rows': [{'name': r['configuration']['name'], 'seed': r['configuration']['seed'],
                                 'ppl': r['perplexity'], 'nll': r['nll'], 'seconds': r['forward_seconds']}
                                for r in rows], 'diagnostics': diagnostic_summary(rows)})
    selection = []
    for c in CANDIDATES:
        rows = [docs['selection/%s_select_s%d.json' % (c['name'], s)] for s in (101, 102)
                if 'selection/%s_select_s%d.json' % (c['name'], s) in docs]
        selection.append(dict(c, completed=len(rows), expected=2,
                              mean_nll=statistics.mean(r['nll'] for r in rows) if rows else None,
                              mean_ppl=statistics.mean(r['perplexity'] for r in rows)
                              if rows and all(r['perplexity'] is not None for r in rows) else None))
    selected = docs.get('SELECTED.json')
    ladders = None
    if selected:
        ladders = {'name': selected['name'], 'definition': next(c for c in CANDIDATES if c['name'] == selected['name']),
                   'tables_sha256': selected['tables_sha256'], 'signals': {}}
        for signal in WIDTHS:
            hist = Counter(math.frexp(row[0])[1] - 1 for layer in LAYERS for row in selected['tables'][layer][signal])
            ladders['signals'][signal] = {'groups': sum(hist.values()), 'highest_exponent_histogram': dict(sorted(hist.items())),
                                         'per_layer_highest_exponents': {layer: [math.frexp(r[0])[1] - 1
                                          for r in selected['tables'][layer][signal]] for layer in LAYERS}}
    valid = sorted(name for name in docs if name.startswith('runs/'))
    test_missing = [v for v in collector.missing if v['file'].startswith('runs/')]
    test_invalid = [v for v in collector.invalid if v['file'].startswith('runs/')]
    complete = len(valid) == 21 and not collector.invalid and not collector.missing
    return {'status': 'complete' if complete else 'invalid' if collector.invalid else 'partial',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'input_root': str(collector.root),
            'code_commit': docs.get('identity.json', {}).get('execution_commit'),
            'model_revision': MODEL_REVISION, 'test_token_sha256': TEST_SHA,
            'full_test': {'expected': 21, 'completed': len(valid), 'missing': test_missing,
                          'invalid': test_invalid, 'completed_files': valid},
            'missing': collector.missing, 'invalid': collector.invalid,
            'baseline': {k: baseline[k] for k in ('perplexity', 'nll', 'scored_tokens', 'windows', 'forward_seconds')}
                        if baseline else None,
            'selection': selection, 'selected_ladder': ladders, 'groups': groups,
            'holdout': [{'name': name, 'nll': row['nll'], 'ppl': row['perplexity']}
                        for name, row in docs.items() if name.startswith('holdout/')],
            'verified_evidence': collector.evidence,
            'boundaries': ['All test groups use complete WT2 sliding-window targets, context2048/stride1024.',
                           'Original BF16 SDPA attention; all24 FFNs replaced on all forwarded tokens.',
                           'K=T randomized stratification/shared64 is not physical IID replay.',
                           'FP32 arithmetic reference, no finite-width RTL/PPA/ASIC timing claim.',
                           'Diagnostic ratios are layer/seed means or maxima, not global power-weighted ratios.',
                           'Diagnostic reductions never drive inference scale tables; their GPU cost is not deployment PPA.',
                           'Sidecars establish byte integrity and binding, not digital signatures or independent model-file rereads.',
                           'PPL seed SD is sample SD, not a test-corpus confidence interval.']}


def fmt(value, digits=6):
    return '—' if value is None else ('%.*f' % (digits, value))


def render_zh(summary):
    full = summary['full_test']
    lines = ['# 固定四档尺度 FFN 评测汇总', '',
             '状态：**%s**。完整TEST已核验 **%d/21**；缺失%d项，结果无效%d项。'
             % (summary['status'], full['completed'], len(full['missing']), len(full['invalid'])),
             '执行版本：`%s`。本文件仅使用通过校验的封存JSON；部分seed不冒充三seed完整结果。'
             % summary['code_commit'], '',
             '比较保持Qwen2.5-0.5B原始Attention，24层FFN全部替换。完整WT2为299077个计分目标；2048上下文、1024步长。', '',
             '## TRAIN选择与实际档位', '',
             'fit/selection/holdout来自互不重叠TRAIN范围；先按selection两个seed的平均NLL选定，再冻结holdout和TEST。', '',
             '| 候选 | 档间指数差d | 顶档余量h | 完成seed | selection平均NLL | selection平均PPL |',
             '|---|---:|---:|---:|---:|---:|']
    for row in summary['selection']:
        lines.append('| %s | %d | %d | %d/2 | %s | %s |' % (row['name'], row['gap'], row['headroom'],
                     row['completed'], fmt(row['mean_nll']), fmt(row['mean_ppl'])))
    selected = summary['selected_ladder']
    if selected:
        d = selected['definition']['gap']
        lines += ['', '已冻结：**%s**；每组四档为 `2^e, 2^(e−%d), 2^(e−%d), 2^(e−%d)`。'
                  % (selected['name'], d, 2*d, 3*d),
                  '顶档e允许因层、x/z与64通道组不同，但推理期间不更新。以下为实际最高指数分布：', '',
                  '| 信号 | 组数 | 最高指数e：组数 |', '|---|---:|---|']
        for signal, info in selected['signals'].items():
            hist = '；'.join('%s：%s' % item for item in info['highest_exponent_histogram'].items())
            lines.append('| %s | %d | %s |' % (signal, info['groups'], hist))
    else:
        lines += ['', '尚无通过完整选优链校验的固定档位，不声明最佳候选。']
    lines += ['', '## 完整WT2 PPL', '',
              '原BF16 PPL：**%s**。下表变化均相对本轮BF16；标准差是seed间样本标准差。'
              % fmt(summary['baseline']['perplexity'] if summary['baseline'] else None), '',
              '| 配置 | 采样T/K | 完成 | PPL均值 | 样本SD | 相对BF16 |',
              '|---|---:|---:|---:|---:|---:|']
    names = {'dynamic': 'x/z均动态', 'both': 'x/z均固定', 'x': '固定x＋动态z', 'z': '动态x＋固定z'}
    for row in summary['groups']:
        name = 'W8无激活编码' if row['mode'] == 'w8_only' else '固定编码无采样控制' if row['mode'] == 'mean' else names[row['scope']]
        tk = '不采样' if row['mode'] != 'sampled' else '%d/%d' % (row['cycles'], row['strata'])
        label = '%d/%d%s' % (row['completed'], row['expected'], '' if row['complete'] else '（部分）')
        lines.append('| %s | %s | %s | %s | %s | %s%% |' % (name, tk, label, fmt(row['perplexity_mean']),
                     fmt(row['perplexity_sample_sd']), fmt(row['relative_ppl_percent'], 3)))
    lines += ['', '无采样控制不等于整个非线性FFN的数学期望；W8-only与固定编码控制单独列出，不算三seed采样结果。', '',
              '## 截断与编码误差', '',
              '下表为各已完成seed、24层的最坏局部比率。它不是整网能耗，不把软件统计归约计入部署硬件。逐层均值、逐seedPPL见SUMMARY.json。', '',
              '| 配置 | 信号 | 编码NMSE最坏层 | 截断SSE/原能量最坏层 | 被截值能量占比最坏层 | 最大超范围倍率 |',
              '|---|---|---:|---:|---:|---:|']
    for row in summary['groups']:
        if not row['completed'] or row['mode'] == 'w8_only':
            continue
        label = '%s/%s/T%d（%d/%d）' % (row['mode'], row['scope'], row['cycles'], row['completed'], row['expected'])
        for signal in WIDTHS:
            values = [row['diagnostics'][signal + '_' + suffix]['worst_layer_seed']
                      for suffix in ('encoding_nmse', 'clip_sse_over_power', 'clipped_value_power_over_power', 'max_overflow_ratio')]
            lines.append('| %s | %s | %s | %s | %s | %s |' % (label, signal, *[fmt(v) for v in values]))
    lines += ['', '最大超范围倍率无溢出时记0；有溢出时为 |输入|/最高档。少量截断不必然意味着损失小。', '',
              '## 核验与缺项', '',
              '仅对通过核验的记录检查原字节sidecar、identity/CPU_READY/CALIBRATION/SELECTED/READY绑定、实际选优排名、配置与尺度SHA、24层forward覆盖和NLL/PPL重算；未齐项不算完成。',
              '权重/数据/执行源码采用封存manifest绑定，汇总器不重新读取远端大文件；SHA sidecar不是身份认证签名。',
              '固定W8、FP32 SiLU及恢复；共享64、K=T分层采样，不是物理IID；没有新RTL、PPA或ASIC周期结论。', '']
    for key, title in (('missing', '缺失证据'), ('invalid', '无效证据')):
        lines.append('**%s：%d项**' % (title, len(summary[key])))
        lines.append('')
        lines.extend('- `%s`：%s' % (row['file'], row.get('error', row.get('missing'))) for row in summary[key])
        if not summary[key]:
            lines.append('无。')
        lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    root, target = Path(args.input).resolve(strict=True), Path(args.output).resolve()
    check(target != root and root not in target.parents, 'Summary must be outside immutable result input tree')
    result = Collector(root).collect()
    target.mkdir(parents=True, exist_ok=True)
    write_json(target / 'SUMMARY.json', result)
    with (target / 'SUMMARY_ZH.md').open('w', encoding='utf-8', newline='\n') as stream:
        stream.write(render_zh(result))
    print(json.dumps({'status': result['status'], 'full_completed': result['full_test']['completed'],
                      'full_expected': 21, 'missing': len(result['missing']), 'invalid': len(result['invalid'])}))
    if result['invalid'] or (result['status'] != 'complete' and not args.allow_partial):
        raise SystemExit(2)


if __name__ == '__main__':
    main()
