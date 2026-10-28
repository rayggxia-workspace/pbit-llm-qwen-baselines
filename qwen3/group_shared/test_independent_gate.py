import types,unittest,torch
from torch.nn import functional as F
from .independent_gate import IndependentGateFFN,original_g_field
from .pot_weight import PoTWeightFFN
from .test_core import setup
from .core import encode_nl
from qwen3.and_direct.multiscale_core import sigmoid_field

class Gate(unittest.TestCase):
    def make(self,device='cpu'):
        torch.manual_seed(127)
        o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False,device=device) for n in ('gate_proj','up_proj','down_proj')})
        m=IndependentGateFFN(o,0);setup(m,'all_max');m.reset_gate('max');return o,m

    def test_signed8_rounding_and_saturation(self):
        x=torch.tensor([-40.,-16.,-8.,-.1875,-.0625,0.,.0625,.1875,15.875,40.])
        self.assertEqual(original_g_field(x).tolist(),[-128,-128,-64,-2,0,0,0,2,127,127])

    def test_gate_independent_of_amplitude_scale_and_clip(self):
        v=torch.full((1,64),.01);v[0,0]=-8.;normal=original_g_field(v)
        for top in (.5,2.,16.,64.):
            c,s,e,h=encode_nl(v,torch.tensor([top]),(1,3,5,7),True,1)
            self.assertTrue(torch.equal(normal,original_g_field(v)))
            self.assertEqual(int(normal[0,0]),-64)
            if top==2.:self.assertNotEqual(int(sigmoid_field(c,s,e)[0,0]),-64)

    def test_g_u_scales_and_clipping_are_separate(self):
        g=torch.full((1,64),.01);g[0,0]=1.;u=torch.full((1,64),.01);u[0,0]=.2
        ge=encode_nl(g,torch.tensor([4.]),(1,3,5,7),True,1)[2]
        ue=encode_nl(u,torch.tensor([8.]),(1,3,5,7),True,0)[2]
        self.assertEqual(int(ge.max()),int(ge.min()));self.assertEqual(int(ue.max()),int(ue.min()));self.assertNotEqual(int(ge[0,0]),int(ue[0,0]))

    def test_old_coupled_full_FFN_replay(self):
        o,a=self.make();b=PoTWeightFFN(o,0);setup(b,'all_max');a.reset_gate('max','old_coupled')
        x=torch.randn(2,64)*.2
        self.assertTrue(torch.equal(a(x),b(x)))

    def test_mean_matches_explicit_decoded_product(self):
        o,m=self.make();m.nonlinear_mean=True;m.reset_gate('both_trim1');x=torch.randn(2,64)*.1
        m.rng_input.manual_seed(33);g,u=m._stage(x,'x','gu',m.rng_input).chunk(2,-1)
        gc,gs,ge,_=encode_nl(g,m.g_top,m.offsets,True,1);uc,us,ue,_=encode_nl(u,m.u_top,m.offsets,True,1)
        h=m.lut[original_g_field(g)+128].double()/256
        gq=torch.ldexp(gc.double()*gs/256,ge);uq=torch.ldexp(uc.double()*us/256,ue)
        ref=F.linear((gq*h*uq).float(),m.down_decoded).to(x.dtype)
        m.rng_input.manual_seed(33);y=m(x);self.assertTrue(torch.allclose(y,ref,atol=1e-7,rtol=1e-5))

    def test_finite_all_policies_keep_group_scales(self):
        for policy in ('max','g_trim1','u_trim1','both_trim1','both_trim4'):
            o,m=self.make();m.reset_gate(policy);y=m(torch.randn(2,64)*.1);self.assertTrue(torch.isfinite(y).all())
            for d in m.shared_report()['stages'].values():self.assertEqual(d['mixed_scale_groups'],0)

@unittest.skipUnless(torch.cuda.is_available(),'CUDA required')
class CUDAGate(unittest.TestCase):
    def test_real_field_and_finite_forward(self):
        v=torch.linspace(-30,30,256);self.assertTrue(torch.equal(original_g_field(v),original_g_field(v.cuda()).cpu()))
        o,m=Gate().make('cuda');m.reset_gate('both_trim1');y=m(torch.randn(2,64,device='cuda')*.1)
        self.assertTrue(torch.isfinite(y).all());self.assertEqual(m.shared_report()['gate_mode'],'original_g')

if __name__=='__main__':unittest.main()
