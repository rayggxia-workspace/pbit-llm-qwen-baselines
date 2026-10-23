"""Tamper tests against actual tiny archived metadata, never model execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from .validate_results import validate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('archive')
    p.add_argument('--complete', action='store_true')
    p.add_argument('--output')
    args = p.parse_args()
    source = Path(args.archive).resolve()
    validate(source, require_complete=args.complete)
    changes = {
        'ppl': lambda d: d.update(perplexity=d['perplexity'] + 1),
        'target': lambda d: d['examples'][0].update(first_target=0),
        'coverage': lambda d: d['execution_audit']['decode_calls_per_layer'].__setitem__(0, 0),
        'token_hash': lambda d: d.update(token_ids_sha256_le_int64='0' * 64),
        'revision': lambda d: d['model'].update(revision='0' * 40),
        'config': lambda d: d.update(config_sha256='0' * 64),
        'protocol': lambda d: d.update(protocol='full'),
        'calibration': lambda d: d.update(calibration_sha256='0' * 64),
        'source_commit': lambda d: d['source'].update(commit='0' * 40),
        'source_file': lambda d: d['source']['files_sha256'].update({'qwen3/stochastic/adapter.py': '0' * 64}),
        'prepared_binding': lambda d: d['input_provenance'].update(prepared_sha256='0' * 64),
        'data_binding': lambda d: d['input_provenance']['data']['wiki.test.raw'].update(sha256='0' * 64),
        'prefill_coverage': lambda d: d['execution_audit']['ffn_prefill_tokens_per_layer'].__setitem__(0, 0),
    }
    if args.complete:
        changes.update({
            'sampler_burn': lambda d: d['sampling_stats']['sampler_parameters'].update(winner_burn=16),
            'sampler_events': lambda d: d['sampling_stats']['layers']['0'].update(sample_events=0),
            'selection_budget': lambda d: d['args'].update(budget_blocks=16),
        })
    for label, change in changes.items():
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / 'work/jieruiz/144') as tmp:
            target = Path(tmp) / 'archive'
            shutil.copytree(source, target)
            filename = 'winner1024_ffn_s0.json' if label.startswith('sampler_') else 'bf16_s0.json'
            path = target / 'results/Qwen3-1.7B-Base' / filename
            d = json.loads(path.read_bytes())
            change(d)
            path.write_bytes((json.dumps(d, indent=2) + '\n').encode())
            side = path.with_suffix('.sha256.json')
            side.write_bytes((json.dumps(dict(name=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())) + '\n').encode())
            manifest_path = target / 'SERVER_SHA256.json'
            manifest = json.loads(manifest_path.read_bytes())
            for changed in [path, side]:
                manifest[str(changed.relative_to(target)).replace('\\', '/')] = hashlib.sha256(changed.read_bytes()).hexdigest()
            manifest_path.write_bytes((json.dumps(manifest) + '\n').encode())
            try:
                validate(target, require_complete=args.complete)
            except AssertionError:
                pass
            else:
                raise AssertionError('tamper accepted: ' + label)
    result = dict(status='PASS', original_archive_valid=True, semantic_negative_guards=list(changes))
    if args.complete:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[2] / 'work/jieruiz/144') as tmp:
            target = Path(tmp) / 'archive'
            shutil.copytree(source, target)
            # Remove a complete case and its checksums; semantic completeness must still reject it.
            manifest_path = target / 'SERVER_SHA256.json'
            manifest = json.loads(manifest_path.read_bytes())
            for suffix in ['.json', '.sha256.json']:
                name = 'results/Qwen3-4B-Base/winner1024_ffn_s2' + suffix
                (target / name).unlink()
                del manifest[name]
            manifest_path.write_bytes((json.dumps(manifest) + '\n').encode())
            try:
                validate(target, require_complete=True)
            except AssertionError:
                result['semantic_negative_guards'].append('missing_final_case')
            else:
                raise AssertionError('missing final case accepted')
    if args.output:
        Path(args.output).write_bytes((json.dumps(result, indent=2) + '\n').encode())
    print(json.dumps(result))


if __name__ == '__main__':
    main()
