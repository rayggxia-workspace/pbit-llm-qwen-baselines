"""Issue171 pilot: quantized nonlinear interfaces, not finite-stream validation."""
import argparse
import gc
import json
import os
from pathlib import Path
import platform
import sys
import torch
from transformers import AutoModelForCausalLM,AutoTokenizer
from qwen3.baselines.support import check_config,check_data,sha256,verify_files,verify_source
from qwen3.stochastic.vendor.scoring import ids_sha256
from qwen3.fixed_scale.run import score,configure,sealed
from .core import NonlinearFFN

HERE=Path(__file__).resolve().parent
def cases():
    rows=[('w8_oracle',(0,0,0))]
    rows += [('gu%d'%b,(b,0,0)) for b in (6,7,8,10,12)]
    rows += [('field%d'%b,(0,b,0)) for b in (8,10,12)]
    rows += [('prob%d'%b,(0,0,b)) for b in (6,8,10,12)]
    rows += [('combined_%d_%d_%d'%s,s) for s in ((6,8,8),(8,8,8),(8,10,8),(10,10,10),(12,12,12))]
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    root=Path(parser.parse_args().root)
    assert str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-nonlinear-width-20261024-issue171'
    assert os.environ.get('SLURM_JOB_ID')
    c=json.loads((HERE/'config.json').read_bytes())
    src=verify_source(HERE.parents[1])
    prepared_path=Path(c['prepared']);prepared=json.loads(prepared_path.read_bytes())
    assert prepared['model']==c['model'] and prepared['cpu_prepare_ok']
    verify_files(prepared);data=check_data(c)
    oldcal=Path(c['fixed_xz_calibration'])
    assert sha256(oldcal)==c['fixed_xz_calibration_sha256']
    tables=json.loads(oldcal.read_bytes())['tables']
    torch.set_num_threads(4);torch.manual_seed(0)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    tok=AutoTokenizer.from_pretrained(prepared['local_path'],local_files_only=True)
    def tokens(name):return tok(Path(data[name]['path']).read_bytes().decode('utf-8'),return_tensors='pt',add_special_tokens=False).input_ids[0]
    train,test=tokens('wiki.train.raw'),tokens('wiki.test.raw')
    assert ids_sha256(test.tolist())==prepared['test_token_ids_sha256_le_int64']
    provenance=dict(source=src,model=c['model'],prepared_sha256=sha256(prepared_path),data=data,
        train_token_sha256=ids_sha256(train.tolist()),test_token_sha256=ids_sha256(test.tolist()),
        config_sha256=sha256(HERE/'config.json'),command=[sys.executable,*sys.argv],
        environment=dict(torch=torch.__version__,cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),host=platform.node(),slurm=os.environ['SLURM_JOB_ID']),
        limitations=['suffix only','nonlinear conditional mean, no finite AND stream',
                    'FP32 matrix restoration oracle, not full bittrue FFN'])
    out=root/'results';sealed(out/'provenance.json',provenance)
    model=AutoModelForCausalLM.from_pretrained(prepared['local_path'],local_files_only=True,
        torch_dtype=torch.bfloat16,attn_implementation='sdpa').cuda().eval()
    check_config(model.config,c['model'])
    reference=score(model,test,c);reference['case']='bf16'
    reference['provenance_sha256']=sha256(out/'provenance.json');sealed(out/'bf16.json',reference)
    print('BF16',reference['perplexity'],reference['seconds'],flush=True)
    for i,l in enumerate(model.model.layers):l.mlp=NonlinearFFN(l.mlp,i).eval()
    gc.collect();torch.cuda.empty_cache()
    maxima={}
    def observe(layer,signal,value):
        maximum=value.reshape(-1,value.shape[-1]//64,64).abs().amax(dim=(0,2))
        key=(layer,signal)
        maxima[key]=torch.maximum(maxima[key],maximum) if key in maxima else maximum
    length=c['calibration_length'];starts=[round((len(train)-length)*i/(c['calibration_examples']-1)) for i in range(c['calibration_examples'])]
    for mode in ('w8_only','sampled'):
        configure(model,mode,64,917,tables,mode=='sampled',mode=='sampled')
        for l in model.model.layers:l.mlp.capture_gu=observe
        with torch.inference_mode():
            for start in starts:model.model(input_ids=train[start:start+length].unsqueeze(0).cuda(),use_cache=False)
        print('CALIBRATED',mode,flush=True)
    cal={}
    for (i,signal),m in maxima.items():
        mantissa,e=torch.frexp(m);e-=(mantissa==.5).to(e.dtype)
        e=torch.where(m==0,torch.zeros_like(e),e)
        top=torch.ldexp(torch.ones_like(m),e)
        setattr(model.model.layers[i].mlp,signal+'_top',top)
        cal.setdefault(str(i),{})[signal]=top.cpu().tolist()
    for l in model.model.layers:l.mlp.capture_gu=None
    sealed(out/'calibration.json',dict(status='completed',tables=cal,train_starts=starts,length=length,
        paths=['w8_only','fixed_xz_T64_K64_seed917'],rule='per64 g/u maxabs ceilPoT; no test access',
        fixed_xz_calibration_sha256=sha256(oldcal),provenance_sha256=sha256(out/'provenance.json')))
    del maxima
    immutable=[(t,t._version,t.data_ptr()) for t in model.parameters()]
    immutable += [(getattr(l.mlp,n),getattr(l.mlp,n)._version,getattr(l.mlp,n).data_ptr()) for l in model.model.layers
                  for n in ('gu_codes','gu_decoded','down_codes','down_decoded','g_top','u_top')]
    allcases=[(name,spec,'w8_only',0) for name,spec in cases()]
    for spec in ((0,0,0),(8,8,8),(10,10,10)):
        for seed in (0,1,2):allcases.append(('fixed64_%d_%d_%d_s%d'%(*spec,seed),spec,'sampled',seed))
    for name,spec,mode,seed in allcases:
        configure(model,mode,64,seed,tables,mode=='sampled',mode=='sampled')
        for l in model.model.layers:l.mlp.set_spec(*spec)
        print('START',name,flush=True)
        result=score(model,test,c)
        assert all(t._version==v and t.data_ptr()==ptr for t,v,ptr in immutable)
        result.update(case=name,spec=list(spec),matrix_mode=mode,matrix_samples=64 if mode=='sampled' else 0,
            seed=seed,nonlinear_mode='conditional mean; no finite sampling',
            calibration_sha256=sha256(out/'calibration.json'),provenance_sha256=sha256(out/'provenance.json'),
            diagnostics={str(i):l.mlp.nonlinear_report() for i,l in enumerate(model.model.layers)})
        assert all(l.mlp.calls==c['examples'] for l in model.model.layers)
        sealed(out/(name+'.json'),result)
        print('COMPLETE',name,result['perplexity'],result['seconds'],flush=True)
    sealed(out/'complete.json',dict(status='completed',cases=len(allcases)+1,
        documents={p.name:sha256(p) for p in sorted(out.glob('*.json')) if not p.name.endswith('.sha256.json')}))

if __name__=='__main__':main()
