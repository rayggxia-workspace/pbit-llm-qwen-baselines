import itertools
import sys
import unittest
from pathlib import Path
import numpy as np
from samplers import chains,corrected_rejection,distribution,output_metrics,sigmoid


class Checks(unittest.TestCase):
    def test_exact_winner_balance(self):
        z=np.array([1.7,-.2,.8,-1.]);pi=distribution(z)
        for shift in (0.,2.,4.):
            p=sigmoid(z-z.max()-shift);kernel=np.zeros((4,4))
            for bits in itertools.product((0,1),repeat=4):
                mass=np.prod(np.where(bits,p,1-p));active=np.flatnonzero(bits)
                for old in range(4):
                    if bits[old] or not len(active):kernel[old,old]+=mass
                    else:kernel[old,active]+=mass/len(active)
            np.testing.assert_allclose(pi@kernel,pi,atol=1e-14)
            np.testing.assert_allclose(pi[:,None]*kernel,(pi[:,None]*kernel).T,atol=1e-14)

    def test_prefix_and_bounds(self):
        z=np.array([1.,-.2,.4,-1.,.3])
        for method in ('winner_hold','two_bits','barker','xor'):
            a,sa=chains(z,50,4,np.random.default_rng(8),method)
            b,sb=chains(z,80,4,np.random.default_rng(8),method)
            np.testing.assert_array_equal(a,b[:,:50])
            self.assertTrue(((a>=0)&(a<len(z))).all())
            self.assertTrue((sa['switch_prefix'][:,-1]<=50).all())

    def test_rejection_matches_frozen_reference(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'qwen_ising_broadcast_20261021'))
        from rejection_sampler import rejection_indices
        z=np.array([2.,.8,-.2,-3.])
        a,stats=corrected_rejection(z,96,4,np.random.default_rng(12))
        b,old=rejection_indices(np.broadcast_to(z,(4,4)).copy(),96,rng=np.random.default_rng(12))
        np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(stats['proposal_phase_at'][:,-1],old['proposal_trials_per_row'])
        self.assertEqual(int(stats['empty_coin_at'][:,-1].sum()),old['needed_fair_bits_for_empty_correction'])

    def test_histogram_scores_equal_direct_V(self):
        z=np.array([.5,1.,-.5]);v=np.array([[1.,2.],[-2.,1.],[4.,-1.]])
        ix=np.array([[0,0,1,2,0],[2,1,1,0,2]])
        curves,profile=output_metrics(ix,z,v,[0,1],[2,4]);mu=distribution(z)@v
        for x in curves:
            direct=np.mean(v[ix[:,x['burn']:x['burn']+x['samples']]],axis=1)
            expected=np.square(direct-mu).sum(1)
            np.testing.assert_allclose(expected,x['squared_error_per_repeat'])

    def test_uniform_iid_error_matches_analytic(self):
        z=np.zeros(4);v=np.eye(4);rng=np.random.default_rng(40)
        ix=rng.integers(0,4,size=(2000,128))
        curves,_=output_metrics(ix,z,v,[0],[128])
        self.assertLess(abs(curves[0]['normalized_mse']*128-1),.08)

    def test_single_category_and_constant_V(self):
        for method in ('winner_hold','two_bits','barker','xor'):
            ix,_=chains([3.],50,3,np.random.default_rng(4),method)
            self.assertTrue((ix==0).all())
        c,_=output_metrics(np.zeros((3,4),int),[3.],np.array([[1.,2.]]),[0],[4])
        self.assertEqual(c[0]['normalized_mse'],0.)

    def test_long_run_correct_mean(self):
        z=np.array([1.,-.3,.2]);pi=distribution(z)
        for method in ('winner_hold','two_bits','barker','xor'):
            ix,_=chains(z,20000,3,np.random.default_rng(42),method,shift=0.)
            freq=np.bincount(ix[:,1000:].reshape(-1),minlength=3)/(3*19000)
            self.assertLess(float(np.abs(freq-pi).max()),.035)

    def test_quantized_drive_is_not_probability_quantization(self):
        # Nonzero extremely small p remains representable through a drive, not R8.
        self.assertLess(float(sigmoid(-20.)),1/256)
        ix,st=chains([0.,-20.],10,2,np.random.default_rng(2),'barker',drive_step=.125)
        self.assertEqual(st['drive_step'],.125)


if __name__=='__main__':unittest.main()
