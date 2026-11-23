"""Independent finite enumeration and resource-bound checks."""
import itertools
import unittest
import numpy as np
from coverage import probabilities, occupancy


class CheckCoverage(unittest.TestCase):
    def test_uniform(self):
        p=np.full((1,4),.25)
        self.assertAlmostEqual(occupancy(p,2)[0][0],1.75)
        self.assertAlmostEqual(occupancy(p,2,2)[0][0],1.5)

    def test_deterministic(self):
        p=np.array([[0.,1.,0.,0.]])
        for k in [1,8,16384]:
            self.assertEqual(occupancy(p,k)[0][0],1)
            self.assertEqual(occupancy(p,k)[2][0],1)
        self.assertEqual(occupancy(p,0)[0][0],0)

    def test_exhaustive(self):
        p=np.array([.05,.15,.3,.2,.3])
        for group in [1,2,4]:
            result=np.zeros(3)
            for draw in itertools.product(range(5),repeat=3):
                chance=np.prod(p[list(draw)])
                groups=set(i//group for i in draw)
                indices=set(i for i in range(5) if i//group in groups)
                result+=chance*np.array([len(groups),len(indices)/5,p[list(indices)].sum()])
            measured=occupancy(p[None],3,group)
            np.testing.assert_allclose([x[0] for x in measured],result,atol=1e-14)

    def test_weight_scale_and_zeros(self):
        p,valid=probabilities(np.array([[.001,.5],[0,0]]),np.array([1000,.1]))
        np.testing.assert_array_equal(valid,[True,False])
        np.testing.assert_allclose(p,[[1/1.05,.05/1.05]])

    def test_bounds(self):
        rng=np.random.default_rng(19);p=rng.random((20,2560));p/=p.sum(-1,keepdims=True)
        prev=np.zeros(20)
        for k in [1,16,64,128,256,512,2048,8192]:
            u,r,_=occupancy(p,k)
            self.assertTrue((u<=min(k,2560)+1e-9).all())
            self.assertTrue((r>=prev-1e-14).all());prev=r
            self.assertTrue((occupancy(p,k,64)[1]>=r-1e-14).all())


if __name__=='__main__':unittest.main()
