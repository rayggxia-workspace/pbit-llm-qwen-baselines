import itertools,unittest
import numpy as np
from rejection_sampler import rejection_indices
from sampler import sigmoid


class RejectionContracts(unittest.TestCase):
    def test_exact_accepted_weights_for_every_shift(self):
        for d in [np.array([-.2,-1.,-2.]),np.zeros(5),np.array([-20.,-30.])]:
            target=np.r_[1.,np.exp(d)];target/=target.sum()
            for m in [0,1,3,8]:
                r=2.**(-m);p=sigmoid(d+np.log(r));a=np.zeros(len(d)+1)
                for b in itertools.product([0,1],repeat=len(d)):
                    b=np.array(b);w=np.prod(np.where(b,p,1-p))
                    if b.sum()==0:a[0]+=w*r
                    elif b.sum()==1:a[1+np.flatnonzero(b)[0]]+=w
                np.testing.assert_allclose(a/a.sum(),target,rtol=1e-13,atol=1e-15)

    def test_adaptive_mixture_of_failed_histories_still_has_same_law(self):
        # A rejected proposal can select the next shift. For arbitrary history
        # weights, success-category weights still factor as scalar * target.
        d=np.array([-.3,-1.7]);w=np.r_[1.,np.exp(d)];target=w/w.sum()
        total=np.zeros(3)
        for history_weight,m in [(0.1,0),(0.3,2),(0.6,6)]:
            r=2.**(-m);C=np.prod(1/(1+r*np.exp(d)))
            total+=history_weight*C*r*w
        np.testing.assert_allclose(total/total.sum(),target)

    def test_padding_and_reference_only(self):
        out,s=rejection_indices(np.array([[-np.inf,2.,-np.inf]]),64)
        self.assertTrue((out==1).all());self.assertEqual(s['mean_trials_per_address'],1.)

    def test_flat_2000_completes_without_committing_collision(self):
        out,s=rejection_indices(np.zeros((3,2000)),64,seed=4)
        self.assertEqual(out.shape,(3,64));self.assertFalse(s['failed'])
        self.assertGreater(sum(s['collision_retries_per_row']),0)
        self.assertLess(s['mean_trials_per_address'],12.)

    def test_cap_failure_keeps_missing_outputs(self):
        out,s=rejection_indices(np.zeros((2,512)),4,max_trials_per_sample=1,strict=False)
        self.assertTrue(s['failed']);self.assertTrue((out==-1).any())


if __name__=='__main__':unittest.main()
