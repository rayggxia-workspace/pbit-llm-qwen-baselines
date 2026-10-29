import itertools,types,unittest,torch
from qwen3.group_shared.grid_refinement import components,counts_grid,GridGroupFFN,GRIDS
from qwen3.group_shared.core import Group64FFN
from qwen3.group_shared.test_core import setup
from qwen3.and_direct.short_core import joint_counts

class Grid(unittest.TestCase):
    def test_old_grid_exact_random_replay(self):
        q=[torch.arange(257).long() for _ in range(3)]
        a,p=joint_counts(q,128,torch.Generator().manual_seed(321))
        b,z=counts_grid(q,(4,2,4),128,torch.Generator().manual_seed(321))
        self.assertTrue(torch.equal(a,b));self.assertTrue(torch.equal(p,z))

    def test_finer_grid_moments_and_endpoints(self):
        for grid in GRIDS:
            q=[torch.full((5000,),v,dtype=torch.long) for v in (77,128,31)]
            base,terms=components(q,grid);mean=base.double();var=torch.zeros_like(mean)
            for n,p in terms:mean+=n*p;var+=n*p*(1-p)
            expected=128*77*128*31/256**3
            self.assertTrue(torch.allclose(mean,torch.full_like(mean,expected),rtol=0,atol=1e-12))
            c,_=counts_grid(q,grid,128,torch.Generator().manual_seed(206))
            self.assertAlmostEqual(c.double().mean().item(),expected,delta=8*(var.mean().item()/5000)**.5+.01)
            allhalf=[torch.full((16,),128,dtype=torch.long)]*3
            z,_=counts_grid(allhalf,grid,128,torch.Generator().manual_seed(6));self.assertTrue((z==16).all())

    def test_literal_finite_grid_independent_oracle(self):
        grid=(8,2,8);N=6000;q=[torch.full((N,),v,dtype=torch.long) for v in (61,133,47)]
        gen=torch.Generator().manual_seed(7);z=torch.zeros(N,dtype=torch.long)
        for cell in itertools.product(*(range(d) for d in grid)):
            event=torch.ones(N,dtype=torch.bool)
            for a,i,d in zip(q,cell,grid):event&=(i*(256//d)+torch.randint(256//d,(N,),generator=gen)<a)
            z+=event.long()
        c,_=counts_grid(q,grid,128,torch.Generator().manual_seed(8))
        se=((z.double().var().item()+c.double().var().item())/N)**.5
        self.assertAlmostEqual(z.double().mean().item(),c.double().mean().item(),delta=8*se+.005)

    def test_old_grid_full_FFN_replay(self):
        torch.manual_seed(14);o=types.SimpleNamespace(**{n:torch.nn.Linear(64,64,bias=False) for n in ('gate_proj','up_proj','down_proj')})
        a=Group64FFN(o,0);b=GridGroupFFN(o,0);setup(a,'all_max');setup(b,'all_max');b.grid=(4,2,4)
        x=torch.randn(2,64)*.1;self.assertTrue(torch.equal(a(x),b(x)))

if __name__=='__main__':unittest.main()
