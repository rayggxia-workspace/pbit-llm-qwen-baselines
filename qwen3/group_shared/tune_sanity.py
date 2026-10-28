"""Unexpected-regression cross-check against independent decoded readout."""
import argparse,hashlib,json,os,pathlib
import torch
from torch.nn import functional as F
from qwen3.group_shared.recal_run import context,load
from qwen3.group_shared.tune_core import TunedFFN,encode_threshold
from qwen3.group_shared.recal_core import RecalibratedFFN
from qwen3.group_shared.pot_weight import exact_pow2
from qwen3.group_shared.independent_gate import original_g_field
from qwen3.fixed_scale.run import sealed
from qwen3.baselines.support import sha256

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=pathlib.Path(a.root);out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=False)
    assert os.environ.get('SLURM_JOB_ID') and str(root)=='/home/Hongjie_Zeng/projects/pbit-qwen3-group64-scale-20261028-issue206'
    torch.manual_seed(0);torch.set_num_threads(4);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    here,c,src,pp,prep,data,tok,test=context();assert src['commit']=='d825f7d6e0757a5f847693922cf0d3018ea3a00d'
    cal=root/'results/d825f7d6e075/tune4/calibration/tables.json';assert sha256(cal)=='e1f511278f627320daabb8d0c2bbd88aab293115ec4e0efc4437d5df94de7924';tables=json.loads(cal.read_bytes())['tables']
    xz=json.loads(pathlib.Path(c['fixed_xz_calibration']).read_bytes())['tables'];train=tok(pathlib.Path(data['wiki.train.raw']['path']).read_bytes().decode(),return_tensors='pt',add_special_tokens=False).input_ids[0];model=load(prep,c);rows=[];handles=[]
    def reset(m,i):
        m.mode='sampled';m.cycles=64;m.strata=64;m.x_scales=torch.tensor(xz[str(i)]['x'],device='cuda',dtype=torch.float32);m.rng_input.manual_seed(700001+i*7)
        m.set_spec(8,8,8);m.reset_short('lower_half','joint32',128,0);m.reset_gu('fixed',64,0);m.reset_gate('max');m.nonlinear_mean=False
    def check(original,args,i):
        x=args[0][:,-16:,:].contiguous();input_sha=hashlib.sha256(x.view(torch.uint16).cpu().numpy().tobytes()).hexdigest()
        tuned=TunedFFN(original,i).eval();parent=RecalibratedFFN(original,i).eval()
        for name,layers in tables.items():
            e=layers[str(i)];tuned.install_tuned(e['g'],e['u'],e['g_delta'],e['u_delta']);reset(tuned,i)
            y=tuned(x);finite_sha=hashlib.sha256(y.view(torch.uint16).cpu().numpy().tobytes()).hexdigest();parent_equal=None
            if not e['thresholds_tuned']:
                parent.install_catalog(e['g'],e['u']);reset(parent,i);yp=parent(x);parent_equal=torch.equal(y,yp);assert parent_equal,('parent finite mismatch',i,name)
            reset(tuned,i);g,u=tuned._stage(x.float(),'x','gu',tuned.rng_input).chunk(2,-1)
            gc,gs,ge,_,_=encode_threshold(g,tuned.g_levels,tuned.g_threshold_delta,tuned.g_carrier)
            uc,us,ue,_,_=encode_threshold(u,tuned.u_levels,tuned.u_threshold_delta,tuned.u_carrier)
            gate=tuned.lut[original_g_field(g)+128].double()/256
            z=(gs*gc.double()*exact_pow2(ge)/256)*(us*uc.double()*exact_pow2(ue)/256)*gate
            reference=F.linear(z.float(),tuned.down_decoded).to(x.dtype)
            reset(tuned,i);tuned.nonlinear_mean=True;actual=tuned(x);equal=torch.equal(reference,actual);assert equal,('direct mean mismatch',i,name,float((reference.float()-actual.float()).abs().max()))
            rows.append(dict(layer=i,scheme=name,input_sha256=input_sha,finite_sha256=finite_sha,parent_finite_equal=parent_equal,direct_mean_equal=equal,max_absolute_difference=0.));print('PASS',i,name,flush=True)
        del tuned,parent
    for i in (0,12,24,35):handles.append(model.model.layers[i].mlp.register_forward_pre_hook(lambda module,args,i=i:check(module,args,i)))
    with torch.inference_mode():model.model(input_ids=train[10000:12048].unsqueeze(0).cuda(),use_cache=False)
    for h in handles:h.remove()
    assert len(rows)==16
    result=dict(status='completed',foundation_source=src,probe_source_sha256=sha256(pathlib.Path(__file__)),calibration_sha256=sha256(cal),prepared_sha256=sha256(pp),slurm=os.environ['SLURM_JOB_ID'],train_span=[10000,12048],rows=rows,finite_parent_comparisons=8,direct_decoded_mean_comparisons=16,limitations='representative4layers/16rows;not proof fullchain integer GU;does not replace model PPL')
    sealed(out/'sanity.json',result);sealed(out/'complete.json',dict(status='completed',documents={'sanity.json':sha256(out/'sanity.json')}))

if __name__=='__main__':main()
