"""Load frozen runtime/dependencies, then bind only this isolated overlay."""
from pathlib import Path
import hashlib, importlib.util, json, sys
HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bind(name,folder):
    spec=importlib.util.spec_from_file_location(name,folder/'__init__.py',submodule_search_locations=[str(folder)])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

def bootstrap(runtime,dependencies):
    spec=importlib.util.spec_from_file_location('frozen_compact_boot',HERE/'vendor_host/bootstrap.py')
    boot=importlib.util.module_from_spec(spec);spec.loader.exec_module(boot)
    identity=boot.use_runtime(runtime,dependencies)
    bind('architecture_tlm.attention_unified250_20261107',HERE/'vendor_attention')
    bind('whole250',HERE)
    identity['overlay_files_sha256']={p.relative_to(HERE).as_posix():sha(p)
        for p in sorted(HERE.rglob('*')) if p.is_file() and p.suffix in ('.py','.json')
        and p.name not in ('VALIDATION.json','ASSEMBLY_STATUS.json') and 'results' not in p.parts}
    return identity
