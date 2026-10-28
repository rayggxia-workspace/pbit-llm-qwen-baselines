import types,unittest,torch
from qwen3.group_shared.mean_diagnostic import MeanGroupFFN
from qwen3.group_shared.test_core import setup
from qwen3.and_direct.short_core import ShortStreamFFN

class MeanDiagnostic(unittest.TestCase):
    def test_replays_upstream_conditional_mean(self):
        torch.manual_seed(206)
        o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False) for n in ('gate_proj','up_proj','down_proj')})
        a=ShortStreamFFN(o,0);b=MeanGroupFFN(o,0)
        # Upstream control has the same fixed-W GU64 then conditional NL mean.
        a.mode='sampled';a.cycles=64;a.strata=64;a.x_scales=torch.tensor([[1.,.25,.0625,.015625]])
        a.rng_input.manual_seed(700001);a.set_spec(8,8,8);a.freeze_down();a.reset_short('lower_half','mean',128,0)
        setup(b,'lane')
        x=torch.randn(3,64)*.1
        self.assertTrue(torch.equal(a(x),b(x)))

    def test_diagnostic_is_explicitly_not_finite_sampling(self):
        torch.manual_seed(7)
        o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False) for n in ('gate_proj','up_proj','down_proj')})
        b=MeanGroupFFN(o,0);setup(b,'all_max');y=b(torch.randn(2,64)*.1);r=b.shared_report()
        self.assertTrue(torch.isfinite(y).all());self.assertIsNone(r['nonlinear_T']);self.assertIsNone(r['zero_AND_count_fraction'])
        self.assertFalse(r['hardware_candidate'])

if __name__=='__main__':unittest.main()
