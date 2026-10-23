"""Replay unmodified, fixed PR122 software against an explicitly pinned backend.

No business source is merged, and no RTL tool is invoked. The exported source
capsule is temporary execution input; only our fresh receipts are published.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

PR_COMMIT = '8007d98f15676ad316180ee18b5d1b29aa00af95'
SCIENTIFIC_COMMIT = '3e8cb017e71a96aa628b1772810b7fdf12884245'
BACKEND_COMMIT = 'e2695e294d6b7fcb73ec9257cb63f2fe2fef0cc8'
PACKAGE = 'architecture_tlm/encoding_restore_contract/'
CORE_FILES = ('__init__.py', 'contracts.py', 'kernel.py', 'memory.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-root', type=Path, required=True)
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    root = args.backend_root.resolve()
    source = args.source_directory.resolve()
    out = args.out.resolve()
    if source.exists() or out.exists():
        raise FileExistsError('source-directory and out must be fresh')
    source.mkdir(parents=True)
    out.mkdir(parents=True)

    def blob(commit, path):
        return subprocess.check_output(['git', 'show', commit+':'+path], cwd=root)

    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', PR_COMMIT, PACKAGE],
                                    cwd=root, text=True).splitlines()
    source_names = [name for name in names if name.endswith('.py') and name.count('/') == 2]
    source_names += ['architecture_tlm/digital_ppa_v1/sim/validate.py',
                     'format_conversion_rtl_20261016/sim/reference.py']
    source_hashes = {}
    for name in source_names:
        data = blob(PR_COMMIT, name)
        target = source/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        assert target.read_bytes() == data
        source_hashes[name] = sha(data)
    backend_hashes = {}
    for name in CORE_FILES:
        relative = 'architecture_tlm/cycle_v1/'+name
        current = (root/relative).read_bytes()
        expected = blob(BACKEND_COMMIT, relative)
        assert current == expected, ('backend differs from requested commit', name)
        backend_hashes[name] = sha(current)
    # The PR's scientific source commit contains these identical software bytes.
    assert all(sha(blob(SCIENTIFIC_COMMIT, name)) == digest
               for name, digest in source_hashes.items())
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env['ENCODE_CYCLE_BACKEND'] = str(root)
    env['ENCODE_CYCLE_REVIEW_TMP'] = str(source/'review-tmp')
    commands = []

    def run(label, module, arguments):
        bootstrap = ('import pathlib,runpy,sys; '
                     'sys.path.insert(0,str(pathlib.Path.cwd().resolve())); '
                     'module=sys.argv.pop(1); runpy.run_module(module,run_name="__main__")')
        command = [sys.executable, '-I', '-X', 'utf8', '-B', '-c', bootstrap, module, *arguments]
        start = time.monotonic()
        result = subprocess.run(command, cwd=source, env=env, capture_output=True,
                                text=True, encoding='utf-8')
        (out/(label+'.stdout.txt')).write_text(result.stdout, encoding='utf-8', newline='\n')
        (out/(label+'.stderr.txt')).write_text(result.stderr, encoding='utf-8', newline='\n')
        commands.append(dict(label=label, argv=command, cwd=str(source),
                             exit_code=result.returncode, elapsed_seconds=time.monotonic()-start))
        save(out/'COMMANDS.json', commands)
        if result.returncode:
            raise RuntimeError(f'{label} failed: see {out}/{label}.stderr.txt')

    start = dict(pr_commit=PR_COMMIT, scientific_commit=SCIENTIFIC_COMMIT,
                 backend_commit=BACKEND_COMMIT, backend_source_sha256=backend_hashes,
                 exported_source_sha256=source_hashes, python=sys.version,
                 platform=platform.platform(), inherited_pythonpath=False,
                 rtl_executed_this_replay=False)
    save(out/'START.json', start)
    run('software_tests', 'unittest', ['-v',
        'architecture_tlm.encoding_restore_contract.test_arithmetic',
        'architecture_tlm.encoding_restore_contract.test_adapter',
        'architecture_tlm.encoding_restore_contract.test_review'])
    run('cycle_matrix', 'architecture_tlm.encoding_restore_contract.run_cycle',
        ['--backend-root', str(root), '--out', str(out/'cases')])
    summary = json.loads((out/'cases/SUMMARY.json').read_text(encoding='utf-8'))
    assert summary['passed'] and len(summary['cases']) == 12
    comparisons = {}
    for name in names:
        if '/results/cycle_20261023/' not in name or name.endswith('/SUMMARY.json'):
            continue
        filename = name.rsplit('/', 1)[-1]
        new = json.loads((out/'cases'/filename).read_text(encoding='utf-8'))
        old = json.loads(blob(PR_COMMIT, name))
        comparisons[filename] = {'full_json_equal_to_original_frozen_result': new == old,
                                 'original_sha256': sha(blob(PR_COMMIT, name))}
    assert all(x['full_json_equal_to_original_frozen_result'] for x in comparisons.values()), comparisons
    frozen_path = 'work/amlink1219/121/VALIDATION.json'
    frozen_bytes = blob(PR_COMMIT, frozen_path)
    frozen = json.loads(frozen_bytes)
    receipt = dict(**start, passed=True, software_unit_tests=28,
                   cycle_cases=len(summary['cases']),
                   restore_outputs=sum(case['restore_outputs'] for case in summary['cases']),
                   frozen_result_comparisons=comparisons,
                   historical_rtl_reference_only=dict(path=frozen_path, sha256=sha(frozen_bytes),
                       cases=frozen['rtl_cases'], outputs=frozen['rtl_outputs'],
                       executed_by_this_replay=False),
                   limits=['No source merge or edit to PR122', 'No RTL re-execution',
                           'No full FFN integration', 'No STA/PPA/PPL claim'])
    save(out/'COMPATIBILITY.json', receipt)
    hashes = {p.relative_to(out).as_posix(): sha(p.read_bytes())
              for p in out.rglob('*') if p.is_file()}
    save(out/'MANIFEST.json', hashes)
    print(json.dumps(dict(passed=True, software_unit_tests=28, cycle_cases=12,
                          restore_outputs=1536, frozen_jsons_equal=len(comparisons))))


if __name__ == '__main__':
    main()
