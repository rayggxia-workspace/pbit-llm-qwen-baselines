"""Reject configuration faults that can silently invalidate a DRAM comparison."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from audit_dram import audit, ROOT


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT/'configs/ddr4_2ch_2rank_Staggered_core_limits.json'
        self.doc = json.loads(self.source.read_text(encoding='utf-8'))

    def check_bad(self, change):
        doc = copy.deepcopy(self.doc)
        change(doc['simulation'])
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory)/'bad.json'
            path.write_bytes((json.dumps(doc)+'\n').encode('utf-8'))
            with self.assertRaises(AssertionError):
                audit(path)

    def test_both_profiles_accept(self):
        for path in (ROOT/'configs').glob('*.json'):
            self.assertEqual(audit(path)['capacity_bytes'], 16*2**30)

    def test_missing_rank_bit_rejected(self):
        self.check_bad(lambda sim: sim['addressmapping'].pop('RANK_BIT'))

    def test_rank_alias_rejected(self):
        self.check_bad(lambda sim: sim['addressmapping'].__setitem__('RANK_BIT',[32]))

    def test_wrong_die_current_rejected(self):
        self.check_bad(lambda sim: sim['memspec']['mempowerspec'].__setitem__('ipp2p',.017))

    def test_free_capacity_expansion_rejected(self):
        self.check_bad(lambda sim: sim['memspec']['memarchitecturespec'].__setitem__('nbrOfRows',65536))

    def test_old_beta_override_rejected(self):
        self.check_bad(lambda sim: sim['memspec']['mempowerspec'].__setitem__('iBeta_vdd',.05625))


if __name__ == '__main__':
    unittest.main()
