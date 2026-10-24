import unittest
import numpy as np
import torch
from .model_tables import build,occupancy,exact_count_moments,CASES

class ModelTests(unittest.TestCase):
    def test_model_mean_zero_and_no_z_reencode(self):
        from .model_core import FSMFFN
        original=torch.nn.Module()
        for name in ('gate_proj','up_proj','down_proj'):
            setattr(original,name,torch.nn.Linear(64,64,bias=False))
        m=FSMFFN(original,0);m.setup(8,.5,[2.],{T:build(8,8,.5,T) for T in (64,128)})
        calls=[]
        def zero_stage(x,signal,matrix,generator):
            calls.append((signal,matrix));return torch.zeros(*x.shape[:-1],128)
        m._stage=zero_stage;m.reset_fsm('fsm_mean',64,0)
        result=m(torch.ones(2,64,dtype=torch.bfloat16))
        self.assertEqual(result.abs().sum().item(),0)
        self.assertEqual(calls,[('x','gu')]);self.assertFalse(m.report()['z_reencoding'])

    def test_scale_inside_nonlinearity(self):
        # A scalar output multiplier cannot undo changing SiLU's argument.
        silu=lambda x:x/(1+np.exp(-x))
        self.assertGreater(abs(8*silu(1/8)-silu(1)),.1)
        for G,N,S in CASES:
            for T in (64,128):
                b=build(G,N,S,T)
                for k,sign in enumerate((1,-1)):
                    Sf=G if sign==1 else S
                    expected=np.rint(np.abs(silu(sign*G*np.arange(256)/256))/Sf*256)
                    np.testing.assert_array_equal(b['lut'][k],expected)
                    self.assertEqual(b['theta'][k][0],0)
                    self.assertEqual(b['mean'][k][0],0)
                    self.assertTrue(all(0<=x<=256 for x in b['theta'][k]))

    def test_finite_mean_moments(self):
        b=build(8,8,.5,64);q=np.arange(256)
        for k in (0,1):
            m,v=exact_count_moments(b['theta'][k],q,np.full(256,256),64)
            np.testing.assert_allclose(m/64,b['mean'][k],atol=1e-14)
            self.assertTrue((v>=0).all())
        np.testing.assert_allclose(occupancy(q,8,64).sum(1),1,atol=1e-14)

    @unittest.skipUnless(torch.cuda.is_available(),'requires Slurm GPU allocation')
    def test_literal_cuda_replay(self):
        from .model_kernel import counts
        for G,N,S in CASES:
            T=64;b=build(G,N,S,T);theta=torch.tensor(b['theta'],dtype=torch.int64)
            q=torch.arange(256,dtype=torch.int64).repeat(2);neg=torch.arange(512)%2
            u=(torch.arange(512)*37)%257
            got,trace=counts(q.cuda(),u.cuda(),neg.cuda(),theta.cuda(),T,901,True)
            trace=trace.cpu();state=torch.zeros_like(q);ref=torch.zeros_like(q)
            for t in range(T):
                state=(state+2*(trace[t,0]<q).long()-1).clamp(0,N-1)
                ref+=((trace[t,1]<theta[neg,state])&(trace[t,2]<u)).long()
            self.assertTrue(torch.equal(got.cpu(),ref))
            again=counts(q.cuda(),u.cuda(),neg.cuda(),theta.cuda(),T,901)
            self.assertTrue(torch.equal(again,got))

    @unittest.skipUnless(torch.cuda.is_available(),'requires Slurm GPU allocation')
    def test_cuda_statistics(self):
        from .model_kernel import counts
        b=build(8,8,.5,64);theta=torch.tensor(b['theta'],device='cuda')
        qs=np.array([0,8,32,96,128,192,255]);us=np.array([256,256,192,128,256,64,256])
        trials=8192
        for neg in (0,1):
            q=torch.tensor(qs,device='cuda')[:,None].expand(-1,trials).contiguous()
            u=torch.tensor(us,device='cuda')[:,None].expand(-1,trials).contiguous()
            got=counts(q,u,torch.full_like(q,neg),theta,64,7561+neg).cpu().double().numpy()
            m,v=exact_count_moments(b['theta'][neg],qs,us,64)
            self.assertTrue((np.abs(got.mean(1)-m)<6*np.sqrt(v/trials)+.003).all())
            self.assertTrue((np.abs(got.var(1)-v)<.12*np.maximum(v,.01)+.01).all())

if __name__=='__main__':unittest.main()
