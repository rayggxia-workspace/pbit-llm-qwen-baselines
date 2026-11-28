"""Analyze sealed capture from the statistics-only failure; no model forward."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys


def main():
    assert os.environ.get('SLURM_JOB_ID')
    root=Path(sys.argv[1]);settings=json.loads((root/'RECOVERY.json').read_bytes())
    source=Path(settings['source']);output=root/'outputs';assert not output.exists();output.mkdir()
    mf=json.loads((source/'EXECUTION_MANIFEST.json').read_bytes())
    for n,d in mf['files'].items():assert hashlib.sha256((source/n).read_bytes()).hexdigest()==d,n
    previous=Path(settings['capture_root']);raw=previous/'outputs/ACTIVATIONS.pt'
    assert hashlib.sha256(raw.read_bytes()).hexdigest()==settings['capture_sha256']
    assert 'observer last-token logits bitwise equality PASS' in (previous/'slurm-6320.log').read_text()
    inputs=json.loads((previous/'INPUTS.json').read_bytes())
    original=previous.parent/'gpu_run_v1/outputs/RESULT.json'
    assert hashlib.sha256(original.read_bytes()).hexdigest()==settings['original_result_sha256']
    parent=json.loads(original.read_bytes());assert parent['status']=='completed'
    runtime=(previous/'assets/runtime').resolve()
    rm=runtime/'SOURCE_MANIFEST.json'
    assert hashlib.sha256(rm.read_bytes()).hexdigest()=='eb23a172efbd18e3e56060a6b10d2bfcde33fc7a014c5b10949038921ffb9076'
    for n,d in json.loads(rm.read_bytes()).items():assert hashlib.sha256((runtime/n).read_bytes()).hexdigest()==d,n
    assigned=os.environ['CUDA_VISIBLE_DEVICES'].split(',')
    available=[d for d in assigned if int(subprocess.check_output(['nvidia-smi','-i',d,'--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip())>=8192]
    assert available,'No sufficiently free assigned GPU'
    os.environ['CUDA_VISIBLE_DEVICES']=available[0]
    os.environ['CUBLAS_WORKSPACE_CONFIG']=':4096:8'
    sys.path.insert(0,str(runtime))
    import torch
    from diagnose import check_moments,analyze
    from seven_deployment import load_ffn
    torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False
    torch.use_deterministic_algorithms(True);check_moments()
    captured={int(k):{n:v.cuda() for n,v in pair.items()} for k,pair in torch.load(raw,map_location='cpu',weights_only=True).items()}
    deployment=Path(inputs['T64_deployment']);export=json.loads((deployment/'export_complete.json').read_bytes())
    assert hashlib.sha256((deployment/'export_complete.json').read_bytes()).hexdigest()==parent['identity']['export_manifest_sha256']
    modules={}
    for layer in captured:
        p=deployment/('ffn_%02d.pt'%layer)
        assert hashlib.sha256(p.read_bytes()).hexdigest()==export['files'][p.name]
        payload=torch.load(p,map_location='cpu',weights_only=True)
        modules[layer]=load_ffn(payload,device='cuda',backend='exact_int8');del payload
    print('Five isolated FFN modules loaded; model forward not repeated',flush=True)
    analyze(captured,modules,parent['identity'],parent['protocol'],output,mf,raw,
            dict(observer_logits_noop_bitwise=True,numeric_moments_tests=True,
                 capture_job='6320',statistics_recovery_job=os.environ['SLURM_JOB_ID'],model_forward_repeated=False))


if __name__=='__main__':main()
