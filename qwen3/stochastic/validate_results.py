"""Independent archived-byte and per-target NLL/coverage audit; partial-safe."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import struct
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(values):
    return hashlib.sha256(b''.join(struct.pack('<q', x) for x in values)).hexdigest()


def validate(root, require_complete=False):
    root = Path(root)
    server_sha = json.loads((root / 'SERVER_SHA256.json').read_bytes())
    for name, expected_sha in server_sha.items():
        path = root / name
        assert path.resolve().is_relative_to(root.resolve()) and sha(path) == expected_sha
    checked = []
    for sidecar in sorted(root.rglob('*.sha256.json')):
        entry = json.loads(sidecar.read_bytes())
        path = sidecar.with_name(entry['name'])
        assert path.is_relative_to(root) and sha(path) == entry['sha256'], str(path)
        checked.append(str(path.relative_to(root)))
    preflight = json.loads((root / 'preflight.json').read_bytes())
    assert preflight['status'] == 'PASS'
    source = preflight['source']
    assert source['commit'] == '8c35145e0073e48581640cd07c770631412a3f99'
    assert source['repository'] == 'https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines'
    assert len(source['files_sha256']) == 27
    assert preflight['config_sha256'] == source['files_sha256']['qwen3/stochastic/config.json']
    repository = Path(__file__).resolve().parents[2]
    for name, expected_sha in source['files_sha256'].items():
        raw = subprocess.check_output(['git', '-C', str(repository), 'show', source['commit'] + ':' + name])
        assert hashlib.sha256(raw).hexdigest() == expected_sha, name
    specifications = json.loads((repository / 'qwen3/baselines/config.json').read_bytes())
    assert [p['model'] for p in preflight['prepared']] == specifications['models']
    assert [p['manifest_sha256'] for p in preflight['prepared']] == [
        'e4f656e2358ec4579580d430c244e28b60b2c72041171aaafb6a1b1dacb7fab6',
        '30068099f8d08309938e1009a80548fb449a1d7a13edae8b12debc77f5626db8']
    assert {k: v['sha256'] for k, v in preflight['data'].items()} == specifications['data_sha256']
    reports = {}
    expected = {('bf16', 0)} | {(label, seed) for label in
        ['ffn', 'screen_exact_ffn', 'rejection128_ffn', 'winner1024_ffn'] for seed in range(3)}
    expected_token_sha = '8d41d21825bb0e103dc63337727daf4b51c631cacec5937f014b119ae209081e'
    for index, name in enumerate(['Qwen3-1.7B-Base', 'Qwen3-4B-Base']):
        directory = root / 'results' / name
        if require_complete:
            for required in ['gates.json', 'real_model_equivalence.json', 'calibration.json', 'complete.json']:
                assert str((directory / required).relative_to(root)).replace('\\', '/') in server_sha
                assert (directory / required).exists()
        rows, seen, targets_reference = [], set(), None
        if not directory.exists():
            reports[name] = dict(status='NOT_YET_AVAILABLE')
            continue
        gates = json.loads((directory / 'gates.json').read_bytes())
        assert gates['source'] == source and gates['native']['status'] == 'PASS'
        assert gates['native']['native_wrapper_bitwise'] and gates['kernels']['status'] == 'passed'
        assert gates['kernels']['cap_failure_passed']
        if (directory / 'real_model_equivalence.json').exists():
            equivalence = json.loads((directory / 'real_model_equivalence.json').read_bytes())
            assert equivalence['status'] == 'PASS' and equivalence['source'] == source
            assert equivalence['native']['scored_logits_sha256'] == equivalence['wrapper']['scored_logits_sha256']
        anchor_file = root / 'anchor/results' / (name + '.json')
        if anchor_file.exists():
            anchor = json.loads(anchor_file.read_bytes())
            assert anchor['unmodified_model'] and anchor['model'] == specifications['models'][index]
            assert anchor['token_ids_int64_le_sha256'] == expected_token_sha
            assert anchor['scored_tokens'] == 299077 and len(anchor['windows']) == 292
            assert anchor['nll_sum'] == [635340.0302581787, 583622.1282043457][index]
        if (directory / 'calibration.json').exists():
            calibration = json.loads((directory / 'calibration.json').read_bytes())
            assert calibration['test_used_for_fit'] is False
            assert calibration['data']['sha256'] == specifications['data_sha256']['wiki.train.raw']
            assert calibration['model'] == specifications['models'][index]
            assert len(calibration['parameter']) == specifications['models'][index]['num_hidden_layers']
            assert all(abs(x - .3) < 1e-6 for layer in calibration['per_layer'] for x in layer['fit_raw_fraction'])
        for path in sorted(directory.glob('*_s[012].json')):
            assert str(path.relative_to(root)) in checked, str(path)
            d = json.loads(path.read_bytes())
            case = d['args']
            key = case['label'], case['seed']
            assert key in expected and key not in seen
            seen.add(key)
            mode_spec = {'bf16': ('sdpa', 'none', 'none', 1),
                'ffn': ('sdpa', 'b4_t32', 'none', 1),
                'screen_exact_ffn': ('screen_exact', 'b4_t32', 'none', 1),
                'rejection128_ffn': ('screen_ising', 'b4_t32', 'rejection', 128),
                'winner1024_ffn': ('screen_ising', 'b4_t32', 'winner', 1024)}
            assert tuple(case[k] for k in ('mode', 'ffn', 'sampler', 'samples')) == mode_spec[key[0]]
            assert d['source'] == source and d['config_sha256'] == preflight['config_sha256']
            assert d['model'] == preflight['prepared'][index]['model']
            assert d['input_provenance']['prepared_sha256'] == preflight['prepared'][index]['manifest_sha256']
            assert d['input_provenance']['model'] == d['model']
            assert d['input_provenance']['data'] == preflight['data']
            assert d['input_provenance']['config_sha256'] == d['config_sha256']
            assert d['input_provenance']['calibration_sha256'] == d['calibration_sha256']
            assert d['token_ids_sha256_le_int64'] == expected_token_sha
            assert d['calibration_sha256'] == sha(directory / 'calibration.json')
            assert d['anchor_sha256'] == sha(root / 'anchor/results' / (name + '.json'))
            assert case['context'] == 2048 and case['decode'] == 128 and case['examples'] == 32
            assert case['batch'] == 2 and d['protocol'] == 'suffix'
            length = d['source_tokens']
            assert length == 299078
            assert case['selection'] == 'fixed' and case['budget_blocks'] == 8
            assert case['target_fraction'] == .3
            starts = [round((length - 2048 - 128) * i / 31) for i in range(32)]
            assert len(d['examples']) == 32
            targets = []
            for i, item in enumerate(d['examples']):
                begin = starts[i]
                expected_targets = list(range(begin + 2048, begin + 2048 + 128))
                assert item['segment_id'] == i and item['begin'] == begin
                assert item['first_target'] == expected_targets[0]
                assert item['last_target_exclusive'] == expected_targets[-1] + 1
                assert item['prefill_tokens'] == 2047 and item['scored_tokens'] == 128
                assert item['target_positions_sha256_le_int64'] == digest(expected_targets)
                assert math.isfinite(item['nll_sum']) and item['nll_sum'] >= 0
                targets.extend(expected_targets)
            assert len(targets) == len(set(targets)) == d['scored_tokens'] == 4096
            assert digest(targets) == d['scoring_plan']['target_positions_sha256_le_int64']
            if targets_reference is None:
                targets_reference = targets
            assert targets == targets_reference
            nll = math.fsum(x['nll_sum'] for x in d['examples'])
            assert nll == d['nll_sum'] and d['mean_nll'] == nll / 4096
            assert d['perplexity'] == math.exp(nll / 4096)
            layers = d['model']['num_hidden_layers']
            audit = d['execution_audit']
            assert d['attention_layers'] == d['ffn_layers'] == layers
            assert audit['scored_query_tokens'] == 4096
            assert audit['decode_calls_per_layer'] == [2048] * layers
            assert audit['prefill_calls_per_layer'] == [16] * layers
            assert audit['ffn_decode_tokens_per_layer'] == [4096] * layers
            assert audit['ffn_decode_calls_per_layer'] == [2048] * layers
            assert audit['ffn_prefill_calls_per_layer'] == [16] * layers
            assert audit['ffn_prefill_tokens_per_layer'] == [65504] * layers
            assert audit['every_scored_target_executed_all_layers']
            assert audit['every_scored_target_executed_all_ffns']
            if case['ffn'] != 'none':
                assert len(d['ffn_stats']) == layers
                for ffn in d['ffn_stats'].values():
                    assert (ffn['cycles'], ffn['strata'], ffn['sharing'], ffn['scale_bin_count']) == (32, 32, 64, 4)
                    assert not ffn['weight_stochastic'] and not ffn['finite_width_bittrue']
                    assert ffn['calls'] == 2064
            if case['mode'] != 'sdpa':
                stat = d['sampling_stats']
                assert stat['installed_layers'] == layers
                assert len(stat['layers']) == layers
                assert stat['actual_sampler'] == case['sampler']
                assert stat['samples'] == case['samples']
                assert stat['sampler_parameters'] == dict(winner_initialization='argmax',
                    winner_burn=0, winner_spacing=1, winner_shift=0, rejection_initial_shift=0,
                    rejection_max_shift=24, rejection_cap_factor=128, no_second_PV_draw=True)
                for v in stat['layers'].values():
                    assert v['query_rows'] == 4096 * d['model']['num_attention_heads']
                    assert v['decode_calls'] == 2048 and v['prefill_calls'] == 16
                    assert v['selected_blocks'] == v['query_rows'] * 8
                    if case['sampler'] != 'none':
                        assert v['sampler_calls'] == 2048
                        assert v['sample_events'] == v['query_rows'] * case['samples']
                if case['sampler'] in ('rejection', 'winner'):
                    assert case['samples'] == (128 if case['sampler'] == 'rejection' else 1024)
            rows.append(dict(label=key[0], seed=key[1], perplexity=d['perplexity'],
                seconds=d['wall_seconds'], sha256=sha(path)))
        bf16 = next((r['perplexity'] for r in rows if r['label'] == 'bf16'), None)
        grouped = {}
        for label in sorted({r['label'] for r in rows}):
            values = [r['perplexity'] for r in rows if r['label'] == label]
            grouped[label] = dict(n=len(values), mean=statistics.mean(values),
                sample_stddev=statistics.stdev(values) if len(values) > 1 else None,
                delta_to_cached_bf16=statistics.mean(values) - bf16 if bf16 else None,
                relative_percent=(statistics.mean(values) / bf16 - 1) * 100 if bf16 else None)
        if (directory / 'complete.json').exists():
            complete = json.loads((directory / 'complete.json').read_bytes())
            assert seen == expected and complete['cases'] == 13 and complete['source'] == source
            assert complete['config_sha256'] == preflight['config_sha256']
        if require_complete:
            assert seen == expected
        reports[name] = dict(status='COMPLETE' if seen == expected else 'PARTIAL',
            checked_cases=len(rows), cases=rows, summary=grouped,
            missing=[list(key) for key in sorted(expected - seen)])
    return dict(status='PASS_FOR_AVAILABLE_ARTIFACTS', raw_files_verified=len(checked),
        source=source, models=reports, protocol='4096-target suffix, not full WT2',
        full_candidate_ppl_available=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root')
    parser.add_argument('--output')
    parser.add_argument('--git-blobs', action='store_true')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    result = validate(args.root, require_complete=args.require_complete)
    if args.git_blobs:
        repository = Path(__file__).resolve().parents[2]
        raw_root = Path(args.root).resolve()
        manifest = json.loads((raw_root / 'SERVER_SHA256.json').read_bytes())
        for name, expected_sha in manifest.items():
            relative = (raw_root / name).relative_to(repository).as_posix()
            raw = subprocess.check_output(['git', '-C', str(repository), 'show', 'HEAD:' + relative])
            assert hashlib.sha256(raw).hexdigest() == expected_sha, relative
        result['committed_server_files_verified'] = len(manifest)
    raw = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        with Path(args.output).open('w', encoding='utf-8', newline='\n') as stream:
            stream.write(raw)
    print(raw)
