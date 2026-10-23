"""CPU allocation: pinned public Qwen3-4B, personal data, isolated environment receipt."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, time, importlib.metadata

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()

def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def personal(path):
    path=Path(path).resolve()
    home=Path('/home/Weican_Chen').resolve()
    if not path.is_relative_to(home): raise ValueError('outside personal root')
    if path.exists() and path.stat().st_uid!=os.getuid(): raise ValueError('foreign-owned path')
    return path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--identity',required=True);args=p.parse_args()
    assert os.environ.get('SLURM_JOB_ID') and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    root=personal(args.root);identity=json.loads(Path(args.identity).read_text())
    assert identity['id']=='Qwen/Qwen3-4B' and identity['sha']=='1cfa9a7208912126459214e8b04321603b3df60c'
    import torch,transformers
    assert transformers.__version__=='4.51.3'
    assert importlib.metadata.version('lm_eval')=='0.4.8'
    from transformers import Qwen3Config,Qwen3ForCausalLM,AutoTokenizer,AutoConfig
    config=Qwen3Config(vocab_size=64,hidden_size=48,intermediate_size=80,num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2,head_dim=16)
    model=Qwen3ForCausalLM(config).eval()
    with torch.no_grad(): assert torch.isfinite(model(torch.tensor([[1,2,3]])).logits).all()
    assert not torch.cuda.is_initialized()
    from huggingface_hub import snapshot_download
    allowed=[x for x in identity['siblings'] if x['rfilename'].endswith(('.json','.safetensors','.txt')) and '/' not in x['rfilename']]
    destination=personal(root/'model');destination.mkdir(exist_ok=True)
    attempts=[]
    for endpoint in ['https://hf-mirror.com','https://huggingface.co']:
        try:
            snapshot_download(repo_id=identity['id'],revision=identity['sha'],allow_patterns=[x['rfilename'] for x in allowed],local_dir=str(destination),max_workers=2,token=False,endpoint=endpoint)
            attempts.append({'endpoint':endpoint,'success':True});break
        except Exception as error:
            attempts.append({'endpoint':endpoint,'success':False,'error':repr(error)})
            save(root/'prepared/download_attempts.json',attempts)
    else:raise RuntimeError('both public download endpoints failed; resume existing files after inspection')
    files=[]
    for row in allowed:
        path=personal(destination/row['rfilename']);digest=sha(path)
        assert path.stat().st_size==row['size'],row['rfilename']
        if row.get('lfs'):assert digest==row['lfs']['sha256'],row['rfilename']
        else:
            b=path.read_bytes();assert hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()==row['blobId']
        files.append({'name':row['rfilename'],'bytes':row['size'],'sha256':digest})
    cfg=AutoConfig.from_pretrained(destination,local_files_only=True,trust_remote_code=False)
    expected={'num_hidden_layers':36,'hidden_size':2560,'num_attention_heads':32,'num_key_value_heads':8,'head_dim':128,'intermediate_size':9728}
    for key,value in expected.items():assert getattr(cfg,key)==value
    tokenizer=AutoTokenizer.from_pretrained(destination,local_files_only=True,trust_remote_code=False)
    sources={
        'wikitext-2/wiki.test.raw':('/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/data/wikitext-2/wiki.test.raw','173c87a53759e0201f33e0ccf978e510c2042d7f2cb78229d9a50d79b9e7dd08'),
        'wikitext-2/wiki.train.raw':('/home/Weican_Chen/projects/pbit-qwen-sigmoid-20260929/data/wikitext-2/wiki.train.raw','6707892fa3788b5ab9ed78ab5ff37d9fe825f6011a2ad4fcd6a6d467f0e7da57'),
        'piqa/0000.parquet':('/home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/data/piqa/0000.parquet','40e1677bba609c8801deacc171d76f3e24c083f365c95a1cbda7520c923dfea2'),
        'arc_easy/0000.parquet':('/home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/data/arc_easy/0000.parquet','4160597d618ae851c7eb04e281574f3f654776216ac6b6641588d64527b47177'),
        'hellaswag/0000.parquet':('/home/Weican_Chen/projects/pbit-pdnn-task-accuracy-issue145/data/hellaswag/0000.parquet','899813071e1e95efafec90f856e1987d2150fa4d020fc005df6962c259f660cd'),
    }
    data=[]
    for rel,(src,checksum) in sources.items():
        src=personal(src);assert sha(src)==checksum
        dest=personal(root/'data'/rel);dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert sha(dest)==checksum
        else:shutil.copyfile(src,dest)
        assert sha(dest)==checksum
        data.append({'path':str(dest),'source':str(src),'sha256':checksum,'bytes':dest.stat().st_size})
    versions={name:importlib.metadata.version(name) for name in ['torch','transformers','tokenizers','huggingface-hub','lm_eval','datasets','numpy']}
    result={'model':identity['id'],'revision':identity['sha'],'model_path':str(destination),'files':files,'data':data,'environment':versions,'shape':expected,'tokenizer_class':type(tokenizer).__name__,'tokenizer_smoke':tokenizer.encode('SparQ baseline verification.',add_special_tokens=False),'download_attempts':attempts,'job':os.environ['SLURM_JOB_ID'],'cpu_only':True,'cuda_initialized':torch.cuda.is_initialized()}
    assert not result['cuda_initialized'];save(root/'prepared/READY.json',result)
    print('PREPARED',json.dumps({'model':result['model'],'revision':result['revision'],'files':len(files),'data':len(data),'versions':versions}),flush=True)

if __name__=='__main__':main()
