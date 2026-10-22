"""Package execution sources/data, then execute FFN and v6 bridge in isolation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


# Imported transitively by unified_v6.model, including historical modules whose
# classes are imported but not instantiated by the supported bridge boundary.
LEGACY_MODULES = (
    'attention_reference_v3', 'screen_ising_tlm_v4', 'attention_tlm_v3',
    'ising_macro_v4', 'system_decode', 'system_decode_local_shared_v2',
    'rng_local_shared_v2', 'rng_hierarchy', 'parallel_sampler_v5',
    'winner_hold_tlm_v5', 'corrected_rejection_tlm_v5',
    'sram_cacti_calibration_v1', 'cacti_memory',
)
RUNTIME_DATA = (
    'architecture_tlm/random_service/shared64_mapping.json',
    'architecture_tlm/llama7b/runtime/results/sram_calibration_v1_20261016/calibration.json',
)


def snapshot_paths(root):
    tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines())
    scopes = ('architecture_tlm/cycle_v1/', 'architecture_tlm/random_service/', 'architecture_tlm/unified_v6/')
    paths = {p for p in tracked if p.startswith(scopes) and '/results/' not in p
             and (p.endswith('.py') or ('/configs/' in p and p.endswith('.json')))}
    required = {*RUNTIME_DATA, *('architecture_tlm/'+name+'.py' for name in LEGACY_MODULES)}
    if missing := required-tracked:
        raise FileNotFoundError('untracked or missing runtime dependencies: '+str(sorted(missing)))
    paths.update(required)
    for name in paths:
        path = (root/name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('runtime source must be a regular file inside repository: '+name)
    return sorted(paths)


def isolated_smoke(directory, env):
    # -I ignores Python env/site injection; insert only the fresh extraction.
    smoke = '''
import json, pathlib, sys
root = pathlib.Path.cwd().resolve()
sys.path.insert(0, str(root))
from architecture_tlm.cycle_v1 import ffn
from architecture_tlm.cycle_v1.run import synthetic_fixture
from architecture_tlm.cycle_v1.v6_adapter import smoke_input, run_adapter
from architecture_tlm.cycle_v1.package_snapshot import LEGACY_MODULES
kernel = ffn.make_kernel()
state = ffn.build_ffn(kernel, synthetic_fixture()['ffn'])
result = kernel.run('event')
assert state['output'] and result.finish_ps > 0
config, shape, fixture = smoke_input('ffn')
bridge = run_adapter('ffn', config, shape, fixture, root/'snapshot-smoke'/'v6-ffn')
assert bridge['status'] == 'passed' and bridge['cycle']['cycle_event_equivalence']['equal'] is True
loaded = {}
for name, module in list(sys.modules.items()):
    if name.startswith('architecture_tlm') or name in LEGACY_MODULES:
        file = getattr(module, '__file__', None)
        if file is not None:
            path = pathlib.Path(file).resolve()
            assert path.is_relative_to(root), (name, str(path))
            loaded[name] = path.relative_to(root).as_posix()
report = {'ffn_finish_ps':result.finish_ps,'ffn_operations':len(result.accepted_ps),
          'bridge_legacy_ns':bridge['legacy']['elapsed_ns'],
          'bridge_cycle_ns':bridge['cycle']['elapsed_ns'],
          'bridge_cycle_event_equal':True,'loaded_project_modules':loaded,
          'python_isolated_flag':sys.flags.isolated,'pythonpath_environment_present':'PYTHONPATH' in __import__('os').environ}
assert report['python_isolated_flag'] == 1 and not report['pythonpath_environment_present']
print(json.dumps(report, sort_keys=True))
'''
    run = subprocess.run([sys.executable, '-I', '-X', 'utf8', '-c', smoke],
                         cwd=directory, env=env, capture_output=True, text=True, encoding='utf-8')
    log = directory/'snapshot-smoke'
    log.mkdir(exist_ok=True)
    (log/'stdout.txt').write_text(run.stdout, encoding='utf-8', newline='\n')
    (log/'stderr.txt').write_text(run.stderr, encoding='utf-8', newline='\n')
    if run.returncode:
        raise RuntimeError(f'isolated snapshot smoke failed ({run.returncode}); see {log}/stderr.txt')
    return json.loads(run.stdout)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--check-directory',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    if any(p.exists() for p in (args.archive,args.manifest,args.check_directory)):
        raise FileExistsError('choose fresh archive, manifest and extraction destinations')
    root = root.resolve()
    args.check_directory = args.check_directory.resolve()
    paths = snapshot_paths(root)
    longest = max(len(str(args.check_directory/path)) for path in paths)
    if os.name == 'nt' and longest >= 250:
        raise ValueError(f'choose a shorter extraction root (longest resulting path: {longest})')
    source_hashes = {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
    args.archive.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(args.archive,'w:gz') as archive:
        for path in paths: archive.add(root/path,arcname=path,recursive=False)
    args.check_directory.mkdir(parents=True)
    with tarfile.open(args.archive) as archive: archive.extractall(args.check_directory,filter='data')
    extracted_hashes = {p:hashlib.sha256((args.check_directory/p).read_bytes()).hexdigest() for p in paths}
    if source_hashes != extracted_hashes:
        raise AssertionError('extracted source/data bytes do not match manifest')
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    manifest={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'files':source_hashes,'extracted_files_verified':len(extracted_hashes),
        'runtime_data':list(RUNTIME_DATA),'legacy_import_modules':list(LEGACY_MODULES),
        'excluded':'model weights, fixture data, previous run results, environments and binaries',
        'longest_extracted_path_characters':longest,
        'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'isolated_extraction_smoke':'running'}
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    try:
        manifest['smoke_receipt'] = isolated_smoke(args.check_directory, env)
        manifest['isolated_extraction_smoke']='FFN and v6 bridge passed with -I and no inherited PYTHONPATH'
    except Exception as exc:
        manifest['isolated_extraction_smoke']='failed'
        manifest['failure']={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        args.manifest.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'files':len(paths),'archive':str(args.archive),'sha256':manifest['archive_sha256']}))


if __name__=='__main__': main()
