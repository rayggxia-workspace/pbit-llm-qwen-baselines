import types,unittest,torch
from torch.nn import functional as F
from .group_sweep_core import inherited_catalog,encode_grouped,GroupSweepFFN
from .recal_core import encode_catalog,RecalibratedFFN,catalog_accumulate
from .pot_weight import exact_pow2
from .test_core import setup


class GroupSweep(unittest.TestCase):
    def make(self,device='cpu'):
        torch.manual_seed(602)
        o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False,device=device) for n in ('gate_proj','up_proj','down_proj')})
        a=GroupSweepFFN(o,0);setup(a,'all_max');a.reset_gate('max')
        return o,a

    def test_eight_levels_nested_no_larger_ceiling(self):
        a=torch.tensor([[-7,-5,-3,0],[-4,-3,-1,2]])
        for g in (16,32,64):
            b=inherited_catalog(a,g,8).reshape(2,64//g,8)
            self.assertTrue((b[:,:,1:]-b[:,:,:-1]==1).all())
            self.assertTrue((b[:,:,-1]==a[:,-1,None]).all())
            self.assertTrue((a[:,None,:,None]==b[:,:,None,:]).any(-1).all())

    def test_parent_catalog_replicates_to_subgroups(self):
        a=torch.tensor([[-5,-3,-1,1],[-6,-4,-2,0]])
        for g in (16,32,64):
            b=inherited_catalog(a,g,4)
            self.assertTrue(torch.equal(b,a.repeat_interleave(64//g,0)))

    def test_group64_matches_frozen_encoder(self):
        torch.manual_seed(17);x=torch.randn(2,3,128)
        a=torch.tensor([[-5,-3,-1,1],[-4,-2,0,2]])
        for v,w in zip(encode_catalog(x,a),encode_grouped(x,a,64)):self.assertTrue(torch.equal(v,w))

    def test_shared16_and32_do_not_share_with_neighbor(self):
        a=torch.tensor([[-4,-2,0,2]])
        x=torch.cat([torch.full((1,16),v) for v in (.04,.2,.8,3.)],-1)
        q,s,e,h,b=encode_grouped(x,inherited_catalog(a,16,4),16)
        self.assertEqual(e[0,::16].tolist(),[-4,-2,0,2])
        for g in (16,32,64):
            z=encode_grouped(x,inherited_catalog(a,g,4),g)
            self.assertTrue((z[2].reshape(-1,g).amax(-1)==z[2].reshape(-1,g).amin(-1)).all())
            self.assertTrue(((z[0]>=0)&(z[0]<=255)).all())

    def test_zero_negative_endpoint_and_saturation(self):
        a=inherited_catalog(torch.tensor([[-4,-2,0,2]]),16,8)
        x=torch.zeros(2,64);x[0,:16]=-4;x[0,16:32]=5
        q,s,e,h,b=encode_grouped(x,a,16)
        self.assertTrue((q[1]==0).all());self.assertTrue((s[1]==0).all())
        self.assertTrue((q[0,:32]==255).all());self.assertTrue((s[0,:16]==-1).all())

    def test_invalid_catalog_or_group_rejected(self):
        with self.assertRaises(ValueError):inherited_catalog([[0,1,2,8]],64,8)
        with self.assertRaises(ValueError):inherited_catalog([[0,1,2,3]],8,4)
        with self.assertRaises(ValueError):encode_grouped(torch.zeros(1,64),torch.tensor([[0,1,1,2]]),64)

    def test_full_group64_four_replays_parent_and_x_unchanged(self):
        o,a=self.make();b=RecalibratedFFN(o,0);setup(b,'all_max');b.reset_gate('max')
        g=[[-7,-5,-3,-1]];u=[[-6,-4,-2,0]]
        b.install_catalog(g,u);a.install_sweep(g,u,64,4)
        x=torch.randn(2,64)*.1
        self.assertTrue(torch.equal(a.x_scales,b.x_scales))
        self.assertTrue(torch.equal(a.gu_codes,b.gu_codes));self.assertTrue(torch.equal(a.down_codes,b.down_codes))
        self.assertTrue(torch.equal(a(x),b(x)))
        r=a.shared_report();self.assertEqual(r['input_shared_group'],64)
        self.assertEqual(r['stages']['g']['mixed_scale_groups'],0)

    def test_all_shapes_output_finite_and_weights_immutable(self):
        _,a=self.make();g=[[-7,-5,-3,-1]];u=[[-6,-4,-2,0]]
        weights={n:getattr(a,n).clone() for n in ('gu_codes','down_codes','gu_decoded','down_decoded','x_scales')}
        for group in (64,32,16):
            for count in (4,8):
                a.install_sweep(g,u,group,count);a.reset_sweep_stats()
                y=a(torch.randn(3,64)*.1);self.assertTrue(torch.isfinite(y).all())
                report=a.shared_report();self.assertEqual(report['stages']['g']['shared_group_size'],group)
                self.assertEqual(report['stages']['u']['mixed_scale_groups'],0)
                self.assertEqual(len(report['stages']['g']['scale_hist']),count)
                for name,w in weights.items():self.assertTrue(torch.equal(getattr(a,name),w))

    def test_mean_nl_matches_direct_decoded_readout(self):
        _,a=self.make();torch.manual_seed(8)
        g=torch.randn(2,64)*.2;u=torch.randn(2,64)*.3
        a._stage=lambda *args:torch.cat((g,u),-1)
        from .independent_gate import original_g_field
        for group in (64,32,16):
            for count in (4,8):
                a.install_sweep([[-7,-5,-3,-1]],[[-6,-4,-2,0]],group,count)
                gc,gs,ge,_,_=encode_grouped(g,a.g_levels,group,a.g_carrier)
                uc,us,ue,_,_=encode_grouped(u,a.u_levels,group,a.u_carrier)
                z=(gs*gc.double()*exact_pow2(ge)/256)*(us*uc.double()*exact_pow2(ue)/256)*(a.lut[original_g_field(g)+128].double()/256)
                ref=F.linear(z.float(),a.down_decoded)
                a.nonlinear_mean=True;actual=a(torch.zeros_like(g))
                self.assertTrue(torch.equal(actual,ref))


@unittest.skipUnless(torch.cuda.is_available(),'CUDA required')
class CUDAGroupSweep(unittest.TestCase):
    def test_encode_cpu_cuda_and_full_forward(self):
        torch.manual_seed(91);x=torch.randn(2,64)*.1
        for group in (64,32,16):
            for count in (4,8):
                levels=inherited_catalog([[-7,-5,-3,-1]],group,count)
                for a,b in zip(encode_grouped(x,levels,group),encode_grouped(x.cuda(),levels.cuda(),group)):
                    self.assertTrue(torch.equal(a,b.cpu()))
        _,m=GroupSweep().make('cuda');m.install_sweep([[-7,-5,-3,-1]],[[-6,-4,-2,0]],16,8)
        self.assertTrue(torch.isfinite(m(x.cuda())).all())


if __name__=='__main__':unittest.main()
