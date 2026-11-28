"""Run control-complete session on the existing unified_v6 event kernel."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import types
from dataclasses import replace

HERE=Path(__file__).resolve().parent
if not __package__:
    # Sparse task checkouts keep only this extension, not a duplicate runtime.
    package=types.ModuleType('plpu_session');package.__path__=[str(HERE)]
    sys.modules['plpu_session']=package
    __package__='plpu_session'
from .session_program import Model
from .session_control import Session


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_core(path):
    spec=importlib.util.spec_from_file_location('plpu_existing_shared_memory',path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--memory-kernel',type=Path,default=HERE/'session_memory_reference.py')
    p.add_argument('--profile',type=Path,default=HERE/'session_profile.json')
    p.add_argument('--prompt',type=int,default=4)
    p.add_argument('--generated',type=int,default=2)
    p.add_argument('--rows',type=int,default=4)
    p.add_argument('--seed',type=int,default=17)
    p.add_argument('--model',choices=['qwen3','llama_template','small'],default='qwen3')
    p.add_argument('--layers',type=int)
    p.add_argument('--sram-backend',choices=['burst','beat'],default='burst')
    p.add_argument('--dma-backend',choices=['burst','beat_analytic'],default='burst')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    hw=json.loads(a.profile.read_bytes());hw['sram_backend']=a.sram_backend;hw['dma_backend']=a.dma_backend;model=Model()
    assert a.dma_backend!='beat_analytic' or a.sram_backend=='beat'
    if a.model=='small':
        model=Model(name='synthetic128',revision='fixture',layers=2,hidden=128,
                    ffn=256,q_heads=2,kv_heads=1,head_dim=64,vocab=137)
    elif a.model=='llama_template':
        model=replace(model,name='synthetic_llama_template',revision='not_a_checkpoint',qk_norm=False)
    if a.layers:
        model=replace(model,layers=a.layers)
    sources={x.name:sha(x) for x in HERE.glob('session*.py')}
    sources['run_session.py']=sha(Path(__file__))
    sources['session_profile.json']=sha(a.profile)
    sources['external_shared_memory.py']=sha(a.memory_kernel)
    started=time.time()
    session=Session(load_core(a.memory_kernel),model,hw,a.prompt,a.generated,a.rows,a.seed)
    session.sim.run(session.execute())
    result=session.report();result['host_seconds']=time.time()-started
    result['sources_sha256']=sources
    for name,value in [('RESULT.json',result),('PLAN.json',session.plan),('HARDWARE.json',hw)]:
        (a.out/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    files={x.name:sha(x) for x in a.out.glob('*.json')}
    (a.out/'SEAL.json').write_bytes((json.dumps(dict(status='completed',sha256=files),indent=2)+'\n').encode('utf-8'))
    print(json.dumps(dict(status=result['status'],first_token_ms=result['first_token_ms'],
        elapsed_ms=result['elapsed_ms'],host_seconds=result['host_seconds'],
        state_slots=result['state_peak_slots'],frames=result['frames'])),flush=True)


if __name__=='__main__':
    main()
