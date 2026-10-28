import types,unittest,torch
from .pot_weight import PoTWeightFFN,quantize_pot64,exact_pow2
from .test_core import setup

class PoT(unittest.TestCase):
    def test_tiled_scale_not_per_row(self):
        w=torch.zeros(128,128);w[:64,:64]=.1;w[:64,64:]=3.;w[64:,:64]=.01
        q,d,s=quantize_pot64(w)
        self.assertEqual(tuple(s.shape),(2,2));self.assertTrue((torch.frexp(s)[0]==.5).all())
        self.assertEqual(s[0,0].item(),2**-10);self.assertEqual(s[0,1].item(),2**-5)
        self.assertEqual(s[1,0].item(),2**-13);self.assertTrue((q[64:,64:]==0).all())
        self.assertTrue(torch.equal(d,q.float()*s.repeat_interleave(64,0).repeat_interleave(64,1)))

    def test_signed_endpoint_and_minimal_no_overflow_step(self):
        w=torch.full((64,64),127/1024);w[0,0]=-127/1024
        q,d,s=quantize_pot64(w);self.assertEqual(s.item(),1/1024);self.assertEqual(int(q.max()),127);self.assertEqual(int(q.min()),-127)
        self.assertTrue(torch.equal(d,w))
        w[1,1]=128/1024;q,d,s=quantize_pot64(w);self.assertEqual(s.item(),1/512)

    def test_Wd_restore_is_exact_shift_coeff(self):
        torch.manual_seed(19);o=types.SimpleNamespace(**{n:torch.nn.Linear(128,128,bias=False) for n in ('gate_proj','up_proj','down_proj')})
        m=PoTWeightFFN(o,0);m.g_top=torch.tensor([.25,4.]);m.u_top=torch.tensor([.5,2.]);m.freeze_down()
        c=m.coeff;self.assertTrue(((c>0)&((c&(c-1))==0)).all());self.assertEqual(m.coefficient_nmse,0.)
        self.assertTrue(m.weight_metrics['gu']['step_is_pot']);self.assertTrue(m.weight_metrics['down']['step_is_pot'])

    def test_shared_output_and_mean_are_finite(self):
        torch.manual_seed(206);o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False) for n in ('gate_proj','up_proj','down_proj')})
        m=PoTWeightFFN(o,0);setup(m,'all_max');x=torch.randn(2,64)*.1
        for mean in (False,True):
            m.nonlinear_mean=mean;y=m(x);self.assertTrue(torch.isfinite(y).all())
            for d in m.shared_report()['stages'].values():self.assertEqual(d['mixed_scale_groups'],0)

@unittest.skipUnless(torch.cuda.is_available(),'CUDA required')
class CUDAPoT(unittest.TestCase):
    def test_cuda_exact_negative_exponents_and_multirow_coefficients(self):
        ex=torch.arange(-100,101,device='cuda')
        self.assertTrue(torch.equal(exact_pow2(ex).cpu(),torch.tensor([2.**e for e in range(-100,101)],dtype=torch.float64)))
        o=types.SimpleNamespace(**{n:torch.nn.Linear(128,128,bias=False,device='cuda') for n in ('gate_proj','up_proj','down_proj')})
        m=PoTWeightFFN(o,0);m.g_top=torch.tensor([1.,.25],device='cuda');m.u_top=torch.tensor([2.,.5],device='cuda');m.freeze_down()
        expected=m.down_tile_lsb.double()*(m.g_top.double()*m.u_top.double())[None,:]
        restored=m.coeff.double()*exact_pow2(m.output_exp[:,None]-16)
        self.assertTrue(torch.equal(expected,restored))

    def test_cuda_weight_codes_and_shared_forward(self):
        torch.manual_seed(27)
        w=torch.randn(128,128)
        cpu=quantize_pot64(w);gpu=quantize_pot64(w.cuda())
        for a,b in zip(cpu,gpu):self.assertTrue(torch.equal(a,b.cpu()))
        o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False,device='cuda') for n in ('gate_proj','up_proj','down_proj')})
        m=PoTWeightFFN(o,0);setup(m,'all_max');y=m(torch.randn(2,64,device='cuda')*.1)
        self.assertTrue(torch.isfinite(y).all())
        for d in m.shared_report()['stages'].values():self.assertEqual(d['mixed_scale_groups'],0)

if __name__=='__main__':unittest.main()
