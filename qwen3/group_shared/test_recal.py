import types,unittest,torch
from .recal_core import RecalibratedFFN,encode_catalog,output_risk,fit_catalogs,ceil_exp
from .independent_gate import IndependentGateFFN
from .test_core import setup
from .pot_weight import exact_pow2
from qwen3.and_direct.short_core import joint_moments

class Recal(unittest.TestCase):
    def make(self,device='cpu'):
        torch.manual_seed(207)
        o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False,device=device) for n in ('gate_proj','up_proj','down_proj')})
        m=RecalibratedFFN(o,0);setup(m,'all_max');m.reset_gate('max');return o,m

    def test_four_scales_group_shared_and_boundary(self):
        x=torch.zeros(2,128);x[0,0]=.3;x[0,64]=2.;levels=torch.tensor([[-3,-2,-1,0],[-2,-1,0,1]])
        q,s,e,h,b=encode_catalog(x,levels)
        self.assertEqual(int(e[0,0]),-1);self.assertEqual(int(e[0,64]),1)
        self.assertTrue((e.reshape(-1,64).amax(-1)==e.reshape(-1,64).amin(-1)).all());self.assertTrue((q[1]==0).all())

    def test_active_zero_gate_cannot_contribute(self):
        x=torch.full((1,64),.1);x[0,0]=100.;mask=torch.ones_like(x,dtype=torch.bool);mask[0,0]=False;levels=torch.tensor([[-3,-2,-1,0]])
        a=encode_catalog(x,levels);b=encode_catalog(x,levels,mask)
        self.assertEqual(int(a[2][0,0]),0);self.assertEqual(int(b[2][0,0]),-3)
        h=torch.full_like(b[0],128);h[0,0]=0
        self.assertEqual(int((b[0]*h)[0,0]),0)

    def test_old_table_full_FFN_exact_replay(self):
        o,m=self.make();n=IndependentGateFFN(o,0);setup(n,'all_max');n.reset_gate('max')
        m.install_catalog([[-7,-5,-3,-1]],[[-7,-5,-3,-1]])
        x=torch.randn(3,64)*.1;self.assertTrue(torch.equal(m(x),n(x)))

    def test_exact_finite_risk_formula(self):
        g=torch.tensor([[[.3,-.7]]]);u=torch.tensor([[[.4,.8]]]);h=torch.tensor([[[192,64]]]);sg=torch.ones(1,1,1);su=torch.ones_like(sg);w=torch.tensor([[2.,3.]])
        m,v=joint_moments(((g.abs()*256).round().long(),h,(u.abs()*256).round().long()),128)
        ref=(((g.sign()*u.sign()*m/128-g.double()*u.double()*h/256).square()+v/(128**2))*w).sum(-1)
        self.assertTrue(torch.equal(output_risk(g,u,h,sg,su,w),ref))

    def test_fit_never_reads_validation_cost(self):
        torch.manual_seed(9);cost=torch.rand(9,3,8,8,dtype=torch.float64);rg=torch.randint(0,8,(9,3));ru=torch.randint(0,8,(9,3))
        a=fit_catalogs(cost,rg,ru,6);other=cost.clone();other[6:]=torch.rand_like(other[6:])*1e5;b=fit_catalogs(other,rg,ru,6)
        for x,y in zip(a,b):self.assertTrue(torch.equal(x,y));self.assertTrue((x[:,1:]>x[:,:-1]).all())

    def test_zero_risk_dense_fallback_and_bad_catalog(self):
        a,b=fit_catalogs(torch.zeros(4,2,8,8),torch.zeros(4,2,dtype=torch.long),torch.zeros(4,2,dtype=torch.long),3)
        self.assertTrue((a==torch.tensor([3,4,5,6])).all())
        with self.assertRaises(ValueError):encode_catalog(torch.zeros(1,64),torch.tensor([[0,1,1,2]]))

    def test_normal_g_sigmoid_and_finite_catalog(self):
        o,m=self.make();m.install_catalog([[-4,-3,-2,-1]],[[-6,-4,-2,0]],True)
        y=m(torch.randn(2,64)*.1);self.assertTrue(torch.isfinite(y).all());r=m.shared_report()
        self.assertTrue(r['catalog_active_gate_mask']);self.assertEqual(r['stages']['g']['mixed_scale_groups'],0)

@unittest.skipUnless(torch.cuda.is_available(),'CUDA required')
class CUDARecal(unittest.TestCase):
    def test_cuda_encoding_and_forward(self):
        torch.manual_seed(99);x=torch.randn(2,128);a=torch.tensor([[-4,-2,-1,1],[-2,-1,1,2]])
        for p,q in zip(encode_catalog(x,a),encode_catalog(x.cuda(),a.cuda())):self.assertTrue(torch.equal(p,q.cpu()))
        o,m=Recal().make('cuda');m.install_catalog([[-4,-3,-2,-1]],[[-4,-3,-2,-1]])
        self.assertTrue(torch.isfinite(m(torch.randn(2,64,device='cuda')*.1)).all())

if __name__=='__main__':unittest.main()
