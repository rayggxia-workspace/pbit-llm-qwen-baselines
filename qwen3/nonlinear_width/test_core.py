import math
import unittest
import torch
from .core import magnitude, make_lut, probability, NonlinearFFN

class Formats(unittest.TestCase):
    def test_full_module_oracle_and_quantized_boundary(self):
        torch.manual_seed(11)
        original=torch.nn.Module()
        for n in ('gate_proj','up_proj','down_proj'):
            setattr(original,n,torch.nn.Linear(64,64,bias=False))
        model=NonlinearFFN(original,0)
        x=torch.randn(2,3,64)
        g,u=torch.nn.functional.linear(x,model.gu_decoded).chunk(2,-1)
        expected=torch.nn.functional.linear(torch.nn.functional.silu(g)*u,model.down_decoded)
        self.assertTrue(torch.equal(model(x),expected))
        model.set_spec(8,8,8)
        gq,_=magnitude(g,model.g_top,8);uq,_=magnitude(u,model.u_top,8)
        z=(gq.double()*uq.double()*probability(gq,8,8,model.lut)).float()
        self.assertTrue(torch.equal(model(x),torch.nn.functional.linear(z,model.down_decoded)))
        self.assertEqual(model.nl_stats[0],g.numel())

    def test_amplitude_scalar_reference(self):
        for b in (6,7,8,10,12):
            values=[-3.,-1.,-.5,0.,.5,1.,3.,1./(2**(b+1))]*8
            x=torch.tensor(values)
            y,_=magnitude(x,torch.ones(1),b)
            expected=[math.copysign(min(max(round(abs(v)*2**b),0),2**b-1)/2**b,v) for v in values]
            self.assertEqual(y.tolist(),expected)

    def test_all_lut_entries_and_comparator_endpoints(self):
        for f in (8,10,12):
            for p in (6,8,10,12):
                lut=make_lut(f,p)
                half=2**(f-1)
                fields=torch.arange(-half,half,dtype=torch.float32)*(32./2**f)
                out=probability(fields,f,p,lut)
                expected=[round((1/(1+math.exp(-float(v))))*2**p)/2**p for v in fields]
                self.assertEqual(out.tolist(),expected)
                for q in (0,1,2**p-1,2**p):
                    count=sum(r<q for r in range(2**p))
                    self.assertEqual(count,q)

    def test_driver_clipping_and_three_stream_expectation(self):
        lut=make_lut(8,8)
        result=probability(torch.tensor([-100.,0.,100.]),8,8,lut)
        self.assertEqual(result.tolist(),[0.,.5,1.])
        # Exhaustive independent integer thresholds, not a stochastic tolerance.
        counts=sum((r<2) and (s<3) and (t<1) for r in range(4) for s in range(4) for t in range(4))
        self.assertEqual(counts/64,(2/4)*(3/4)*(1/4))

if __name__=='__main__':unittest.main()
