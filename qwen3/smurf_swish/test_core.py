import itertools
import unittest
import numpy as np
from core import stationary, propagate, moments, simulate, threshold_stream, fit, target, weighted_planes


class TestFSM(unittest.TestCase):
    def test_stationary_invariant(self):
        p=np.array([0,.001,.25,.5,.9,.999,1])
        for n in (2,4,8,16):
            a=stationary(p,n)
            np.testing.assert_allclose(propagate(a,p),a,atol=1e-14)
            np.testing.assert_allclose(a.sum(1),1,atol=1e-14)

    def test_finite_moments_exhaustive(self):
        # Enumerate both input and output bits, independent of recurrence.
        q=64;p=q/256;codes=np.array([13,87,201,256]);theta=codes/256
        for t in (1,2,3):
            m=v=mass=0.
            for seq in itertools.product((0,1),repeat=2*t):
                state=2;count=0;prob=1.
                for i in range(t):
                    x,y=seq[2*i:2*i+2]
                    prob*=p if x else 1-p
                    state=max(0,min(3,state+2*x-1))
                    prob*=theta[state] if y else 1-theta[state]
                    count+=y
                mass+=prob;m+=prob*count/t;v+=prob*(count/t)**2
            am,av=moments(codes,[q],t)
            self.assertAlmostEqual(mass,1);self.assertAlmostEqual(am[0],m)
            self.assertAlmostEqual(av[0],v-m*m)

    def test_monte_carlo_mean_variance(self):
        codes=np.array([3,81,170,237]);q=np.array([16,64,128,240])
        a,_=simulate(codes,q,64,123,8192)
        m,v=moments(codes,q,64)
        np.testing.assert_array_less(np.abs(a.mean(1)-m),5*np.sqrt(v/8192)+1e-4)
        np.testing.assert_allclose(a.var(1),v,rtol=.08,atol=2e-5)

    def test_endpoints_and_replay(self):
        a,_=simulate([0,0,256,256],[0,256],64,4)
        np.testing.assert_array_equal(a[0],0);np.testing.assert_array_equal(a[1],1)
        a,_=simulate([1,99,176,240],[19,128,222],32,7)
        b,_=simulate([1,99,176,240],[19,128,222],32,7)
        np.testing.assert_array_equal(a,b)

    def test_strata_coverage(self):
        for mode in ('ordered32','shuffle32'):
            r=threshold_stream(np.random.default_rng(7),64,(3,5),mode)
            for frame in r.reshape(2,32,3,5):
                expected=np.broadcast_to(np.arange(32)[:,None,None],(32,3,5))
                np.testing.assert_array_equal(np.sort(frame//8,axis=0),expected)

    def test_plane_sum_signed(self):
        rng=np.random.default_rng(17)
        b=rng.integers(0,2,(128,64));w=rng.integers(-127,128,64)
        np.testing.assert_array_equal(weighted_planes(b,w),b@w)
        # Unsigned raw planes have equal bit counts but different values.
        self.assertEqual(weighted_planes([1],[1]),1)
        self.assertEqual(weighted_planes([1],[64]),64)

    def test_target_scale_and_noncommutativity(self):
        from scipy.special import expit
        p=np.array([0,.25,.5,1])
        for sign in (-1,1):
            np.testing.assert_allclose(sign*4*target(p,4,sign),sign*4*p*expit(sign*4*p))
        self.assertGreater(abs(.5*(2*expit(2))-expit(1)),.1)

    def test_coefficient_and_budget(self):
        c,_=fit(4)
        self.assertTrue(np.all((c>=0)&(c<=256)))
        with self.assertRaises(ValueError):simulate(c,[128],256,0)
        with self.assertRaises(ValueError):simulate(c,[257],64,0)

if __name__=='__main__':unittest.main(verbosity=2)
