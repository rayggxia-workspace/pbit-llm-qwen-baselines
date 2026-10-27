import copy
import tempfile
import unittest
from pathlib import Path
import torch
from torch import nn
from torch.utils.checkpoint import checkpoint
from qwen3.and_direct.short_core import ShortStreamFFN
from .core import (Config,NoiseKey,TrainableFFN,noise_context,install,quantize,
                   trainable_names,attach)


def original(device='cpu'):
    m=nn.Module()
    for name in ('gate_proj','up_proj','down_proj'):
        setattr(m,name,nn.Linear(64,64,bias=False,device=device))
    return m


def tables():
    return dict(x=[[4.,1.,.25,.0625]],g=[4.],u=[4.])


class TestTraining(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(81)
        torch.set_num_threads(1)
        torch.backends.cuda.matmul.allow_tf32=False

    def test_matches_frozen_W8_oracle_all_samples_and_policies(self):
        src=original();x=torch.randn(3,64).bfloat16()
        key=NoiseKey(3,1,2,0)
        for policy in ('original','lower_half','lower_floor'):
            for samples in (32,64,128):
                oracle=ShortStreamFFN(copy.deepcopy(src),0)
                oracle.mode='sampled';oracle.cycles=oracle.strata=64
                oracle.x_scales=torch.tensor(tables()['x'])
                oracle.g_top=torch.tensor(tables()['g']);oracle.u_top=torch.tensor(tables()['u'])
                oracle.freeze_down();oracle.reset_short(policy,'joint32',samples,0)
                oracle.rng_input=key.generator(x.device,0,'input')
                oracle.rng_and=key.generator(x.device,0,'and')
                m=TrainableFFN(copy.deepcopy(src),tables(),0,Config(nonlinear_samples=samples,policy=policy))
                with noise_context(m,key):y=m(x)
                self.assertTrue(torch.equal(y,oracle(x)),(policy,samples))

    def test_all_three_weights_and_input_receive_finite_gradient(self):
        m=TrainableFFN(original(),tables(),0)
        x=torch.randn(4,64,requires_grad=True)
        with noise_context(m,NoiseKey(9)):
            m(x).square().mean().backward()
        for p in [x]+list(m.parameters()):
            self.assertIsNotNone(p.grad)
            self.assertTrue(torch.isfinite(p.grad).all())
            self.assertGreater(float(p.grad.abs().sum()),0)

    def test_wd_gradient_uses_sampled_z_and_not_mean(self):
        from .core import hard_forward
        m=TrainableFFN(original(),tables(),0);x=torch.randn(4,64)
        key=NoiseKey(5)
        y,c=hard_forward(x,m.gate_proj.weight,m.up_proj.weight,m.down_proj.weight,m,key)
        with noise_context(m,key):m(x).sum().backward()
        expected=c[9].sum(0).expand(64,64)
        self.assertTrue(torch.allclose(m.down_proj.weight.grad,expected,atol=1e-6,rtol=1e-6))

    def test_checkpoint_replay_and_rng_do_not_advance(self):
        m=TrainableFFN(original(),tables(),0);n=copy.deepcopy(m)
        x=torch.randn(3,64,requires_grad=True);xx=x.detach().clone().requires_grad_()
        key=NoiseKey(7,4,2,1)
        with noise_context(m,key):
            a=m(x);a.square().sum().backward()
        with noise_context(n,key):
            b=checkpoint(n,xx,use_reentrant=False);b.square().sum().backward()
        self.assertTrue(torch.equal(a,b));self.assertTrue(torch.equal(x.grad,xx.grad))
        for p,q in zip(m.parameters(),n.parameters()):self.assertTrue(torch.equal(p.grad,q.grad))
        with noise_context(m,key):self.assertTrue(torch.equal(a,m(x)))
        with noise_context(m,NoiseKey(7,5,2,1)):self.assertFalse(torch.equal(a,m(x)))

    def test_state_dict_roundtrip_and_train_eval_both_random(self):
        m=TrainableFFN(original(),tables(),0);n=TrainableFFN(original(),tables(),0)
        n.load_state_dict(m.state_dict());x=torch.randn(2,64)
        with noise_context(m,NoiseKey(2)),noise_context(n,NoiseKey(2)):
            a=m.train()(x);b=n.eval()(x)
        self.assertTrue(torch.equal(a,b))
        with self.assertRaises(RuntimeError):m(x)

    def test_quantization_4_6_8_and_all_zero(self):
        for bits in (4,6,8):
            for w in (torch.randn(128,64),torch.zeros(128,64)):
                codes,dq,lsb=quantize(w,bits)
                self.assertLessEqual(int(codes.abs().max()),2**(bits-1)-1)
                self.assertTrue(torch.isfinite(dq).all())
            m=TrainableFFN(original(),tables(),0,Config(weight_bits=bits))
            with noise_context(m,NoiseKey(1)):m(torch.randn(2,64)).square().sum().backward()
            self.assertTrue(all(torch.isfinite(p.grad).all() for p in m.parameters()))

    def test_only_ffn_is_trainable(self):
        model=nn.Module();model.model=nn.Module();model.model.layers=nn.ModuleList()
        model.embed=nn.Embedding(16,64);model.lm_head=nn.Linear(64,16)
        for _ in range(2):
            layer=nn.Module();layer.mlp=original();layer.norm=nn.LayerNorm(64)
            layer.attention=nn.Linear(64,64);model.model.layers.append(layer)
        names=install(model,dict(layers={'0':tables(),'1':tables()}))
        self.assertEqual(len(names),6)
        self.assertEqual(names,trainable_names(model))
        self.assertTrue(all('.mlp.' in n for n in names))
        with self.assertRaises(ValueError):install(model,dict(layers={'0':tables(),'1':tables()}))

    def test_attach_preserves_exact_hard_bits_and_gradient(self):
        a=torch.tensor([.03125,-2.,1e-5]);b=torch.tensor([1e10,-1e10,1e10],requires_grad=True)
        z=attach(a,b);self.assertTrue(torch.equal(z,a));z.sum().backward()
        self.assertTrue(torch.equal(b.grad,torch.ones_like(b)))

    def test_resume_matches_uninterrupted_next_step(self):
        from .checkpoint import save,restore
        m=TrainableFFN(original(),tables(),0);n=copy.deepcopy(m)
        opt=torch.optim.AdamW(m.parameters(),lr=.001);opt2=torch.optim.AdamW(n.parameters(),lr=.001)
        x=torch.randn(2,64);cfg=Config();provenance={'test':'synthetic'}
        def step(model,optimizer,k):
            optimizer.zero_grad(set_to_none=True)
            with noise_context(model,NoiseKey(1,k)):model(x).square().sum().backward()
            optimizer.step()
        step(m,opt,0)
        # Explicit task-local checkpoint storage (also safe on shared servers).
        parent=Path(__file__).resolve().parents[3]/'work/rayggxia/177'
        parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(parent)) as tmp:
            path=Path(tmp)/'c.pt';save(path,m,opt,1,cfg,provenance,1)
            self.assertEqual(restore(path,n,opt2,cfg,provenance,1),1)
            step(m,opt,1);step(n,opt2,1)
            for a,b in zip(m.parameters(),n.parameters()):self.assertTrue(torch.equal(a,b))
            with self.assertRaises(ValueError):restore(path,n,opt2,Config(nonlinear_samples=64),provenance,1)
            with self.assertRaises(ValueError):restore(path,n,opt2,cfg,{'test':'changed'},1)

    def test_hard_forward_does_not_call_float_nonlinearity(self):
        from unittest.mock import patch
        m=TrainableFFN(original(),tables(),0);x=torch.randn(2,64)
        with patch('torch.sigmoid',side_effect=AssertionError('runtime sigmoid')), \
                patch('torch.nn.functional.silu',side_effect=AssertionError('runtime SiLU')), \
                noise_context(m,NoiseKey(3)),torch.no_grad():
            self.assertTrue(torch.isfinite(m(x)).all())

    def test_scale_calibration_and_train_only_guard(self):
        from .calibrate import collect
        from .train import ReferenceFFN
        class Toy(nn.Module):
            def __init__(self):
                super().__init__();self.embed=nn.Embedding(16,64);self.model=nn.Module()
                layer=nn.Module();layer.mlp=ReferenceFFN(original())
                self.model.layers=nn.ModuleList([layer])
            def forward(self,input_ids,use_cache=False):
                return self.model.layers[0].mlp(self.embed(input_ids))
        m=Toy();batches=[torch.randint(16,(2,4)) for _ in range(2)]
        cal=collect(m,batches,{'split':'train'})
        install(m,cal)
        with self.assertRaises(ValueError):collect(m,batches,{'split':'test'})

    def test_warm_start_keeps_master_precision(self):
        from .checkpoint import load_warm_weights,sha256
        m=nn.Module();m.model=nn.Module();layer=nn.Module();layer.mlp=original().bfloat16()
        m.model.layers=nn.ModuleList([layer]);state={n:torch.randn_like(p.float()) for n,p in m.named_parameters()}
        parent=Path(__file__).resolve().parents[3]/'work/rayggxia/177';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(parent)) as tmp:
            path=Path(tmp)/'warm.pt';torch.save(state,path);load_warm_weights(m,path,sha256(path))
        for n,p in m.named_parameters():self.assertTrue(torch.equal(p,state[n]));self.assertEqual(p.dtype,torch.float32)

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA unavailable')
    def test_cuda_autocast_and_checkpoint(self):
        m=TrainableFFN(original('cuda'),tables(),0)
        x=torch.randn(2,64,device='cuda',dtype=torch.bfloat16,requires_grad=True)
        with noise_context(m,NoiseKey(11)),torch.autocast('cuda',dtype=torch.bfloat16):
            a=checkpoint(m,x,use_reentrant=False);a.float().square().sum().backward()
        with noise_context(m,NoiseKey(11)):b=m(x)
        self.assertTrue(torch.equal(a,b));self.assertTrue(torch.isfinite(x.grad).all())


if __name__=='__main__':unittest.main()
