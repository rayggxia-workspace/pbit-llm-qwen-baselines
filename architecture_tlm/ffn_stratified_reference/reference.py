"""Pinned behavioral FFN profiles. Reuse the merged sampler; no TLM/PPA override."""
from pathlib import Path
import argparse,copy,hashlib,importlib,json,sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def _sha(raw):return hashlib.sha256(raw).hexdigest()

def configuration():
    return json.loads((HERE/'reference.json').read_text(encoding='utf-8'))

def verify_sources():
    """Check source contents; permit CRLF/LF-only checkout differences.

    Original Git blob byte hashes remain recorded separately. This exception
    applies to Python source text, never to signed experiment artifacts.
    """
    cfg=configuration();records=[]
    for row in cfg['implementation']['files']:
        path=(ROOT/row['path']).resolve()
        if not path.is_relative_to(ROOT):raise ValueError('Source path escapes repository')
        raw=path.read_bytes();exact=_sha(raw)==row['sha256']
        if not exact and _sha(raw.replace(b'\r\n',b'\n'))!=row['lf_text_sha256']:
            raise ValueError('Pinned source differs: '+row['path'])
        records.append(dict(path=row['path'],exact_original_bytes=exact,
                            actual_sha256=_sha(raw),source_git_sha256=row['sha256']))
    return records

def profile(name=None):
    cfg=configuration();name=cfg['default_profile'] if name is None else name
    if name not in cfg['profiles']:raise ValueError('Unknown FFN reference profile: '+str(name))
    result=copy.deepcopy(cfg['profiles'][name]['constructor'])
    t,k=result['cycles'],result['strata']
    if type(t) is not int or type(k) is not int or t<1 or k<1 or 256%k or t%k:
        raise ValueError('Invalid T/K in reference configuration')
    if result['mode']!='sampled' or result['policy'] not in ('pot2','pot4'):
        raise ValueError('Unexpected FFN encoding in reference configuration')
    return result

def build_ffn(original,*,name=None,seed=0,layer=0):
    """Build one FFN only; caller owns model coverage and matched controls."""
    if type(seed) is not int or seed<0 or type(layer) is not int or not 0<=layer<24:
        raise ValueError('Nonnegative seed and Qwen layer 0..23 are required')
    verify_sources()
    if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
    module=importlib.import_module('experiments.qwen_multiscale_stratified_20261019.stratified_core')
    expected={
        'core':'experiments/qwen_dual_iid_exact_20261018/vendor/frozen/core.py',
        'shared_counts':'experiments/qwen_dual_iid_exact_20261018/vendor/frozen/shared_counts.py',
        'range_core':'experiments/qwen_dual_range_20261018/range_core.py',
        module.__name__:'experiments/qwen_multiscale_stratified_20261019/stratified_core.py',
    }
    for key,rel in expected.items():
        loaded=sys.modules.get(key)
        if loaded is None or Path(loaded.__file__).resolve()!=(ROOT/rel).resolve():
            raise RuntimeError('Conflicting imported sampler dependency: '+key)
    return module.StratifiedFFN(original,seed=seed,layer=layer,**profile(name)).eval()

def smoke():
    """CPU interface check, not model PPL or finite-width hardware validation."""
    import torch
    from torch import nn
    if torch.cuda.is_initialized():raise RuntimeError('CPU smoke must not initialize CUDA')
    results=[]
    for name in configuration()['profiles']:
        torch.manual_seed(55)
        original=nn.Module()
        original.gate_proj=nn.Linear(128,128,bias=False)
        original.up_proj=nn.Linear(128,128,bias=False)
        original.down_proj=nn.Linear(128,128,bias=False)
        ffn=build_ffn(original,name=name)
        with torch.inference_mode():values=ffn(torch.randn(2,3,128,dtype=torch.bfloat16))
        diag=ffn.diagnostics();p=profile(name)
        assert values.shape==(2,3,128) and values.dtype==torch.bfloat16 and torch.isfinite(values).all()
        assert diag['cycles']==p['cycles'] and diag['strata']==p['strata']
        assert not diag['weight_stochastic'] and not diag['finite_width_bittrue']
        results.append(dict(profile=name,constructor=p,shape=list(values.shape),dtype=str(values.dtype)))
    return dict(passed=True,scope='CPU toy-module interface only; no model PPL/PPA',
                torch=torch.__version__,cuda_initialized=torch.cuda.is_initialized(),profiles=results)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
    output=dict(source_checks=verify_sources(),default_profile=configuration()['default_profile'])
    if args.smoke:output['smoke']=smoke()
    print(json.dumps(output,ensure_ascii=False,indent=2))
