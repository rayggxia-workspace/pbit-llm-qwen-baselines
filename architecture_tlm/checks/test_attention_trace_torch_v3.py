"""Optional CPU torch cross-check against the EXISTING max4 router code."""
import importlib.util
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from capture_attention_trace_v3 import DecodeTraceCollector
from attention_reference_v3 import selector


class TorchTraceTests(unittest.TestCase):
    def test_actual_router_scores_and_probabilities(self):
        source=ROOT.parent/'joint_router_ffn_20261009/metrics.py'
        spec=importlib.util.spec_from_file_location('existing_router_metrics',source)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
        torch.manual_seed(17)
        q=torch.randn(1,14,1,64);k=torch.randn(1,2,257,64)
        scores=old.score(q,old.build(k,4,False),257,'max4')
        n=old.sizes(257,q.device);mandatory=old.mandatory(n)
        free=(~mandatory).float();den=free.sum().clamp_min(1)
        mean=(scores*free).sum(-1,keepdim=True)/den
        std=(((scores-mean).square()*free).sum(-1,keepdim=True)/den).sqrt().clamp_min(.01)
        pi=(((scores-mean)/std-1)/.7).sigmoid().masked_fill(mandatory,1.)
        collector=DecodeTraceCollector({'kind':'CPU synthetic Q/K golden check'})
        collector.add(0,0,q,k)
        for head,row in enumerate(collector.rows):
            _,info=selector(row['logits'],-1.,.7,random.Random(1))
            self.assertTrue(torch.allclose(torch.tensor(info['block_scores']),scores[0,head],atol=1e-6))
            self.assertTrue(torch.allclose(torch.tensor(info['block_probabilities']),pi[0,head],atol=1e-6))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'trace.json';collector.save(path)
            self.assertEqual(len(json.loads(path.read_text())['rows']),14)


if __name__=='__main__':unittest.main(verbosity=2)
