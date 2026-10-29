import types,unittest,torch
from qwen3.group_shared.core import VARIANTS,group_choice,encode_x,encode_nl,Group64FFN
from qwen3.dual_gu.core import DualGUFFN
from qwen3.and_direct.multiscale_core import sigmoid_field


def setup(module,variant=None,method='fixed',seed=0):
    module.mode='sampled';module.cycles=64;module.strata=64
    module.x_scales=torch.tensor([[1.,.25,.0625,.015625]],device=module.gu_codes.device)
    module.rng_input.manual_seed(700001+1000*seed)
    module.set_spec(8,8,8);module.freeze_down();module.reset_short('lower_half','joint32',128,seed)
    module.reset_gu(method,64 if method=='fixed' else 256,seed)
    if variant is not None:module.reset_shared(variant)


class Encoding(unittest.TestCase):
    def test_group_selection_and_endpoint(self):
        v=torch.zeros(2,128);v[0,0]=.5;v[0,64]=.02
        table=torch.tensor([[1.,.25,.0625,.015625]]*2)
        x=encode_x(v,table,True,0)
        self.assertTrue(torch.equal(x['scale'][0,:64],torch.ones(64)))
        self.assertTrue(torch.equal(x['scale'][0,64:],torch.full((64,),.0625)))
        self.assertTrue(torch.equal(x['scale'][1],torch.full((128,),.015625)))
        self.assertTrue(torch.equal(x['decoded'][1],torch.zeros(128)))
        y=encode_x(torch.ones(1,64),table[:1],True,0)
        self.assertTrue(y['full_one'].all());self.assertTrue((y['probability']==1).all())

    def test_trim_is_count_not_new_scale(self):
        table=torch.tensor([[4.,1.,.25,.0625]])
        x=torch.full((1,64),.2);x[0,0]=3.
        s,_=group_choice(x,table,0);self.assertTrue((s==4).all())
        s,_=group_choice(x,table,1);self.assertTrue((s==.25).all())
        x[0,1]=3.;s,_=group_choice(x,table,1);self.assertTrue((s==4).all())
        s,_=group_choice(x,table,4);self.assertTrue((s==.25).all())

    def test_no_hidden_new_scale_or_lane_index(self):
        torch.manual_seed(4);v=torch.randn(5,128)
        table=torch.tensor([[4.,1.,.25,.0625],[8.,2.,.5,.125]])
        for allow in (0,1,4):
            s,b=group_choice(v,table,allow)
            self.assertTrue((b.reshape(-1,64).amax(-1)==b.reshape(-1,64).amin(-1)).all())
            for g in range(2):self.assertTrue(torch.isin(s[:,g*64:(g+1)*64],table[g]).all())

    def test_uniform_group_replays_lane_encoder(self):
        table=torch.tensor([[4.,1.,.25,.0625]])
        for val in (-4.,-1.,-.17,0.,.0625,.26,4.,5.):
            v=torch.full((3,64),val)
            a=encode_x(v,table,False,0);b=encode_x(v,table,True,0)
            for k in a:self.assertTrue(torch.equal(a[k],b[k]),k)

    def test_groupmax_no_extra_clipping(self):
        torch.manual_seed(12);v=torch.randn(7,128)
        table=torch.tensor([[2.,.5,.125,.03125]]*2)
        a=encode_x(v,table,False,0);b=encode_x(v,table,True,0)
        self.assertTrue(torch.equal(v.abs()>a['scale'],v.abs()>b['scale']))

    def test_nonlinear_true_field_and_different_g_u(self):
        top=torch.tensor([8.,2.]);v=torch.linspace(-5,5,128).reshape(1,128)
        offsets=(1,3,5,7)
        for shared in (False,True):
            c,s,e,h=encode_nl(v,top,offsets,shared,0)
            decoded=torch.ldexp(c.double()*s/256,e)
            expected=(decoded/.125).round().clamp(-128,127).long()
            self.assertTrue(torch.equal(sigmoid_field(c,s,e),expected))
            if shared:self.assertTrue((h.reshape(-1,64).amax(-1)==h.reshape(-1,64).amin(-1)).all())

    def test_bad_group_or_policy(self):
        with self.assertRaises(ValueError):group_choice(torch.zeros(1,65),torch.ones(1,4))
        with self.assertRaises(ValueError):group_choice(torch.zeros(1,64),torch.ones(1,4),2)


class Forward(unittest.TestCase):
    def test_lane_replays_old_full_FFN_fixed_and_dual(self):
        torch.manual_seed(6)
        original=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False) for n in ('gate_proj','up_proj','down_proj')})
        x=torch.randn(2,64)*.1
        for method in ('fixed','joint'):
            a=DualGUFFN(original,0);b=Group64FFN(original,0)
            setup(a,method=method);setup(b,'lane',method)
            self.assertTrue(torch.equal(a(x),b(x)),method)

    def test_all_shared_forward_and_immutable_Wd(self):
        torch.manual_seed(8)
        original=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False) for n in ('gate_proj','up_proj','down_proj')})
        m=Group64FFN(original,0);x=torch.randn(3,64)*.1
        for variant in VARIANTS:
            setup(m,variant)
            saved=[(getattr(m,n),getattr(m,n).data_ptr(),getattr(m,n)._version) for n in ('down_codes','coeff','output_exp')]
            y=m(x);self.assertTrue(torch.isfinite(y).all());r=m.shared_report()
            self.assertEqual(y.shape,x.shape)
            for n,z in r['stages'].items():
                if z['shared_group64']:self.assertEqual(z['mixed_scale_groups'],0)
            self.assertTrue(all(a.data_ptr()==p and a._version==v for a,p,v in saved))


@unittest.skipUnless(torch.cuda.is_available(),'Slurm CUDA check')
class CUDA(unittest.TestCase):
    def test_gpu_group_boundaries_and_field(self):
        v=torch.linspace(-4,4,128,device='cuda').reshape(1,128)
        table=torch.tensor([[4.,1.,.25,.0625]]*2,device='cuda')
        a=encode_x(v,table,True,1);b=encode_x(v.cpu(),table.cpu(),True,1)
        for k in a:self.assertTrue(torch.equal(a[k].cpu(),b[k]),k)


if __name__=='__main__':unittest.main()
