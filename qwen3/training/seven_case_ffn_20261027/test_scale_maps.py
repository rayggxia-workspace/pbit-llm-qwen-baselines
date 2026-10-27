import unittest
import torch
from torch import nn
from .scale_maps import make_scale_maps, attach_to_common_calibration
from qwen3.weight_quantization.pot64 import quantize
from qwen3.training.stochastic_nonlinear.core import Config,TrainableFFN,NoiseKey,noise_context


def model():
    result=nn.Module();result.model=nn.Module();result.model.layers=nn.ModuleList()
    for depth in range(2):
        layer=nn.Module();layer.mlp=nn.Module()
        for role,value in [('gate_proj',.015625),('up_proj',.125),('down_proj',.5)]:
            p=nn.Linear(64,64,bias=False)
            with torch.no_grad(): p.weight.fill_(value*2**depth)
            setattr(layer.mlp,role,p)
        result.model.layers.append(layer)
    return result


class TestScaleMaps(unittest.TestCase):
    def test_global_is_one_exponent_across_every_layer_and_role(self):
        maps=make_scale_maps(model(),sharing='all_ffn')
        values={x for layer in maps.values() for table in layer.values() for row in table for x in row}
        self.assertEqual(values,{-6})

    def test_roles_share_across_layers_not_across_roles(self):
        maps=make_scale_maps(model(),sharing='projection_role')
        self.assertEqual(maps['0'],maps['1'])
        self.assertEqual(maps['0'],dict(gu=[[-11],[-8]],down=[[-6]]))

    def test_tiles_retain_independent_exponents(self):
        maps=make_scale_maps(model())
        self.assertEqual(maps['0'],dict(gu=[[-12],[-9]],down=[[-7]]))
        self.assertEqual(maps['1'],dict(gu=[[-11],[-8]],down=[[-6]]))

    def test_width_change_holds_the_binary_fullscale_power_fixed(self):
        m=model();baseline=make_scale_maps(m)
        for bits in (6,10):
            maps=make_scale_maps(m,weight_bits=bits)
            for layer in baseline:
                for role in ('gu','down'):
                    before=torch.tensor(baseline[layer][role])+7
                    after=torch.tensor(maps[layer][role])+bits-1
                    self.assertTrue(torch.equal(before,after))

    def test_case_calibration_keeps_activation_tables_unchanged(self):
        original=dict(format='fixed-four-and-training-pot64-v2',weight_bits=8,
            layers={str(i):dict(x=[[4.,1.,.25,.0625]],g=[4.],u=[4.]) for i in range(2)})
        changed=attach_to_common_calibration(original,make_scale_maps(model(),6),6)
        self.assertEqual(changed['weight_bits'],6)
        for layer in original['layers']:
            for role in ('x','g','u'):
                self.assertEqual(original['layers'][layer][role],changed['layers'][layer][role])
        self.assertNotIn('weight_exponents',original['layers']['0'])

    def test_w10_integer_range_and_training_path(self):
        torch.manual_seed(18);torch.set_num_threads(1)
        torch.backends.cuda.matmul.allow_tf32=False
        m=model();source=m.model.layers[0].mlp
        with torch.no_grad():
            for p in source.parameters():p.normal_(0,.1)
        exponents=make_scale_maps(m,10)['0']
        tables=dict(x=[[4.,1.,.25,.0625]],g=[4.],u=[4.],weight_exponents=exponents)
        wrapped=TrainableFFN(source,tables,0,Config(weight_bits=10,nonlinear_samples=32))
        with noise_context(wrapped,NoiseKey(7)):
            wrapped(torch.randn(3,64)).square().mean().backward()
        self.assertTrue(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in wrapped.parameters()))
        codes,_,_=quantize(source.gate_proj.weight,10,wrapped.gu_weight_exponents[:1])
        self.assertLessEqual(int(codes.abs().max()),511)


if __name__=='__main__':unittest.main()
