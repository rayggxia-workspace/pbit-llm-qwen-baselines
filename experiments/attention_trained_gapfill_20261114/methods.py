"""Full-WT2 sweep; reuse the frozen S12/P8 numeric law and native FFN."""
from experiments.attention_gap_accuracy_20261102.methods import Patch as GapPatch
from experiments.sparq_ising_20261028.core import Config

CASES = [{'name': 'bf16', 'k': None, 'samples': None, 'seed': 0, 'overlay': None}, {'name': 'k_wh128_wh_k64_s64', 'k': 64, 'samples': 64, 'seed': 0, 'overlay': 'k_wh128'}, {'name': 'k_wh128_wh_k64_s128', 'k': 64, 'samples': 128, 'seed': 0, 'overlay': 'k_wh128'}, {'name': 'k_wh128_wh_k128_s16', 'k': 128, 'samples': 16, 'seed': 0, 'overlay': 'k_wh128'}, {'name': 'k_wh128_wh_k256_s16', 'k': 256, 'samples': 16, 'seed': 0, 'overlay': 'k_wh128'}, {'name': 'k_wh128_wh_k256_s128', 'k': 256, 'samples': 128, 'seed': 0, 'overlay': 'k_wh128'}]


def configuration(case):
    if case['k'] is None:
        return None
    return Config(r=32, k=case['k'], local=32, samples=case['samples'] or 64,
                  burn=0, mode='winner' if case['samples'] else 'exact')


class Patch(GapPatch):
    def __init__(self, case):
        self.case = case
        super().__init__('ising64_gap_s12_p8' if case['samples'] else 'bf16')

    def report(self):
        value = super().report()
        value.update(case=self.case, samples=self.case['samples'],
                     screening=f"FP32 SparQ r32/k{self.case['k']}/recent32; no mean-V compensation"
                     if self.case['k'] else None,
                     numeric=value['numeric'] if self.case['samples'] else
                     ('FP32 candidate softmax and weighted PV; original BF16 interfaces'
                      if self.case['k'] else 'unchanged native BF16 SDPA'),
                     hardware_changed=False, hardware_bittrue=False)
        return value
