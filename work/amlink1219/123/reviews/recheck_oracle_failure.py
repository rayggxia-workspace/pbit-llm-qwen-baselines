"""One fresh tiny kernel run proving artifacts precede an oracle exception."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
from unittest.mock import patch


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def read(path):
    return json.loads(path.read_bytes())


def main():
    review_dir = Path(__file__).resolve().parent
    repository = review_dir.parents[3]
    source_root = repository.parent/'fi23-int'
    evidence = repository/'architecture_tlm/ffn_cycle_integration/results/smoke_20261023'
    output = review_dir/'oracle-failure-recheck'
    output.mkdir(exist_ok=False)
    sys.path.insert(0, str(source_root))
    from architecture_tlm.cycle_v1 import ffn, run_contract_ffn
    from architecture_tlm.cycle_v1.ffn_contract import CONTRACT

    bundle = read(evidence/'fixture.json')
    profile = read(evidence/'profile.json')
    config = ffn.FFNConfig(samples=16, strata=16,
        encoding_restore_contract=CONTRACT, restore_rounding='rtl_fused0_order',
        encoding_restore_profile=profile)
    config.validate()
    original = ffn.reference_ffn_tiled
    unique_message = 'ISSUE123_ORACLE_FAILURE_RECHECK_20261023'
    captured = {}

    def raise_after_persistence(fixture_argument, config_argument):
        manifest = read(output/'artifact_manifest.json')
        mode = manifest['modes']['event']
        assert mode['complete']
        assert mode['validation_status'] == 'not yet numerically validated'
        assert not (output/'summary.json').exists()
        assert len(manifest['artifacts']) == 6
        for item in manifest['artifacts']:
            artifact = (output/item['path']).resolve()
            artifact.relative_to(output.resolve())
            raw = artifact.read_bytes()
            assert len(raw) == item['bytes'] and sha(raw) == item['sha256']
        captured.update(
            persisted_before_oracle_exception=True,
            artifacts_verified_before_exception=len(manifest['artifacts']),
            artifact_manifest_sha256_at_oracle_entry=sha((output/'artifact_manifest.json').read_bytes()),
            actual_arguments=dict(fixture=fixture_argument, config=asdict(config_argument)),
            call_stack_at_oracle_entry=traceback.format_stack())
        raise AssertionError(unique_message)

    start = time.perf_counter()
    caught = None
    with patch.object(ffn, 'reference_ffn_tiled', side_effect=raise_after_persistence) as mocked:
        try:
            run_contract_ffn.execute(bundle, config, compare_modes=False, memory_latency=4,
                max_time_ps=10**13, max_steps=10**8, artifact_dir=output)
        except AssertionError as error:
            if str(error) != unique_message:
                raise
            caught = dict(type=type(error).__name__, message=str(error), traceback=traceback.format_exc())
        call_count = mocked.call_count
    elapsed = time.perf_counter()-start
    assert caught is not None and call_count == 1
    assert ffn.reference_ffn_tiled is original
    assert not (output/'summary.json').exists()
    assert sha((output/'artifact_manifest.json').read_bytes()) == captured['artifact_manifest_sha256_at_oracle_entry']
    execution = read(output/'event/execution.json')
    assert execution['complete'] and execution['error'] is None
    sources = read(output/'source_manifest.json')
    assert sha(canonical(sources['files'])) == sources['files_sha256']
    for item in sources['files']:
        raw = (source_root/item['path']).read_bytes()
        assert len(raw) == item['bytes'] and sha(raw) == item['sha256']
    source_files = {}
    for name, path in (
        ('review_driver', Path(__file__)),
        ('runner', Path(inspect.getsourcefile(run_contract_ffn))),
        ('original_reference_dispatch', Path(inspect.getsourcefile(original))),
        ('fixture', evidence/'fixture.json'), ('profile', evidence/'profile.json')):
        source_files[name] = dict(path=str(path.resolve()), sha256=sha(path.read_bytes()))
    receipt = dict(schema='issue123.oracle_failure_recheck.1', status='passed',
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        source_checkout_head=subprocess.check_output(['git', '-C', str(source_root), 'rev-parse', 'HEAD'], text=True).strip(),
        source_files=source_files, source_files_sha256=sources['files_sha256'],
        source_manifest_sha256=sha((output/'source_manifest.json').read_bytes()),
        shape=[5, 3, 2], execute_wall_seconds=elapsed,
        execute_kwargs=dict(compare_modes=False, memory_latency=4, max_time_ps=10**13,
                            max_steps=10**8, artifact_dir=str(output)),
        original_reference=dict(module=original.__module__, name=original.__qualname__,
                                first_source_line=inspect.getsourcelines(original)[1]),
        mock_call_count=call_count, exception=caught,
        summary_absent_after_exception=True, original_function_restored=True,
        kernel_completed=True, numeric_oracle_executed=False,
        actual_arguments_sha256=sha(canonical(captured['actual_arguments'])),
        scope='fresh local tiny event-kernel exception-path check; not historical failure causality or numerical equivalence',
        **captured)
    receipt_path = review_dir/'ORACLE_FAILURE_RECEIPT.json'
    with receipt_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status='passed', execute_wall_seconds=elapsed,
        persisted_artifacts=captured['artifacts_verified_before_exception'],
        exception=caught['message'], receipt_sha256=sha(receipt_path.read_bytes()))))


if __name__ == '__main__':
    main()
