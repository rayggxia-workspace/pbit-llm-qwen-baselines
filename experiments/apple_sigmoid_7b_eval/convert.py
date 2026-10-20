"""CPU Slurm conversion of verified source Zarr arrays into BF16 safetensors."""
from pathlib import Path
import argparse, gc, hashlib, json, os
import numpy as np
import torch
import tensorstore as ts
from safetensors.torch import save_file

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for x in iter(lambda:f.read(8*1024*1024),b''):h.update(x)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--dtype',choices=['float32','bfloat16'],default='bfloat16');args=p.parse_args()
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
    assert args.source.resolve().is_relative_to(Path.home().resolve())
    assert args.output.resolve().is_relative_to(Path.home().resolve())
    args.output.mkdir(exist_ok=False,parents=True)
    base=args.source/'gda/model/decoder'
    records=[]
    for meta in sorted(base.rglob('.zarray')):
        path=meta.parent.relative_to(base).as_posix()
        name=path.replace('/','__')+'.safetensors'
        spec=json.loads(meta.read_text())
        assert spec['dtype']=='<f4'
        print('CONVERT',path,spec['shape'],flush=True)
        array=ts.open({'driver':'zarr','kvstore':{'driver':'file','path':str(meta.parent)+'/'}}).result().read().result()
        assert np.isfinite(array).all()
        t=torch.from_numpy(array).to(getattr(torch,args.dtype))
        save_file({'weight':t},str(args.output/name))
        records.append({'path':path,'shape':spec['shape'],'file':name,'bytes':(args.output/name).stat().st_size,'sha256':sha(args.output/name),'source_dtype':'float32','stored_dtype':args.dtype})
        del array,t;gc.collect()
    assert len(records)==13,len(records)
    cfg={'schema':'apple-gala-inference-v1','layers':32,'hidden':4096,'heads':32,'head_dim':128,'ffn':11008,'vocab':32768,'training_seq_len':4096,'rms_eps':1e-5,'source':str(args.source),'arrays':records}
    (args.output/'config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    print('CONVERSION_COMPLETE',flush=True)

if __name__=='__main__':main()
