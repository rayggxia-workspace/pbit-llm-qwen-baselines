"""Extra independent restoration oracle for every proposed sampler family.

Runs on a Slurm GPU, imports an immutable quality snapshot and the original
frozen arithmetic. No trained model, checkpoint edit or model inference.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    old=Path('/home/Hongjie_Zeng/projects/ffn-stratified-validation-issue204-20261105')
    sys.path[:0]=[str(a.source),str(old/'real_activity_source_7c8ee7deb401'),str(old/'runtime_original')]
    import numpy as np
    import torch
    import seven_forward as sf
    from sparse_sampling import sample,compact,input_mass
    from sparse_gu import pack_bank,project,multiply_checked
    from sampling import shared_input_counts
    from types import SimpleNamespace
    torch.backends.cuda.matmul.allow_tf32=False
    plan=json.loads((a.source/'PLAN.json').read_bytes())
    torch.manual_seed(901)
    n,m,rows=128,128,4
    codes=torch.randint(0,257,(rows,n),device='cuda');codes[0]=0
    bins=torch.randint(0,4,(rows,n),device='cuda')
    signs=(torch.randint(0,2,(rows,n),device='cuda')*2-1).long()
    tops=torch.tensor([[16.,4.,1.,.25],[8.,2.,.5,.125]],device='cuda')
    module=SimpleNamespace(x_scales=tops)
    weights=torch.randint(-127,128,(2*m,n),device='cuda',dtype=torch.int16)
    ew=torch.randint(-8,-2,(2*m//64,n//64),device='cuda')
    step=sf.pow2_exact(ew)
    bank=pack_bank(weights,64)
    # Float64 is exact for this deliberately bounded dyadic toy dot. The
    # independent NumPy formula does not use the DUT coefficients or finish.
    w=weights.cpu().numpy().astype(np.float64)
    wd=w*np.exp2(ew.cpu().numpy().repeat(64,0).repeat(64,1))
    xscale=tops[:,0].repeat_interleave(64)[None,:]/(1 << (2*bins))
    mass,total,unit=input_mass(codes,bins,tops)
    np.testing.assert_array_equal(mass.cpu().numpy()*2.**unit,
        (codes.double()*xscale.double()/256).cpu().numpy())
    checks=[]
    for case in plan['cases']:
        s=sample(codes,{'bin_id':bins},module,case,
                 torch.Generator(device='cuda').manual_seed(991),shared_input_counts)
        normalized=s['mass'] is not None
        if normalized:
            top=sf.pow2_exact(torch.full((n//64,),s['unit'],device='cuda',dtype=torch.int64))
            coeff,exponent=sf.exact_coefficients(step,top,torch.ones_like(top))
            shifts=torch.zeros_like(bins);maximum=0;multiplier=s['mass']
            values=s['counts'].cpu().numpy().astype(np.float64)*signs.cpu().numpy()
            reference=(values@wd.T)*(s['mass'].cpu().numpy()*2.**s['unit']/s['denominator'])[:,None]
        else:
            coeff,exponent=sf.exact_coefficients(step,tops[:,0],torch.ones_like(tops[:,0]))
            shifts=2*bins;maximum=6;multiplier=s['compensation']
            values=(s['counts'].double()*signs*xscale.double()).cpu().numpy()
            reference=(values@wd.T)*(s['compensation']/s['denominator'])
        record,pointer,_=compact(s['counts'],signs,shifts)
        acc=multiply_checked(project(bank,record,pointer,coeff,maximum),multiplier)
        result=sf.finish_fp32(acc,exponent,s['denominator'],maximum).cpu().numpy()
        if not np.array_equal(result.view(np.uint32),reference.astype(np.float32).view(np.uint32)):
            raise AssertionError('independent restoration mismatch: '+case['id'])
        checks.append(dict(case=case['id'],integer_mass_correct=True,
                           selected_counted_dot_and_RNE24_bitwise=True))
    value=dict(status='completed',scope='independent_small_dyadic_GPU_restore_oracle_not_model_PPL',
        tests=len(checks),checks=checks,source_manifest_sha256=hashlib.sha256((a.source/'EXECUTION_MANIFEST.json').read_bytes()).hexdigest(),
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes((json.dumps(value,indent=2)+'\n').encode())
    a.output.with_suffix('.sha256').write_bytes((hashlib.sha256(a.output.read_bytes()).hexdigest()+'\n').encode())
    print(json.dumps(value))


if __name__=='__main__':main()
