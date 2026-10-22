"""Allocation-only environment/input gates, without GPU initialization in CPU mode."""
from pathlib import Path
import argparse, hashlib, json, os, platform, pwd, sys, time

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);p.add_argument('--gpu',action='store_true');a=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID'),'Computation requires a Slurm allocation'
    home=Path('/home/Weican_Chen');assert pwd.getpwuid(os.getuid()).pw_name=='Weican_Chen' and Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()==home
    out=Path(a.output).resolve();assert out.is_relative_to(home);out.mkdir(parents=True,exist_ok=True)
    if not a.gpu:assert os.environ.get('CUDA_VISIBLE_DEVICES')=='','CPU preflight must hide GPUs'
    import torch,transformers,numpy
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8'));model=Path(cfg['model']).resolve();text=Path(cfg['text']).resolve()
    assert model.is_relative_to(home) and text.is_relative_to(home)
    record={'job':os.environ['SLURM_JOB_ID'],'node':platform.node(),'python':sys.executable,'prefix':sys.prefix,
            'torch':torch.__version__,'transformers':transformers.__version__,'numpy':numpy.__version__,
            'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'gpu_requested':a.gpu,
            'source_commit':os.environ.get('GATE_SOURCE_COMMIT'),'config_sha256':sha(a.config),'inputs':{}}
    for path in [text]+[model/n for n in ['model.safetensors','config.json','tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','generation_config.json']]:
        assert path.is_file(),str(path)
        record['inputs'][str(path)]={'bytes':path.stat().st_size,'sha256':sha(path)}
    assert record['inputs'][str(text)]['sha256']==cfg['expected_text_sha256'],'Training corpus mismatch'
    assert record['inputs'][str(model/'model.safetensors')]['sha256']==cfg['expected_model_sha256'],'Model weights mismatch'
    if a.gpu:
        assert os.environ.get('CUDA_VISIBLE_DEVICES') not in (None,''),'No explicit GPU allocation'
        assert torch.cuda.is_available() and torch.cuda.device_count()==1
        record['gpu_name']=torch.cuda.get_device_name(0)
        t=torch.ones((2,2),device='cuda');assert float((t@t)[0,0].item())==2
    else:assert not torch.cuda.is_initialized()
    record['status']='passed';record['scope']='Input/environment gate; not PPL or training'
    (out/'ENVIRONMENT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
