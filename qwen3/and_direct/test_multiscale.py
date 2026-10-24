import unittest,torch
from .core import literal_events,output_counts
from .multiscale_core import encode_bins,sigmoid_field,shifted_output,MultiScaleFFN,OFFSETS

class MultiTests(unittest.TestCase):
    def setUp(self):torch.manual_seed(175)

    def test_shift_after_bucket_and_count_compression_exact(self):
        t=8;n=128;o=64
        codes=tuple(torch.randint(0,256,(2,n)) for _ in range(3))
        events=literal_events(codes,torch.randint(0,256,(t,3,2,n)))
        sign=torch.randint(0,2,(2,n))*2-1
        shifts=torch.randint(0,15,(2,n));w=torch.randint(-127,128,(o,n))
        coeff=torch.randint(0,65536,(1,n//64))
        weight=w*coeff.repeat_interleave(64,0).repeat_interleave(64,1)
        expected=torch.zeros(2,o,dtype=torch.int64)
        for b in events:
            for shift in range(15):
                partial=((b&(shifts==shift)).long()*sign)@weight.T
                expected+=partial<<(14-shift)
        actual=shifted_output(events.sum(0),sign,shifts,w,coeff,t,14)
        self.assertTrue(torch.equal(actual,expected))

    def test_sigmoid_all_amplitude_exponent_sign_combinations(self):
        q=torch.arange(256)[:,None,None].expand(256,25,2)
        exponent=torch.arange(-16,9)[None,:,None].expand_as(q)
        sign=torch.tensor([-1,1])[None,None,:].expand_as(q)
        ref=(torch.ldexp((q*sign).double(),exponent-5)).round().clamp(-128,127).long()
        self.assertTrue(torch.equal(sigmoid_field(q,sign,exponent),ref))
        # Same physical g=1 at two scales MUST have the same sigmoid input.
        self.assertEqual(sigmoid_field(torch.tensor(128),torch.tensor(1),torch.tensor(1)).item(),8)
        self.assertEqual(sigmoid_field(torch.tensor(64),torch.tensor(1),torch.tensor(2)).item(),8)

    def test_scalar_fixed_bin_selection_and_endpoints(self):
        top=torch.tensor([64.]);x=torch.linspace(-65,65,1280).reshape(20,64)
        for bins in OFFSETS:
            q,s,e,k=encode_bins(x,top,bins)
            for value,code,sign,exp,shift in zip(x.flatten().tolist(),q.flatten().tolist(),s.flatten().tolist(),e.flatten().tolist(),k.flatten().tolist()):
                chosen=max([0]+[a for a in OFFSETS[bins] if abs(value)<=64*2**(-a)])
                expected=min(255,round(abs(value)/(64*2**(-chosen))*256))
                self.assertEqual((code,shift,exp),(expected,chosen,6-chosen))

    def test_b1_matches_previous_integer_output(self):
        x=torch.randint(0,65,(2,128));s=torch.randint(0,2,(2,128))*2-1
        w=torch.randint(-127,128,(64,128));c=torch.randint(0,65536,(1,2))
        self.assertTrue(torch.equal(shifted_output(x,s,torch.zeros_like(x),w,c,64,0),output_counts(x*s,w,c,64)))

    @unittest.skipUnless(torch.cuda.is_available(),'CUDA verified inside Slurm')
    def test_cuda_shifted_output_exact(self):
        torch.backends.cuda.matmul.allow_tf32=False
        t=1024;n=128;o=128
        x=torch.randint(0,t+1,(7,n));s=torch.randint(0,2,(7,n))*2-1;k=torch.randint(0,15,(7,n))
        w=torch.randint(-127,128,(o,n));c=torch.randint(0,65536,(2,2))
        expected=((x<<(14-k))*s)@(w*c.repeat_interleave(64,0).repeat_interleave(64,1)).T
        actual=shifted_output(x.cuda(),s.cuda(),k.cuda(),w.cuda(),c.cuda(),t,14).cpu()
        self.assertTrue(torch.equal(actual,expected))

    def test_only_x_stage_and_replay(self):
        m=torch.nn.Module()
        for name in ('gate_proj','up_proj','down_proj'):setattr(m,name,torch.nn.Linear(64,64,bias=False))
        m=MultiScaleFFN(m,0);m.freeze_down();calls=[];stage=m._stage
        def traced(v,s,w,r):calls.append(s);return stage(v,s,w,r)
        m._stage=traced;x=torch.randn(2,64).bfloat16()
        m.reset_multi(4,'sampled',64,0);a=m(x)
        m.reset_multi(4,'sampled',64,0);b=m(x)
        self.assertEqual(calls,['x','x']);self.assertTrue(torch.equal(a,b))

if __name__=='__main__':unittest.main()
