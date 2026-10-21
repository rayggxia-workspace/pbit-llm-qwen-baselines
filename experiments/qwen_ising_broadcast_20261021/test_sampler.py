import itertools
import math
import unittest
import numpy as np
from sampler import finite_equilibrium,sample_indices,SamplingLimitError,sigmoid


class Contracts(unittest.TestCase):
    def test_count_energy_conditional(self):
        d=np.array([-.2,-1.1,-2.]);k=3.
        def energy(s):return k*s.sum()*(s.sum()-1)/2-d@s
        for bits in itertools.product([0,1],repeat=3):
            s=np.array(bits)
            for j in range(3):
                a=s.copy();b=s.copy();a[j]=0;b[j]=1
                self.assertAlmostEqual(energy(a)-energy(b),d[j]-k*(s.sum()-s[j]))

    def test_equilibrium_dp(self):
        z=np.array([0.,-.2,-1.1,-2.]);k=2.;weights=[];legal=[]
        for bits in itertools.product([0,1],repeat=3):
            s=np.array(bits);w=math.exp(z[1:]@s-k*s.sum()*(s.sum()-1)/2)
            weights.append(w);legal.append(w if s.sum()<=1 else 0.)
        got=finite_equilibrium(z,k)
        self.assertAlmostEqual(got['equilibrium_invalid_fraction'],1-sum(legal)/sum(weights))

    def test_kappa_zero_independent(self):
        z=np.array([[0.,-1.,-2.]])
        a,s=sample_indices(z,8,kappa=0,block=0,burn=2,spacing=1,max_slots=64)
        self.assertEqual(a.shape,(1,8));self.assertFalse(s['iid_fallback'])

    def test_padding_and_reference(self):
        z=np.array([[float('-inf'),2.,float('-inf')]])
        a,s=sample_indices(z,8,kappa=12,block=0,burn=0,spacing=1,max_slots=8)
        self.assertTrue((a==1).all());self.assertEqual(s['peak_active_count'],0)

    def test_seed_and_stall(self):
        z=np.zeros((4,32))
        a,s=sample_indices(z,8,kappa=16,block=0,burn=2,spacing=1,max_slots=16,strict=False)
        b,t=sample_indices(z,8,kappa=16,block=0,burn=2,spacing=1,max_slots=16,strict=False)
        self.assertTrue(np.array_equal(a,b));self.assertEqual(s,t)
        self.assertGreater(s['invalid_phase_fraction'],.1)
        self.assertGreater(s['adjacent_repeat_fraction'],.9)
        with self.assertRaises(SamplingLimitError):
            sample_indices(z,8,kappa=16,block=0,burn=2,spacing=1,max_slots=1)

    def test_single_site_transition_preserves_finite_gibbs(self):
        # Exact enumeration tests the true conditional update, not sampled means.
        z=np.array([-.1,-.9,-1.7]);k=2.;states=np.array(list(itertools.product([0,1],repeat=3)))
        w=np.exp(states@z-k*states.sum(1)*(states.sum(1)-1)/2);pi=w/w.sum()
        P=np.zeros((8,8))
        for a,s in enumerate(states):
            for j in range(3):
                p=sigmoid(z[j]-k*(s.sum()-s[j]))
                for value in [0,1]:
                    y=s.copy();y[j]=value;b=np.flatnonzero((states==y).all(1))[0]
                    P[a,b]+=(p if value else 1-p)/3
        self.assertLess(float(np.abs(pi@P-pi).max()),1e-14)

if __name__=='__main__':unittest.main()
