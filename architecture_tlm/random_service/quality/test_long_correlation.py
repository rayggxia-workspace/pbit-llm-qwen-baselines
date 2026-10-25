import os
import tempfile
import unittest
from pathlib import Path
import numpy as np
from ..backends import PROFILES,generate
from .long_correlation import native_gen,native_corr,numeric_corr,decode_state,pearson,describe

EXE=Path(os.environ.get('RNG_CORR_EXE','C:/Users/86134/Documents/a_P_BIT/project_archives/rng_correlation_20261025/build/correlation_native.exe'))
TMP=EXE.parent


class CorrelationTests(unittest.TestCase):
    def test_native_reference_all_words_and_state(self):
        for kind in PROFILES:
            width=PROFILES[kind]['state_bits'];lanes=PROFILES[kind]['lanes']
            for seeds in [[1,(1<<width)-1],[0x12345678,0x9abcdef1]]:
                with tempfile.TemporaryDirectory(dir=TMP) as tmp:
                    w,states=native_gen(EXE,kind,seeds,1024,Path(tmp))
                    for port,state in enumerate(seeds):
                        for _ in range(PROFILES[kind]['warmup']):_,state=generate(kind,state)
                        for t in range(1024):
                            out,state=generate(kind,state)
                            np.testing.assert_array_equal(w[t,port*lanes:(port+1)*lanes],out)
                        self.assertEqual(state,decode_state(states[port,2]))

    def test_packed_correlations_all_entries(self):
        for n in [257,511]:
            with tempfile.TemporaryDirectory(dir=TMP) as tmp:
                d=Path(tmp);x=np.random.default_rng(n).integers(0,256,(n,6),dtype=np.uint8)
                x[:,1]=x[:,0];x[:,2]=np.roll(x[:,0],3);x[:,5]=0;x.tofile(d/'words.bin')
                lags=[0,1,3,63,64,65,128];tlags=lags[1:]
                for feature in [4,128,192,-1,-8]:
                    t,s=native_corr(EXE,x,feature,d,lags,tlags)
                    z=x<feature if feature>0 else (x>>(-feature-1))&1
                    for ki,k in enumerate(lags):
                        for i in range(6):
                            for j in range(6):
                                p=pearson(z[:n-k,i],z[k:,j])
                                if p is None:self.assertTrue(np.isnan(s[ki,i,j]))
                                else:self.assertAlmostEqual(s[ki,i,j],p,places=12)
                    for ki,k in enumerate(tlags):np.testing.assert_allclose(t[ki],np.diag(s[ki+1]),equal_nan=True)
                    if feature==128:self.assertAlmostEqual(s[2,0,2],1.0,places=12)

    def test_numeric_fft_and_matrix(self):
        x=np.random.default_rng(19).integers(0,256,(1024,8),dtype=np.uint8)
        lags=[0,1,63,128];t,s=numeric_corr(x,lags,lags[1:])
        for ki,k in enumerate(lags):
            for i in range(8):
                for j in range(8):self.assertAlmostEqual(s[ki,i,j],pearson(x[:len(x)-k,i],x[k:,j]),places=12)
        for k in range(3):np.testing.assert_allclose(t[k],np.diag(s[k+1]),atol=1e-12)

    def test_masks_and_single_lane(self):
        s=np.ones((2,2,2));t=np.ones((2,2))*.1
        r=describe(t,s,[0,1],[1,2],1)
        self.assertIsNone(r['spatial']['within_instance']['same_cycle'])
        self.assertEqual(r['spatial']['between_instances']['same_cycle']['tests'],1)

    def test_invalid_state_no_fallback(self):
        with tempfile.TemporaryDirectory(dir=TMP) as tmp:
            with self.assertRaises(ValueError):native_gen(EXE,'lfsr32',[0,1],1024,Path(tmp))


if __name__=='__main__':unittest.main()
