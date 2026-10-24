import itertools
import unittest
import torch
from .core import output_counts,finish_bf16,literal_events,count_events,coefficient_table,DirectFFN

class DirectTests(unittest.TestCase):
    def setUp(self):torch.manual_seed(73)

    def test_literal_stream_output_equals_compressed_integer(self):
        t=16;n=128;o=64
        codes=tuple(torch.randint(0,257,(2,n),dtype=torch.int64) for _ in range(3))
        thresholds=torch.randint(0,256,(t,3,2,n))
        bits=literal_events(codes,thresholds)
        sign=torch.randint(0,2,(2,n))*2-1
        w=torch.randint(-127,128,(o,n),dtype=torch.int64)
        coeff=torch.randint(1,65536,(1,n//64),dtype=torch.int64)
        weights=w*coeff.repeat_interleave(64,0).repeat_interleave(64,1)
        # Direct circuit semantic: every clock chooses signed W or zero,
        # accumulate only at each output. No intermediate z estimate.
        expected=torch.zeros(2,o,dtype=torch.int64)
        for b in bits:expected+=(b.long()*sign)@weights.T
        actual=output_counts(bits.sum(0)*sign,w,coeff,t)
        self.assertTrue(torch.equal(actual,expected))

    def test_large_count_integer_exactness(self):
        for t in (64,256,1024,4096,16384):
            x=torch.randint(-t,t+1,(3,128),dtype=torch.int64)
            x[0,:]=t;x[1,:]=-t
            w=torch.randint(-127,128,(64,128),dtype=torch.int64);w[0,:]=127
            c=torch.full((1,2),65535,dtype=torch.int64)
            expected=x@(w*c.repeat_interleave(64,0).repeat_interleave(64,1)).T
            self.assertTrue(torch.equal(output_counts(x,w,c,t),expected))

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA check runs in Slurm allocation')
    def test_cuda_integer_partial_gemm(self):
        torch.backends.cuda.matmul.allow_tf32=False
        for t in (64,4096,16384):
            x=torch.randint(-t,t+1,(17,128),dtype=torch.int64)
            w=torch.randint(-127,128,(128,128),dtype=torch.int64)
            c=torch.randint(1,65536,(2,2),dtype=torch.int64)
            expected=x@(w*c.repeat_interleave(64,0).repeat_interleave(64,1)).T
            actual=output_counts(x.cuda(),w.cuda(),c.cuda(),t).cpu()
            self.assertTrue(torch.equal(actual,expected))

    def test_bf16_rounding_ties_and_sign(self):
        # Values are integers times2^-16, including exactly halfway cases.
        a=torch.tensor([0,65536,65792,66304,-65792,-66304,2**48+2**40],dtype=torch.int64)
        a=a[:,None].expand(-1,64)
        out=finish_bf16(a,torch.tensor([0]),1)
        expected=[0.,1.,1.,1.015625,-1.,-1.015625,float(2**48)/65536]
        self.assertEqual(out[:,0].double().tolist(),expected)

    def test_comparator_joint_law_and_endpoints(self):
        # Enumerate independent two-bit thresholds to prove product law.
        for q in ((0,4,4),(1,2,3),(4,4,4)):
            count=sum(r<q[0] and s<q[1] and u<q[2] for r,s,u in itertools.product(range(4),repeat=3))
            self.assertEqual(count/64,q[0]*q[1]*q[2]/64)
        gen=torch.Generator().manual_seed(2)
        z=torch.zeros(4,dtype=torch.int64);one=torch.full_like(z,256)
        self.assertTrue(torch.equal(count_events((z,one,one),64,gen)[0],z))
        self.assertTrue(torch.equal(count_events((one,one,one),64,gen)[0],torch.full_like(z,64)))

    def test_no_z_reencoding_and_replay(self):
        original=torch.nn.Module()
        for name in ('gate_proj','up_proj','down_proj'):setattr(original,name,torch.nn.Linear(64,64,bias=False))
        model=DirectFFN(original,0);model.freeze_down()
        calls=[];stage=model._stage
        def traced(value,signal,matrix,generator):
            calls.append(signal);return stage(value,signal,matrix,generator)
        model._stage=traced
        x=torch.randn(2,64).to(torch.bfloat16)
        model.reset_direct('sampled',64,0);a=model(x)
        model.reset_direct('sampled',64,0);b=model(x)
        self.assertTrue(torch.equal(a,b));self.assertEqual(calls,['x','x'])
        self.assertFalse(model.direct_report()['z_reencoding'])

if __name__=='__main__':unittest.main()
