import math,unittest
from qwen3.group_shared.full_plan import full_window_plan,split_plan,verify_rows,window_seed,ids_sha256


class PlanTests(unittest.TestCase):
    def test_all_targets_and_tail(self):
        p=full_window_plan(299078,2048,1024);r=[dict(x,nll_sum=x['scored_tokens']*2.) for x in p]
        s=verify_rows(r,p);self.assertEqual(s['scored_tokens'],299077);self.assertEqual(s['target_positions_sha256'],ids_sha256(range(1,299078)))
        self.assertEqual(p[0]['first_target'],1);self.assertEqual(p[-1]['end'],299078);self.assertAlmostEqual(s['perplexity'],math.exp(2))
    def test_shards_loss_weighting(self):
        p=full_window_plan(103,20,11);parts=[split_plan(p,i,6) for i in range(6)];self.assertEqual(sum(parts,[]),p)
        r=[dict(x,nll_sum=(x['segment_id']+1)*x['scored_tokens']) for x in p]
        s=verify_rows(r,p);self.assertEqual(s['nll_sum'],sum(x['nll_sum'] for x in r));self.assertEqual(s['scored_tokens'],102)
    def test_duplicate_missing_corrupt(self):
        p=full_window_plan(99,20,11);r=[dict(x,nll_sum=1.) for x in p]
        for bad in (r[:-1],r+[r[-1]],[r[0],*r[2:],r[-1]]):
            with self.assertRaises(ValueError):verify_rows(bad,p)
        r[0]['first_target']+=1
        with self.assertRaises(ValueError):verify_rows(r,p)
    def test_rng_not_repeated_or_shard_dependent(self):
        keys=[window_seed(s,i) for s in (0,1,2) for i in range(293)];self.assertEqual(len(keys),len(set(keys)))
        p=full_window_plan(299078,2048,1024)
        self.assertEqual([window_seed(0,r['segment_id']) for r in p],[window_seed(0,r['segment_id']) for part in range(6) for r in split_plan(p,part,6)])
    def test_invalid(self):
        for x in ((0,0),(3,0),(0,-1)):
            if x!=(0,0):
                with self.assertRaises(ValueError):window_seed(*x)
        with self.assertRaises(ValueError):split_plan([1],6,6)


class ScorerTests(unittest.TestCase):
    def test_next_token_masking_and_chunking(self):
        import torch
        from torch import nn
        from types import SimpleNamespace
        from qwen3.group_shared.full_wt2_run import score_plan
        class Body(nn.Module):
            def __init__(self):
                super().__init__();self.emb=nn.Embedding(7,7);self.emb.weight.data.copy_(torch.eye(7));self.layers=nn.ModuleList([nn.ModuleDict({'mlp':nn.Identity()})])
                # nn.ModuleDict exposes no .mlp attribute, use a plain Module holder.
                l=nn.Module();l.mlp=nn.Identity();self.layers=nn.ModuleList([l])
            def forward(self,input_ids,use_cache=False):
                assert not use_cache
                return SimpleNamespace(last_hidden_state=self.layers[0].mlp(self.emb(input_ids)))
        class Model(nn.Module):
            def __init__(self):
                super().__init__();self.model=Body();self.lm_head=nn.Linear(7,7,bias=False);self.lm_head.weight.data.copy_(torch.arange(49).reshape(7,7)/20)
        m=Model().eval();ids=torch.tensor([0,1,3,2,4,6,5,1,2,3,0,6,5,4,1,3,2]);p=full_window_plan(len(ids),8,4)
        a=score_plan(m,ids,p,chunk=2);b=score_plan(m,ids,p,chunk=16)
        oracle=0.
        for i in range(1,len(ids)):
            z=m.lm_head(m.model.emb(ids[i-1])).float();oracle+=float(torch.logsumexp(z,0)-z[ids[i]])
        self.assertAlmostEqual(a['nll_sum'],oracle,places=5);self.assertAlmostEqual(a['nll_sum'],b['nll_sum'],places=6)
        self.assertEqual(a['scored_tokens'],len(ids)-1);self.assertEqual(a['all_layer_calls'],[len(p)])


if __name__=='__main__':unittest.main()
