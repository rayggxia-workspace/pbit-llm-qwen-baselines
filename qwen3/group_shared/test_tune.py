import ast,pathlib,types,unittest,torch
from .tune_core import TunedFFN,encode_threshold,risk_components,fit_policies
from .recal_core import encode_catalog,RecalibratedFFN
from .test_core import setup
from qwen3.and_direct.short_core import joint_moments

class Tune(unittest.TestCase):
    def make(self,device='cpu'):
        torch.manual_seed(208)
        o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False,device=device) for n in ('gate_proj','up_proj','down_proj')})
        m=TunedFFN(o,0);setup(m,'all_max');m.reset_gate('max');return o,m

    def test_zero_threshold_replays_catalog_encoder(self):
        torch.manual_seed(14);x=torch.randn(4,128);levels=torch.tensor([[-4,-2,-1,0],[-5,-3,0,1]]);delta=torch.zeros(2,dtype=torch.long);carrier=torch.tensor([1,2])
        for a,b in zip(encode_threshold(x,levels,delta,carrier),encode_catalog(x,levels,None,carrier)):self.assertTrue(torch.equal(a,b))

    def test_threshold_changes_selection_not_scale_values(self):
        x=torch.full((1,64),.3);levels=torch.tensor([[-3,-2,-1,0]]);carrier=torch.tensor([0])
        expected={-1:0,0:-1,1:-2}
        for d,e in expected.items():
            q,s,p,h,b=encode_threshold(x,levels,torch.tensor([d]),carrier)
            self.assertTrue((p==e).all());self.assertTrue((p.reshape(-1,64).amax(-1)==p.reshape(-1,64).amin(-1)).all())

    def test_zero_threshold_entire_FFN_replay(self):
        o,m=self.make();a=RecalibratedFFN(o,0);setup(a,'all_max');a.reset_gate('max')
        g=[[-4,-3,-2,-1]];u=[[-6,-4,-2,0]];m.install_tuned(g,u,[0],[0]);a.install_catalog(g,u)
        x=torch.randn(2,64)*.1;self.assertTrue(torch.equal(m(x),a(x)))

    def test_gram_risk_matches_explicit_local_output(self):
        torch.manual_seed(22);g=torch.randn(3,2,64)*.3;u=torch.randn_like(g);h=torch.randint(0,257,g.shape);w=torch.randn(2,64,7,dtype=torch.float64);gram=torch.bmm(w,w.transpose(1,2));norm=gram.diagonal(dim1=-2,dim2=-1)
        sg=torch.ones(1,2,1);su=torch.ones_like(sg);d,b,v=risk_components(g,u,h,sg,su,norm,gram)
        a,c=joint_moments(((g.abs()*256).round().clamp(0,255).long(),h,(u.abs()*256).round().clamp(0,255).long()),128)
        delta=g.sign()*u.sign()*a/128-g.double()*u.double()*h/256
        actual=torch.bmm(delta.permute(1,0,2),w).square().sum(-1).T
        self.assertTrue(torch.allclose(b,actual,rtol=1e-12,atol=1e-12));self.assertTrue(torch.allclose(v,(c/128**2*norm).sum(-1)))

    def test_fitting_ignores_validation_cost(self):
        torch.manual_seed(17);c=torch.rand(5,2,10,10,dtype=torch.float64);g=torch.randint(-1,11,(5,2));u=torch.randint(-1,11,(5,2))
        a=fit_policies(c,g,u,3,True);other=c.clone();other[3:]*=1e6;b=fit_policies(other,g,u,3,True)
        for x,y in zip(a,b):self.assertTrue(torch.equal(x,y))

    def test_empty_risk_falls_back_dense_zero_delta(self):
        g=torch.zeros(4,1,dtype=torch.long);a,b,c,d=fit_policies(torch.zeros(4,1,10,10),g,g,3,True)
        self.assertEqual(a.tolist(),[[5,6,7,8]]);self.assertEqual(c.tolist(),[0]);self.assertEqual(d.tolist(),[0])

    def test_complete_local_calibration(self):
        from .tune_run import local_tune,SCHEMES
        torch.manual_seed(25);g=torch.randn(5,1,64);u=torch.randn_like(g);w=torch.randn(1,64,8,dtype=torch.float64);gram=torch.bmm(w,w.transpose(1,2));norm=gram.diagonal(dim1=-2,dim2=-1)
        tables=local_tune(g,u,norm,gram,3);self.assertEqual(set(tables),set(SCHEMES))
        for e in tables.values():
            for k in ('g','u'):self.assertTrue((torch.tensor(e[k])[:,1:]>torch.tensor(e[k])[:,:-1]).all())
            if not e['thresholds_tuned']:self.assertEqual(e['g_delta'],[0]);self.assertEqual(e['u_delta'],[0])

    def test_main_module_aliases_not_shadowed(self):
        root=ast.parse(pathlib.Path(__file__).with_name('tune_run.py').read_text());aliases={a.asname or a.name.split('.')[0] for n in root.body if isinstance(n,ast.Import) for a in n.names}
        main=next(n for n in root.body if isinstance(n,ast.FunctionDef) and n.name=='main');assigned={n.id for n in ast.walk(main) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)};self.assertFalse(aliases&assigned)

@unittest.skipUnless(torch.cuda.is_available(),'CUDA required')
class CUDATune(unittest.TestCase):
    def test_cuda_encoding_and_forward(self):
        torch.manual_seed(17);x=torch.randn(3,128);levels=torch.tensor([[-4,-2,-1,0],[-5,-3,0,1]]);d=torch.tensor([1,-1]);carrier=torch.tensor([1,2])
        for a,b in zip(encode_threshold(x,levels,d,carrier),encode_threshold(x.cuda(),levels.cuda(),d.cuda(),carrier.cuda())):self.assertTrue(torch.equal(a,b.cpu()))
        o,m=Tune().make('cuda');m.install_tuned([[-4,-3,-2,-1]],[[-4,-3,-2,-1]],[1],[-1]);self.assertTrue(torch.isfinite(m(torch.randn(2,64,device='cuda')*.1)).all())

if __name__=='__main__':unittest.main()
