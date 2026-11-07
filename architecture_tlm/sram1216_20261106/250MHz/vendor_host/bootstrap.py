from pathlib import Path
import hashlib, importlib.util, json, sys

EXPECTED_RUNTIME = '7c5cb9b603ca2bd139ac6fa7b75d789e00c316acde994ff3db9bdcbb33c4bb40'

def use_runtime(runtime, dependencies):
    runtime, dependencies = Path(runtime).resolve(), Path(dependencies).resolve()
    raw = (runtime/'EXECUTION_MANIFEST.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_RUNTIME
    manifest = json.loads(raw)
    for name, digest in manifest['files_sha256'].items():
        if not name.startswith('inputs/'):
            assert hashlib.sha256((runtime/name).read_bytes()).hexdigest() == digest, name
    depraw = (dependencies/'MANIFEST.json').read_bytes()
    for name, record in json.loads(depraw)['files'].items():
        assert hashlib.sha256((dependencies/name).read_bytes()).hexdigest() == record['sha256'], name
    sys.path[:0] = [str(runtime), str(runtime/'base')]
    import architecture_tlm
    architecture_tlm.__path__[:] = [str(dependencies/'architecture_tlm'),
        str(runtime/'architecture_tlm'), str(runtime/'base/architecture_tlm')]
    package = 'architecture_tlm.sram1216_20261106'
    folder = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(package, folder/'__init__.py',
        submodule_search_locations=[str(folder)])
    module = importlib.util.module_from_spec(spec); sys.modules[package] = module
    spec.loader.exec_module(module)
    setattr(architecture_tlm, 'sram1216_20261106', module)
    return dict(runtime_manifest_sha256=EXPECTED_RUNTIME,
        dependencies_manifest_sha256=hashlib.sha256(depraw).hexdigest())
