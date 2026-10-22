"""Read-only independent artifact audit; writes only adjacent REVIEW.json."""
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def read(path):
    return json.loads(path.read_bytes())


def relative(root, name):
    assert '\\' not in name
    path = (root/name).resolve()
    path.relative_to(root.resolve())
    assert path.is_file()
    return path


def verify_record(root, item):
    raw = relative(root, item['path']).read_bytes()
    assert len(raw) == item['bytes'], item['path']
    assert sha(raw) == item['sha256'], item['path']


def main():
    repository = Path(__file__).resolve().parents[4]
    evidence = repository/'architecture_tlm/ffn_cycle_integration/results/smoke_20261023'
    source_root = repository.parent/'fi23-int'
    outer_raw = (evidence/'MANIFEST.json').read_bytes()
    outer = json.loads(outer_raw)
    actual = {p.relative_to(evidence).as_posix() for p in evidence.rglob('*') if p.is_file() and p.name != 'MANIFEST.json'}
    assert set(outer) == actual
    for name, record in outer.items():
        verify_record(evidence, dict(record, path=name))
    fixture = read(evidence/'fixture.json')
    fixture = fixture.get('ffn', fixture)
    matrix_rows = lambda name: len(fixture[name]['codes'] if isinstance(fixture[name], dict) else fixture[name])
    shape = [len(fixture['x']), matrix_rows('wg'), matrix_rows('wd')]
    lengths = dict(gate=shape[1], up=shape[1], z=shape[1], projected=shape[2], output=shape[2])
    cases = {}
    for name in ('final_evidence_result', 'injected_oracle_failure', 'injected_kernel_limit'):
        folder = evidence/name
        manifest = read(folder/'artifact_manifest.json')
        records = manifest['artifacts']
        assert len(records) == len({r['path'] for r in records})
        for item in records:
            verify_record(folder, item)
        sources = read(folder/'source_manifest.json')
        assert sha(canonical(sources['files'])) == sources['files_sha256']
        assert manifest['sources'] == sources
        source_changes = []
        publication_changes = []
        publication_missing = []
        for item in sources['files']:
            path = relative(source_root, item['path'])
            raw = path.read_bytes()
            if len(raw) != item['bytes'] or sha(raw) != item['sha256']:
                source_changes.append(item['path'])
            published = repository/item['path']
            if not published.is_file():
                publication_missing.append(item['path'])
            elif len(published.read_bytes()) != item['bytes'] or sha(published.read_bytes()) != item['sha256']:
                publication_changes.append(item['path'])
        trace_record = next(r for r in records if r['path'] == 'event/trace.jsonl.gz')
        raw = gzip.decompress((folder/'event/trace.jsonl.gz').read_bytes())
        assert len(raw) == trace_record['uncompressed_bytes']
        assert sha(raw) == trace_record['uncompressed_sha256']
        rows = raw.splitlines(keepends=True)
        trace = [json.loads(row) for row in rows]
        assert all(canonical(event)+b'\n' == row for event, row in zip(trace, rows))
        assert len(rows) == trace_record['records']
        assert all(a['time_ps'] <= b['time_ps'] for a, b in zip(trace, trace[1:]))
        execution = read(folder/'event/execution.json')
        mode_record = manifest['modes']['event']
        assert sha(raw) == mode_record['trace_stream_sha256']
        accept = {event['op']:event['time_ps'] for event in trace if event['kind'] == 'accept'}
        complete = {event['op']:event['time_ps'] for event in trace if event['kind'] == 'complete'}
        assert accept == execution['accepted_ps'] and complete == execution['completion_ps']
        assert len(accept) == sum(event['kind'] == 'accept' for event in trace)
        assert len(complete) == sum(event['kind'] == 'complete' for event in trace)
        assert set(complete) <= set(accept)
        actions = Counter()
        config = manifest.get('config')
        if config is not None:
            depth = config['encoding_restore_profile']['restore_depth']
            lanes = config['encoding_restore_profile']['restore_lanes']
            depths = {f'ffn.er.restore{i}':depth for i in range(lanes)}
        else:
            # Older receipts did not bind configuration. Reconstruct the initial
            # free credits from the final snapshot and traced token transfers;
            # this is a consistency check, not proof of a configured capacity.
            depths = {}
            for key, free in execution['buffer_final'].items():
                if re.fullmatch(r'ffn\.er\.restore\d+\.free', key):
                    lane = key[:-5]
                    takes = sum(e['kind'] == 'accept' and e['resource'] == lane for e in trace)
                    returns = sum(e.get('outputs', {}).get(key, 0) for e in trace if e['kind'] == 'complete')
                    depths[lane] = free+takes-returns
        credits = {lane:[depth, 0, 0, 0] for lane, depth in depths.items()}
        for event in trace:
            kind = event['kind']
            if kind == 'accept':
                actions.update(event.get('actions', {}))
                if 'size_bytes' in event:
                    prefix = f"memory.{event['resource']}.{'write' if event['write'] else 'read'}"
                    actions[prefix+'_bytes'] += event['size_bytes']
                    actions[prefix+'_requests'] += 1
                    actions[prefix+'_beats'] += sum(event['bank_beats'].values())
            for lane, counters in credits.items():
                if kind == 'accept':
                    if event['resource'] == lane:
                        counters[0] -= 1; counters[1] += 1
                    if lane+'.ready' in event.get('inputs', {}):
                        counters[2] -= 1; counters[3] += 1
                elif kind == 'complete':
                    if event['resource'] == lane:
                        counters[1] -= 1; counters[2] += 1
                    if lane+'.free' in event.get('outputs', {}):
                        counters[3] -= 1; counters[0] += 1
                assert sum(counters) == depths[lane] and min(counters) >= 0
        assert dict(actions) == execution['actions']
        thresholds = read(folder/'event/thresholds.json')
        words = thresholds['thresholds']
        assert set(words) == {'x', 'z'}
        assert sha(canonical(words)) == thresholds['thresholds_sha256']
        observed = [v for groups in words.values() for group in groups for v in group if v is not None]
        assert all(type(v) is int and 0 <= v <= 255 for v in observed)
        if execution['complete']:
            assert len(words['x']) == math.ceil(shape[0]/64) and len(words['z']) == math.ceil(shape[1]/64)
            for groups in words.values():
                for group in groups:
                    assert len(group) in (16, 32, 64) and None not in group
                    if config is not None:
                        samples, strata = config['samples'], config['strata']
                        assert len(group) == samples
                        assert Counter(v//(256//strata) for v in group) == Counter({i:samples//strata for i in range(strata)})
        stages = read(folder/'event/stages.fp32.json')
        assert set(stages['stages']) == set(lengths)
        stage_bytes = {}
        for field, item in stages['stages'].items():
            if item is None:
                assert not execution['complete']
                continue
            assert all(re.fullmatch('[0-9a-f]{8}', word) for word in item['raw_words_hex'])
            raw_field = b''.join(struct.pack('<I', int(word, 16)) for word in item['raw_words_hex'])
            assert len(raw_field) == item['bytes'] == 4*item['values']
            assert sha(raw_field) == item['fp32le_sha256']
            if execution['complete']:
                assert item['values'] == lengths[field]
            stage_bytes[field] = raw_field
        assert thresholds['complete'] == stages['complete'] == mode_record['complete'] == execution['complete']
        native = read(folder/'event/native_random.json')
        assert native['report_available'] == execution['complete']
        if name == 'final_evidence_result':
            summary = read(folder/'summary.json')
            assert summary['shape'] == shape
            assert execution['complete'] and mode_record['validation_status'] == 'independent numerical checks passed'
            assert all(summary['numerical_validation']['bit_equal_fields'].values())
            assert summary['trace_stream_sha256'] == sha(raw)
            assert summary['source_manifest'] == sources
            assert summary['artifact_manifest'] == manifest
            assert summary['actions'] == execution['actions']
            for field in ('projected', 'output'):
                assert struct.pack('<'+'f'*len(summary[field]), *summary[field]) == stage_bytes[field]
            output = stage_bytes['output']
            if manifest['config']['output_bf16']:
                output = b''.join(output[i+2:i+4] for i in range(0, len(output), 4))
            assert sha(output) == summary['output_memory_sha256']
            assert execution['buffer_final'] == {k:v['initial'] for k, v in summary['storage'].items()}
            assert all(c == [depths[lane], 0, 0, 0] for lane, c in credits.items())
        else:
            assert not (folder/'summary.json').exists()
            assert mode_record['validation_status'] == 'not yet numerically validated'
            if name == 'injected_kernel_limit':
                assert not execution['complete'] and execution['error']['type'] == 'RuntimeError'
                assert 'execution limit' in execution['error']['message']
            else:
                assert execution['complete'] and execution['error'] is None
        cases[name] = dict(artifact_records=len(records), trace_records=len(trace),
            trace_uncompressed_bytes=len(raw), trace_uncompressed_sha256=sha(raw),
            observed_threshold_words=len(observed), fp32_fields_verified=len(stage_bytes),
            complete=execution['complete'], validation_status=mode_record['validation_status'],
            source_records=len(sources['files']), source_differences_from_current_checkout=source_changes,
            source_differences_from_publication_tree=publication_changes,
            source_files_absent_from_publication_tree=publication_missing,
            config_bound=config is not None, threshold_stratification_checked=config is not None and execution['complete'],
            per_lane_credit_conservation_checked=True,
            credit_capacity_basis='recorded config' if config is not None else 'reconstructed from trace and final snapshot; historical config absent')
    assert (evidence/'MANIFEST.json').read_bytes() == outer_raw
    head = subprocess.check_output(['git', '-C', str(source_root), 'rev-parse', 'HEAD'], text=True).strip()
    receipt_path = Path(__file__).with_name('ORACLE_FAILURE_RECEIPT.json')
    receipt = read(receipt_path)
    assert receipt['status'] == 'passed' and receipt['mock_call_count'] == 1
    assert receipt['exception']['type'] == 'AssertionError'
    assert receipt['exception']['message'] == 'ISSUE123_ORACLE_FAILURE_RECHECK_20261023'
    assert receipt['persisted_before_oracle_exception'] and receipt['summary_absent_after_exception']
    fresh = Path(__file__).parent/'oracle-failure-recheck'
    fresh_manifest = read(fresh/'artifact_manifest.json')
    for item in fresh_manifest['artifacts']:
        verify_record(fresh, item)
    assert not (fresh/'summary.json').exists()
    review = dict(schema='issue123.smoke_artifact_review.1', status='passed_with_evidence_limit',
        evidence_root=evidence.relative_to(repository).as_posix(), indexed_files=len(outer),
        outer_manifest_sha256=sha(outer_raw), shape=shape, current_source_checkout_head=head,
        independently_executed=['24 indexed byte-size/SHA256 checks', 'nested artifact and source-list canonical hashes',
            'gzip decompression/CRC, canonical JSONL/raw bytes/count/digest', 'trace accept/complete/action reconstruction',
            'actual thresholds digest/range; stratified occupancy for config-bound successful case', 'FP32 rawword little-endian digest/length',
            'summary output and BF16 memory digest', 'per-lane free/flight/ready/add credit conservation',
            'success vs unvalidated/incomplete status cross-checks',
            'one fresh 5x3x2 event kernel with mocked reference failure; persisted-before-exception checks'],
        cases=cases, fresh_oracle_failure=dict(receipt='ORACLE_FAILURE_RECEIPT.json', sha256=sha(receipt_path.read_bytes()),
            status=receipt['status'], execute_wall_seconds=receipt['execute_wall_seconds'],
            purpose='independently establishes current exception path; does not retroactively prove the historical injection cause'),
        evidence_limits=[
            'injected_oracle_failure proves completed kernel artifacts persisted before numerical validation, but contains no saved oracle exception/injection receipt; cause is not independently established by directory name',
            'execution.json validation_status is the earlier prevalidation checkpoint; final artifact_manifest/summary are authoritative when present',
            'historical injection manifests omit config: their threshold stratification and configured credit capacity cannot be independently bound',
            'fi23-int active_memory.py is a newer working-tree variant; its exact SHA is bound by the fresh recheck source manifest, while the successful historical package binds the published fi23 version',
            'historical injected runs bind older exact source hashes; do not relabel them as execution of the final checkout'],
        not_executed=['no original numeric oracle rerun: fresh oracle was deliberately mocked to raise', 'no full 896x4864x896 execution', 'no remote access or job submission',
                      'no DC/VCS/PT/STA/PPA', 'no independent rerun of parent-reported 23 tests or RTL45'])
    output = Path(__file__).with_name('REVIEW.json')
    with output.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(review, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=review['status'], files=len(outer), cases=cases), ensure_ascii=False))


if __name__ == '__main__':
    main()
