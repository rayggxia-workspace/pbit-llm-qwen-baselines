import types
import unittest
import torch
from torch.nn import functional as F
from .core import UnifiedGUFFN, amplitude_threshold, raw_g_code, thresholds_from_raw, field_from_raw
from qwen3.group_shared.group_sweep_core import GroupSweepFFN, encode_grouped
from qwen3.group_shared.test_core import setup
from qwen3.and_direct.multiscale_core import sigmoid_field
from qwen3.group_shared.independent_gate import original_g_field


def make(cls=UnifiedGUFFN,device='cpu'):
    torch.manual_seed(602)
    o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False,device=device)
                              for n in ('gate_proj','up_proj','down_proj')})
    a=cls(o,0);setup(a,'all_max');a.reset_gate('max')
    a.install_sweep([[-7,-5,-3,-1]],[[-6,-4,-2,0]],64,4)
    return o,a


class CodecTests(unittest.TestCase):
    def test_control_replays_frozen_parent_including_rng(self):
        for seed in (0,1,2):
            o,a=make();b=GroupSweepFFN(o,0);setup(b,'all_max',seed=seed);b.reset_gate('max')
            b.install_sweep([[-7,-5,-3,-1]],[[-6,-4,-2,0]],64,4)
            setup(a,'all_max',seed=seed);a.reset_gate('max');a.set_codec('independent9')
            x=torch.randn(3,64)*.1
            self.assertTrue(torch.equal(a(x),b(x)))
            for name in ('rng_input','rng_and','rng_weight'):
                self.assertTrue(torch.equal(getattr(a,name).get_state(),getattr(b,name).get_state()))

    def test_shared9_keeps_every_amplitude_code_and_group(self):
        g=torch.linspace(-2,2,512).reshape(8,64)
        a=encode_grouped(g,torch.tensor([[-6,-4,-2,0]]),64)
        self.assertTrue(torch.equal(amplitude_threshold(g,a,9),a[0]))
        q=amplitude_threshold(g,a,8)
        self.assertTrue(((q%2==0)&(q>=0)&(q<=254)).all())
        oracle=(torch.ldexp(g.abs(),-a[2])*128).round().clamp(0,127).long()*2
        self.assertTrue(torch.equal(q,oracle))

    def test_direct_rounding_avoids_double_rounding(self):
        g=torch.full((1,64),2.75/256)
        a=encode_grouped(g,torch.tensor([[0,1,2,3]]),64)
        self.assertEqual(int(a[0][0,0]),3)
        self.assertEqual(int(amplitude_threshold(g,a,8)[0,0]),2)
        self.assertEqual(int((a[0].double()/2).round()[0,0])*2,4)

    def test_all_codes_signs_exponents_field_against_decoded_oracle(self):
        for bits in (8,9):
            c=torch.arange(1<<(bits-1)).repeat(2,33,1).long()<<(9-bits)
            s=torch.tensor([-1,1])[:,None,None].expand_as(c)
            e=torch.arange(-16,17)[None,:,None].expand_as(c)
            decoded=torch.ldexp(c.double()*s/256,e)
            expected=(decoded*8).round().clamp(-128,127).long()
            self.assertTrue(torch.equal(sigmoid_field(c,s,e),expected))

    def test_same_code_respects_scale_and_sign(self):
        c=torch.tensor([192,192,192]);s=torch.tensor([1,1,-1]);e=torch.tensor([2,3,2])
        self.assertEqual(sigmoid_field(c,s,e).tolist(),[24,48,-24])

    def test_mean_readout_uses_exactly_the_selected_stored_code(self):
        _,a=make();torch.manual_seed(8)
        g=torch.randn(2,64)*.2;u=torch.randn(2,64)*.3
        a._stage=lambda *args:torch.cat((g,u),-1)
        aa=encode_grouped(g,a.g_levels,64,a.g_carrier)
        bb=encode_grouped(u,a.u_levels,64,a.u_carrier)
        saved={n:getattr(a,n).clone() for n in ('gu_codes','down_codes','g_levels','u_levels')}
        for mode,bits in (('shared9',9),('shared8',8)):
            a.set_codec(mode);a.nonlinear_mean=True
            cg=amplitude_threshold(g,aa,bits);cu=amplitude_threshold(u,bb,bits)
            h=a.lut[sigmoid_field(cg,aa[1],aa[2])+128].long()
            z=torch.ldexp((aa[1]*bb[1]*cg*h*cu).double()/256**3,aa[2]+bb[2])
            self.assertTrue(torch.equal(a(torch.zeros_like(g)),F.linear(z.float(),a.down_decoded)))
            for n,v in saved.items():self.assertTrue(torch.equal(v,getattr(a,n)))

    def test_deterministic_joint_cell_oracle_for_both_widths(self):
        for mode in ('shared9','shared8'):
            _,a=make();a.install_sweep([[-10,-8,-6,-4]],[[-10,-8,-6,-4]],64,4)
            a.set_codec(mode);g=torch.full((1,64),2.**-12);u=torch.full_like(g,2.**-11)
            a._stage=lambda *args:torch.cat((g,u),-1)
            # g threshold64,h128,u128:all boundaries are whole Cartesian cells.
            # The real model boundary is BF16. Sampled finish_bf16 always
            # rounds there; a float32 input would leave mean output unrounded.
            x=torch.zeros_like(g,dtype=torch.bfloat16)
            a.nonlinear_mean=True;expected=a(x)
            a.nonlinear_mean=False;self.assertTrue(torch.equal(a(x),expected))

    def test_zero_clipping_and_ties(self):
        g=torch.tensor([0.,-2.,2.,.5/128,1.5/128]+[0.]*59).reshape(1,64)
        a=encode_grouped(g,torch.tensor([[-6,-4,-2,0]]),64)
        q=amplitude_threshold(g,a,8)
        self.assertEqual(q[0,:5].tolist(),[0,254,254,0,4])
        self.assertEqual(a[1][0,:3].tolist(),[0,-1,1])

    def test_raw8_preserves_original_sigmoid_field(self):
        g=torch.arange(-16384,16385,dtype=torch.float32)/512
        self.assertTrue(torch.equal(raw_g_code(g,8),original_g_field(g)))

    def test_raw_amplitude_integer_conversion_exhaustive(self):
        for bits in (8,9):
            limit=1<<(bits-1)
            q=torch.arange(-limit,limit)[None,:].expand(33,-1)
            e=torch.arange(-16,17)[:,None].expand_as(q)
            expected=torch.ldexp(q.abs().double(),8-(bits-5)-e).round().clamp(0,255).long()
            self.assertTrue(torch.equal(thresholds_from_raw(q,e,bits),expected))
            f=q if bits==8 else (q.double()/2).round().clamp(-128,127).long()
            self.assertTrue(torch.equal(field_from_raw(q,bits),f))

    def test_raw_mean_matches_literal_decoded_g_and_u(self):
        _,a=make();g=torch.linspace(-3,3,128).reshape(2,64)
        u=torch.linspace(.4,-.4,128).reshape_as(g)
        a._stage=lambda *args:torch.cat((g,u),-1)
        aa=encode_grouped(g,a.g_levels,64,a.g_carrier);bb=encode_grouped(u,a.u_levels,64,a.u_carrier)
        for mode,bits in (('raw9',9),('raw8',8)):
            q=raw_g_code(g,bits);cg=thresholds_from_raw(q,aa[2],bits)
            cu=amplitude_threshold(u,bb,bits)
            f=q if bits==8 else (q.double()/2).round().clamp(-128,127).long()
            h=a.lut[f+128].long()
            z=torch.ldexp((q.sign()*bb[1]*cg*h*cu).double()/256**3,aa[2]+bb[2])
            a.set_codec(mode);a.nonlinear_mean=True
            self.assertTrue(torch.equal(a(torch.zeros_like(g)),F.linear(z.float(),a.down_decoded)))


@unittest.skipUnless(torch.cuda.is_available(),'CUDA required')
class CUDAProof(unittest.TestCase):
    def test_cpu_cuda_codes_and_finite_gpu_forward(self):
        g=torch.linspace(-2,2,512).reshape(8,64);levels=torch.tensor([[-6,-4,-2,0]])
        cpu=encode_grouped(g,levels,64);gpu=encode_grouped(g.cuda(),levels.cuda(),64)
        for bits in (8,9):
            self.assertTrue(torch.equal(amplitude_threshold(g,cpu,bits),amplitude_threshold(g.cuda(),gpu,bits).cpu()))
        for mode in ('shared9','shared8','raw9','raw8'):
            _,a=make(device='cuda');a.set_codec(mode)
            self.assertTrue(torch.isfinite(a(torch.randn(2,64,device='cuda')*.1)).all())


if __name__=='__main__':unittest.main()
