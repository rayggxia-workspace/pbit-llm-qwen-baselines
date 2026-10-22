import itertools,unittest
import numpy as np
from field_quant import accepted_law,quantize_field,limits
from rejection_sampler import rejection_indices
from sampler import sigmoid


class FieldQuantContracts(unittest.TestCase):
    def test_field_law_matches_exact_event_enumeration(self):
        d=np.array([[0.,-.3,-2.,-8.]])
        for m in [0,4,12]:
            a=quantize_field(d-m*np.log(2.),8,.125)
            p=sigmoid(a[0,1:]);mass=np.zeros(4)
            for bits in itertools.product([0,1],repeat=3):
                b=np.array(bits);w=np.prod(np.where(b,p,1-p))
                if b.sum()==0:mass[0]+=w*2.**(-m)
                elif b.sum()==1:mass[1+np.flatnonzero(b)[0]]+=w
            np.testing.assert_allclose(mass/mass.sum(),accepted_law(d,[m],a)[0],rtol=2e-13)

    def test_no_field_quantization_is_shift_invariant(self):
        d=np.array([[0.,-2.,-30.,-np.inf]])
        for m in [0,4,14,24]:
            np.testing.assert_allclose(accepted_law(d,[m]),accepted_law(d,[0]),atol=1e-15)

    def test_invalid_sites_remain_disabled_after_saturation(self):
        d=np.array([[0.,-2.,-np.inf]])
        q=accepted_law(d,[14],quantize_field(d-14*np.log(2.),8,.125))
        self.assertEqual(q[0,2],0.)

    def test_negative_format_uses_all_256_levels(self):
        self.assertEqual(limits(8,.125,True),(-31.875,0.))
        self.assertEqual(len(np.unique(quantize_field(np.arange(256)*-.125,8,.125,True))),256)

    def test_observer_does_not_change_sampler_outputs_or_stats(self):
        z=np.array([[0.,-.2,-3.,-np.inf],[0.,-2.,-8.,-9.]])
        seen=[]
        plain,s=rejection_indices(z,64,seed=17)
        obs,t=rejection_indices(z,64,seed=17,proposal_observer=lambda a,v,m,r:seen.append(int(v.sum())))
        np.testing.assert_array_equal(plain,obs);self.assertEqual(s,t);self.assertGreater(sum(seen),0)

    def test_negative_clipping_can_accumulate_with_large_offset(self):
        d=np.r_[0.,np.full(1999,-40.)][None]
        q=accepted_law(d,[14],quantize_field(d-14*np.log(2.),8,.125))
        self.assertLess(q[0,0],.3)
        # This is a stress case at forced m14, not a normal adaptive peaked row.


if __name__=='__main__':unittest.main()
