import copy,unittest
import numpy as np
from evaluate_trace import evaluate
from formats import quantize,words

def fixture(role):
    gen=np.random.default_rng(225);G=40 if role=='GU' else 152;T=16 if role=='GU' else 32
    parts=gen.integers(-100000,100001,(G,4,256),dtype=np.int64)
    hi=gen.integers(2,13,(4,G),dtype=np.int64);cf=np.ones((4,G),dtype=np.int64)<<gen.integers(4,size=(4,G))
    ce=np.frexp(cf.astype(np.float64))[1]-1
    ex=np.array([8,9,8,9]);delta=np.repeat(12-hi.T[:,:,None]+ce.T[:,None,:],64,-1)
    ref=(parts<<delta).sum(0);p=np.repeat(ex-16-int(np.log2(T))-12,64)
    physical=np.ldexp(ref.astype(np.float64),p)
    z=dict(parts=parts,hi=hi,minimum_shift=hi-2,coeff=cf,ex=ex,reference=ref,samples=T,R=12,role=role,g_cap=256,u_cap=256)
    if role=='GU':z['reference_fp32']=physical.astype(np.float32)
    else:z['reference_bf16']=words(quantize(physical,8)[0],8).astype(np.uint16)
    return z

class Tests(unittest.TestCase):
    def test_full_K_GU(self):
        r=evaluate(fixture('GU'));self.assertEqual(r['K_blocks'],40)
        self.assertTrue(all(v['rational_chains_checked']==2 for k,v in r['formats'].items() if k in ('FP24','BF16')))
    def test_full_K_Wd(self):
        r=evaluate(fixture('Wd'));self.assertEqual(r['K_blocks'],152)
        self.assertEqual(r['formats']['FP24']['values'],1024)
    def test_wrong_exact_reference_rejected(self):
        z=fixture('GU');z['reference'][0,0]+=1
        with self.assertRaises(AssertionError):evaluate(z)

if __name__=='__main__':unittest.main()
