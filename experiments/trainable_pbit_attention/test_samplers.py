"""Independent finite-state oracles, rule replay, gradient and distribution tests."""
import importlib.util
import itertools
import math
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import torch

from . import samplers as s

torch.set_num_threads(1)
METRICS = {}


class Tape:
    def __init__(self, bits, ranks=(), coins=()):
        self.b = iter(bits)
        self.r = iter(ranks)
        self.c = iter(coins)

    def bits(self, drive, mask):
        b = torch.tensor(next(self.b), device=drive.device, dtype=torch.bool)
        b = b.reshape_as(mask)
        assert not bool((b & ~mask).any())
        return b

    def rank(self, counts):
        ranks = torch.tensor(next(self.r), device=counts.device).reshape_as(counts)
        assert bool(((ranks >= 0) & (ranks < counts)).all())
        return ranks, torch.zeros_like(counts)

    def coin(self, shift):
        return torch.tensor(next(self.c), device=shift.device, dtype=torch.bool).reshape_as(shift)


def enumerated_winner(z, steps):
    """Scalar exhaustive oracle, independent of Torch and production transitions."""
    p = [1 / (1 + math.exp(-(x - max(z)))) for x in z]
    states = [(int(np.argmax(z)), [], [], [], 1.0)]
    for _ in range(steps):
        new = []
        for old, tape, ranks, outputs, mass in states:
            for bits in itertools.product([0, 1], repeat=len(z)):
                prob = math.prod(p[i] if b else 1 - p[i] for i, b in enumerate(bits))
                active = [i for i, b in enumerate(bits) if b]
                if bits[old] or not active:
                    choices = [(old, None)]
                else:
                    choices = list(zip(active, range(len(active))))
                for target, rank in choices:
                    new.append((target, tape + [bits], ranks + ([] if rank is None else [[rank]]),
                                outputs + [target], mass * prob / len(choices)))
        states = new
    return states


def transition(z):
    p = 1 / (1 + np.exp(-(z - max(z))))
    t = np.zeros((len(z), len(z)))
    for old in range(len(z)):
        for bits in itertools.product([0, 1], repeat=len(z)):
            mass = math.prod(p[i] if b else 1-p[i] for i, b in enumerate(bits))
            active = [i for i, b in enumerate(bits) if b]
            if bits[old] or not active:
                t[old, old] += mass
            else:
                for j in active:
                    t[old, j] += mass / len(active)
    return t


class Rules(unittest.TestCase):
    def test_winner_hold_replay_and_costs(self):
        z = torch.tensor([3., 2., 1.], requires_grad=True)
        v = torch.eye(3)
        tape = Tape([[1, 1, 0], [0, 0, 0], [0, 1, 1], [1, 0, 0]], [[1], [0]])
        with patch.object(s, '_Draws', return_value=tape):
            r = s.WinnerHoldAttention(samples=3, burn_in=1)(z, v, record_trace=True)
        self.assertEqual(r.indices.tolist(), [0, 2, 0])
        self.assertEqual(int(r.stats['updates']), 4)
        self.assertEqual(int(r.stats['holds']), 2)
        self.assertEqual(int(r.stats['pbit_draws']), 12)
        self.assertEqual(len(r.trace), 4)
        # All four proposals, including discarded burn and holds, contribute.
        p = torch.sigmoid(z - z[0])
        b = torch.tensor([[1,1,0],[0,0,0],[0,1,1],[1,0,0]], dtype=torch.bool)
        expected = torch.where(b, p.log(), torch.log1p(-p)).sum()
        torch.testing.assert_close(r.score_log_prob, expected)

    def test_spacing_keeps_complete_updates(self):
        with patch.object(s, '_Draws', return_value=Tape([[1,0]]*7)):
            r = s.WinnerHoldAttention(samples=2, burn_in=1, spacing=3)(
                torch.tensor([1., 0.]), torch.eye(2))
        self.assertEqual(r.indices.tolist(), [0, 0])
        self.assertEqual(int(r.stats['updates']), 7)

    def test_rejection_replay_and_correction(self):
        # collision m0->1; rejected zero m1->0; singleton accept; zero m0 accepts ref.
        tape = Tape([[0,1,1], [0,0,0], [0,0,1], [0,0,0]], coins=[[False], [True]])
        with patch.object(s, '_Draws', return_value=tape):
            r = s.CorrectedRejectionAttention(samples=2)(
                torch.tensor([2., 1., 0.], requires_grad=True), torch.eye(3), record_trace=True)
        self.assertEqual(r.indices.tolist(), [2, 0])
        self.assertEqual([x['shift_before'].item() for x in r.trace], [0,1,0,0])
        self.assertEqual(int(r.stats['pbit_draws']), 8)
        self.assertEqual(int(r.stats['correction_fair_bits']), 1)
        self.assertEqual(int(r.stats['collisions']), 1)
        self.assertEqual(int(r.stats['zero_rejections']), 1)
        self.assertEqual(int(r.stats['reference_accepts']), 1)

    def test_cap_has_no_success_or_fallback(self):
        with patch.object(s, '_Draws', return_value=Tape([[0,1,1]]*2)):
            with self.assertRaises(s.SamplingCapError) as e:
                s.CorrectedRejectionAttention(samples=1, max_trials_per_sample=2)(
                    torch.tensor([2.,1.,0.]), torch.eye(3))
        self.assertEqual(int(e.exception.stats['accepted']), 0)
        self.assertEqual(int(e.exception.stats['proposals']), 2)

    def test_completed_rows_stop_and_shift_clamps(self):
        # First row accepts immediately; only second row keeps proposing.
        tape=Tape([[[0,1,0],[0,1,1]], [[0,1,1]], [[0,0,0]], [[0,0,0]]],
                  coins=[[False],[True]])
        with patch.object(s,'_Draws',return_value=tape):
            r=s.CorrectedRejectionAttention(samples=1,max_shift=1)(
                torch.tensor([[3.,2.,1.],[3.,2.,1.]]),torch.eye(3),record_trace=True)
        self.assertEqual(r.stats['proposals'].tolist(),[1,4])
        self.assertEqual(r.stats['pbit_draws'].tolist(),[2,8])
        self.assertEqual([x['shift_after'].tolist() for x in r.trace],[[0,1],[1],[0],[0]])

    def test_default_forward_does_not_call_softmax(self):
        with patch.object(torch.Tensor,'softmax',side_effect=AssertionError('dense softmax called')):
            for cls in (s.WinnerHoldAttention,s.CorrectedRejectionAttention):
                cls(samples=3)(torch.tensor([1.,.2,0.]),torch.eye(3))

    def test_large_masked_rows_and_low_precision_interface(self):
        for cls in (s.WinnerHoldAttention,s.CorrectedRejectionAttention):
            z=torch.linspace(0,-10,128,dtype=torch.bfloat16).expand(2,128)
            mask=torch.arange(128)[None,:] < torch.tensor([[128],[37]])
            r=cls(samples=8)(z,torch.ones(128,5,dtype=torch.bfloat16),mask,
                            generator=torch.Generator().manual_seed(9))
            self.assertEqual(r.output.dtype,torch.bfloat16)
            self.assertTrue(bool((r.indices[1]<37).all()))
            torch.testing.assert_close(r.output,torch.ones(2,5,dtype=torch.bfloat16))

    def test_batched_mask_and_gradient(self):
        for cls in (s.WinnerHoldAttention, s.CorrectedRejectionAttention):
            z = torch.tensor([[[2., 1., -torch.inf], [1., 2., 3.]]], requires_grad=True)
            mask = torch.tensor([[[True, True, False], [True, False, True]]])
            v = torch.arange(6.).reshape(3, 2).requires_grad_()
            r = cls(samples=9)(z, v, mask, generator=torch.Generator().manual_seed(7))
            self.assertEqual(r.output.shape, (1, 2, 2))
            self.assertFalse(bool((r.indices[0,0] == 2).any()))
            self.assertFalse(bool((r.indices[0,1] == 1).any()))
            r.objective(r.output.square().sum(-1)).sum().backward()
            self.assertTrue(torch.isfinite(z.grad).all())
            self.assertEqual(z.grad[0,0,2].item(), 0)
            self.assertEqual(z.grad[0,1,1].item(), 0)
            torch.testing.assert_close(z.grad.sum(-1), torch.zeros(1,2), atol=2e-5, rtol=0)
            self.assertTrue(torch.isfinite(v.grad).all())

    def test_seed_replay_and_advancement(self):
        for cls in (s.WinnerHoldAttention, s.CorrectedRejectionAttention):
            f = cls(samples=50).eval()
            g = torch.Generator().manual_seed(73)
            z, v = torch.tensor([2.,1.5,1.,0.]), torch.eye(4)
            first = f(z,v,generator=g)
            again = f(z,v,generator=g)
            reset = f(z,v,generator=torch.Generator().manual_seed(73))
            self.assertTrue(torch.equal(first.indices, reset.indices))
            self.assertFalse(torch.equal(first.indices, again.indices))

    def test_single_key(self):
        for cls in (s.WinnerHoldAttention, s.CorrectedRejectionAttention):
            r = cls(samples=3)(torch.tensor([0.]), torch.tensor([[7.]]))
            self.assertEqual(r.indices.tolist(), [0,0,0])
            self.assertEqual(r.output.item(), 7.)

    def test_validation(self):
        for kwargs in [dict(samples=0), dict(probability_bits=8), dict(drive_step=.125),
                       dict(gradient_mode='fake')]:
            with self.assertRaises(ValueError):
                s.WinnerHoldAttention(**kwargs)
        for z in [torch.tensor([-torch.inf]*2), torch.tensor([float('nan'),1.]),
                  torch.tensor([float('inf'),1.])]:
            with self.assertRaises(ValueError):
                s.WinnerHoldAttention()(z,torch.eye(2))

    def test_quantization_and_q256_endpoints(self):
        # Direct source check includes p=0 and p=1 endpoints (threshold 256).
        rng = s._Draws(torch.Generator().manual_seed(0), 8)
        for _ in range(5):
            self.assertEqual(rng.bits(torch.tensor([[-1000.,1000.]]),
                             torch.ones(1,2,dtype=torch.bool)).tolist(), [[False, True]])
        f = s.WinnerHoldAttention(samples=5, gradient_mode='none', drive_step=.125, probability_bits=8)
        self.assertEqual(f._drive(torch.tensor([-99., -.19, 0.])).tolist(), [-31.875, -.25, 0.])
        self.assertEqual(f(torch.tensor([1.,0.]),torch.eye(2)).indices.numel(),5)

    def test_fair_ranks_and_coins(self):
        rng = s._Draws(torch.Generator().manual_seed(8), None)
        ranks, cost = rng.rank(torch.full((30000,),3))
        self.assertTrue(bool((cost >= 2).all()))
        hist = torch.bincount(ranks,minlength=3).double()/len(ranks)
        self.assertLess(float((hist-1/3).abs().max()), .015)
        for m in (0,1,3):
            fraction = rng.coin(torch.full((30000,),m)).double().mean().item()
            self.assertLess(abs(fraction-2**(-m)), .012)


class Gradients(unittest.TestCase):
    def test_nonlinear_loss_of_sample_average_gradient(self):
        z0=np.array([.4,-.1]);v=np.array([-1.,2.])
        paths=enumerated_winner(z0,3)
        grad_sum=np.zeros(2)
        for _,bits,ranks,outputs,mass in paths:
            z=torch.tensor(z0,requires_grad=True)
            with patch.object(s,'_Draws',return_value=Tape(bits,ranks)):
                r=s.WinnerHoldAttention(samples=2,burn_in=1)(z,torch.tensor(v[:,None]))
            loss=(r.output.squeeze()-.25)**2
            grad_sum+=mass*torch.autograd.grad(r.objective(loss),z)[0].numpy()
        def expectation(z):
            return sum(m*(np.mean(v[o[1:]])-.25)**2 for _,_,_,o,m in enumerated_winner(z,3))
        eps=1e-5
        numeric=[(expectation(z0+np.eye(2)[i]*eps)-expectation(z0-np.eye(2)[i]*eps))/(2*eps) for i in range(2)]
        np.testing.assert_allclose(grad_sum,numeric,atol=1e-9)
        METRICS['nonlinear_average_gradient_max_abs_error']=float(np.max(np.abs(grad_sum-numeric)))

    def test_finite_winner_expectation_gradient_exact_enumeration(self):
        z0 = np.array([.6, -.2, .1])
        values = np.array([-1., .5, 2.])
        def expectation(z):
            return sum(mass * (values[outputs[-1]]-.3)**2
                       for _,_,_,outputs,mass in enumerated_winner(z, 2))
        total_grad = np.zeros(3)
        paths = enumerated_winner(z0, 2)
        self.assertAlmostEqual(sum(path[-1] for path in paths), 1., places=13)
        for _, bits, ranks, outputs, mass in paths:
            z = torch.tensor(z0, requires_grad=True)
            with patch.object(s, '_Draws', return_value=Tape(bits,ranks)):
                r = s.WinnerHoldAttention(samples=1,burn_in=1)(z,torch.tensor(values[:,None]))
            self.assertEqual(r.indices.item(), outputs[-1])
            loss = (r.output.squeeze()-.3)**2
            grad = torch.autograd.grad(r.objective(loss),z)[0].numpy()
            total_grad += mass * grad
        eps = 1e-5
        numeric = np.array([(expectation(z0+np.eye(3)[i]*eps)-expectation(z0-np.eye(3)[i]*eps))/(2*eps)
                            for i in range(3)])
        np.testing.assert_allclose(total_grad,numeric,atol=2e-9,rtol=1e-7)
        METRICS['winner_enumerated_paths']=len(paths)
        METRICS['winner_gradient_max_abs_error']=float(np.max(np.abs(total_grad-numeric)))

    def test_rejection_accepted_path_gradient_includes_retries(self):
        bits = [[0,1,1], [0,0,0], [0,1,0]]
        z = torch.tensor([.7,-.4,.2],dtype=torch.float64,requires_grad=True)
        with patch.object(s,'_Draws',return_value=Tape(bits,coins=[[False]])):
            r = s.CorrectedRejectionAttention(samples=1)(z,torch.eye(3,dtype=torch.float64))
        derivative = torch.autograd.grad(r.score_log_prob,z)[0].numpy()
        def log_path(a):
            total = math.log(.5)  # zero correction rejected at m=1
            for b,m in zip(bits,[0,1,0]):
                for j in [1,2]:
                    p=1/(1+math.exp(-(a[j]-a[0]-m*math.log(2))))
                    total += math.log(p if b[j] else 1-p)
            return total
        a=z.detach().numpy();eps=1e-5
        numeric=[(log_path(a+np.eye(3)[i]*eps)-log_path(a-np.eye(3)[i]*eps))/(2*eps) for i in range(3)]
        np.testing.assert_allclose(derivative,numeric,atol=1e-9)
        METRICS['rejection_retry_path_gradient_max_abs_error']=float(np.max(np.abs(derivative-numeric)))

    def test_rejection_two_key_expected_loss_gradient(self):
        # m=0,N=2 always accepts: exhaustive finite process, no cap conditioning.
        z0 = torch.tensor([.7,-.2],dtype=torch.float64)
        expected = torch.zeros(2,dtype=torch.float64)
        for bit in (0,1):
            z=z0.clone().requires_grad_()
            with patch.object(s,'_Draws',return_value=Tape([[0,bit]],coins=[[True]])):
                r=s.CorrectedRejectionAttention(samples=1)(z,torch.tensor([[-1.],[2.]],dtype=torch.float64))
            loss=(r.output.squeeze()-.4)**2
            p=torch.sigmoid(z0[1]-z0[0])
            expected += (p if bit else 1-p)*torch.autograd.grad(r.objective(loss),z)[0]
        z=z0.clone().requires_grad_()
        exact=(z.softmax(-1)*torch.tensor([1.96,2.56],dtype=torch.float64)).sum()
        torch.testing.assert_close(expected,torch.autograd.grad(exact,z)[0])

    def test_direct_values_and_explicit_surrogate(self):
        for mode in ('score_function','softmax_surrogate','none'):
            z=torch.tensor([1.,0.,-.4],requires_grad=True)
            v=torch.tensor([[1.],[2.],[4.]],requires_grad=True)
            f=s.WinnerHoldAttention(samples=12,gradient_mode=mode)
            r=f(z,v,generator=torch.Generator().manual_seed(5))
            loss=r.output.sum()
            obj=r.objective(loss) if mode=='score_function' else loss
            self.assertEqual(obj.item(),loss.item())
            obj.backward()
            expected=torch.bincount(r.indices,minlength=3).float()/12
            torch.testing.assert_close(v.grad.squeeze(),expected)
            if mode=='softmax_surrogate':
                a=z.detach().requires_grad_()
                exact=(a.softmax(-1)*v.detach().squeeze()).sum()
                torch.testing.assert_close(z.grad,torch.autograd.grad(exact,a)[0])
            if mode=='none':self.assertIsNone(z.grad)

    def test_global_loss_requires_joint_path_score(self):
        with self.assertRaises(ValueError):
            s.score_function_loss(torch.ones(2),torch.ones(2,3))
        lp=torch.tensor([[1.,2.],[3.,4.]],requires_grad=True)
        out=s.score_function_loss(torch.tensor([5.,6.]),lp.sum(-1),baseline=1.)
        out.mean().backward()
        torch.testing.assert_close(lp.grad,torch.tensor([[2.,2.],[2.5,2.5]]))


class Distributions(unittest.TestCase):
    def test_winner_stationary_detailed_balance(self):
        z=np.array([.8,.2,-.3,.1]);t=transition(z)
        pi=np.exp(z)/np.exp(z).sum()
        np.testing.assert_allclose(t.sum(-1),1,atol=1e-14)
        np.testing.assert_allclose(pi[:,None]*t,(pi[:,None]*t).T,atol=1e-14)

    def test_rejection_conditional_law_at_every_shift(self):
        z=np.array([.7,.3,-.2,.1]);target=np.exp(z)/np.exp(z).sum()
        for m in (0,1,3,8):
            p=1/(1+np.exp(-(z[1:]-z[0]-m*math.log(2))))
            mass=np.zeros(4)
            for bits in itertools.product([0,1],repeat=3):
                pr=math.prod(p[i] if b else 1-p[i] for i,b in enumerate(bits))
                if sum(bits)==0:mass[0]+=pr*2**(-m)
                if sum(bits)==1:mass[1+bits.index(1)]+=pr
            np.testing.assert_allclose(mass/mass.sum(),target,atol=1e-14)

    def test_three_seed_distributions_against_oracle_and_historical_numpy(self):
        path=Path(__file__).parents[1]/'pbit_sampler_qkv_20261021'/'samplers.py'
        spec=importlib.util.spec_from_file_location('historical_samplers',path)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        z=np.array([.8,.2,-.3,.1]);n=15000;updates=4
        pi=np.exp(z)/np.exp(z).sum()
        init=np.eye(4)[z.argmax()];finite=init@np.linalg.matrix_power(transition(z),updates)
        scores=torch.tensor(z).expand(n,-1);v=torch.eye(4,dtype=torch.float64)
        for seed in (0,1,2):
            for kind,cls,expected in [('winner_hold',s.WinnerHoldAttention,finite),
                                      ('rejection',s.CorrectedRejectionAttention,pi)]:
                options=dict(samples=1,gradient_mode='none')
                if kind=='winner_hold':options['burn_in']=updates-1
                r=cls(**options)(scores,v,generator=torch.Generator().manual_seed(seed))
                hist=torch.bincount(r.indices.flatten(),minlength=4).numpy()/n
                self.assertLess(np.max(np.abs(hist-expected)),.018)
                if kind=='winner_hold':
                    oi,_=old.chains(z,updates,n,np.random.default_rng(seed),'winner_hold');oi=oi[:,-1]
                else:oi,_=old.corrected_rejection(z,1,n,np.random.default_rng(seed));oi=oi[:,0]
                oh=np.bincount(oi,minlength=4)/n
                self.assertLess(np.max(np.abs(oh-expected)),.018)
                self.assertLess(np.max(np.abs(hist-oh)),.025)
                METRICS.setdefault('distribution_checks',[]).append(dict(
                    seed=seed,kind=kind,repeats=n,expected=expected.tolist(),
                    pytorch=hist.tolist(),historical_numpy=oh.tolist(),
                    max_abs_frequency_error=float(np.max(np.abs(hist-expected)))))


if __name__ == '__main__':
    unittest.main(verbosity=2)
