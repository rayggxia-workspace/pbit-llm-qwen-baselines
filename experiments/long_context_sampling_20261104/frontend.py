"""Current S12/F4 max-gap -> U8/F4 floor-P8, winner slot0 and burn0.

Independent Philox behavior: dyadic probabilities are equivalent to R8 < q,
but do not reproduce the GF64/Bivium shared hardware random sequences.
"""
from contextlib import AbstractContextManager
import torch
from .vendor.sparq_ising import scoring
from .vendor.sparq_ising.vendor import kernels


class Frontend(AbstractContextManager):
    def __init__(self, table):
        self.table = table
        self.old = kernels.probabilities
        self.old_controller = scoring.Controller
        self.metrics = {}
        self.calls = 0

    def probabilities(self, logits, method):
        if method != 'winner' or not bool(torch.isfinite(logits).all()):
            raise ValueError('winner with finite, unpadded candidate scores required')
        raw = torch.round(logits.float()*16)
        code = raw.clamp(-2048, 2047).long()
        gap = code.amax(-1, keepdim=True)-code
        address = gap.clamp(0, 255)
        threshold = self.table[address]
        values = dict(score_entries=torch.tensor(logits.numel(), device=logits.device),
                      score_clipped=(raw != code).sum(), gap_clipped=(gap > 255).sum(),
                      zero_threshold_entries=(threshold == 0).sum())
        for name, value in values.items():
            self.metrics[name] = self.metrics.get(name, 0)+value
        self.calls += 1
        planes = torch.zeros((logits.shape[0], 26, logits.shape[1]), device=logits.device)
        planes[:, 0] = threshold.float()/256
        planes[:, 25, 0] = 1  # Actual current hardware initialization, no hidden argmax/burn.
        return planes.contiguous()

    def __enter__(self):
        kernels.probabilities = self.probabilities
        owner = self
        class Controller(self.old_controller):
            def report(self):
                r = super().report()
                r.update(ideal_sigmoid_source=False if self.cfg and self.cfg.mode=='winner' else None,
                         hardware_bittrue=False, hardware_ppa=None,
                         numeric_contract='S12F4_gap_U8F4_floorP8',
                         initial_winner_slot=0, burn=0)
                return r
        scoring.Controller = Controller
        return owner

    def __exit__(self, *args):
        kernels.probabilities = self.old
        scoring.Controller = self.old_controller

    def report(self):
        return dict(probability_calls=self.calls,
                    **{name:int(value) for name,value in self.metrics.items()},
                    contract='S12F4_gap_U8F4_floorP8', initial_winner_slot=0, burn=0,
                    rng='independent keyed Philox; no paired prefixes across S; not hardware bittrue')


def replay_gate(table):
    """Actual Triton candidate widths versus independent scalar state replay."""
    checks = []
    for n in (4, 256, 512, 1024):
        gen = torch.Generator(device='cuda').manual_seed(237+n)
        z = torch.randn((2, n), generator=gen, device='cuda')*2
        s = 8
        raw_score = torch.round(z*16).clamp(-2048, 2047).long()
        q = table[(raw_score.amax(-1, keepdim=True)-raw_score).clamp(0,255)]
        words = torch.randint(256, (2,s,n), generator=gen, device='cuda')
        bits = (words < q[:,None]).cpu().tolist()
        expected = []
        for row in range(2):
            state = 0
            stream = []
            for frame in bits[row]:
                active = [i for i,b in enumerate(frame) if b]
                if active and not frame[state]:
                    state = active[(2**31) % len(active)]
                stream.append(state)
            expected.append(stream)
        raw = torch.full((2,s), 2**31, device='cuda', dtype=torch.int64)
        coin = torch.zeros((2,s), device='cuda')
        with Frontend(table):
            actual,stats = kernels.sample(z,s,'winner',burn=0,seed=7,
                                         replay=(words.float()/256,raw,coin))
        assert actual.cpu().tolist() == expected
        assert bool((stats[:,0]==s).all() and (stats[:,1]==s).all())
        checks.append(dict(candidates=n,samples=s,actual_triton_replay=True))
    return checks
