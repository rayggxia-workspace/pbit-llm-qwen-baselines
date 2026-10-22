"""Load a caller-selected Issue116 checkout without copying its implementation."""
import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace


def load(root):
    folder = Path(root).resolve()/'architecture_tlm/cycle_v1'
    names = ('__init__.py', 'contracts.py', 'kernel.py', 'memory.py')
    hashes = {name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in names}
    joint = hashlib.sha256(''.join(name+hashes[name] for name in names).encode()).hexdigest()
    key = '_encoding_cycle_'+joint
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, folder/'__init__.py',
                                                    submodule_search_locations=[str(folder)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    contracts = importlib.import_module(key+'.contracts')
    kernel = importlib.import_module(key+'.kernel')
    api = SimpleNamespace(**{name:getattr(contracts, name) for name in ('Clock','Resource','Buffer','Operation')},
                          Kernel=kernel.Kernel)
    return api, hashes
