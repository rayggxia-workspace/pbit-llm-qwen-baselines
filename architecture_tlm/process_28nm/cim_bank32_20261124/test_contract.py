"""Meaningful invariants for the offline layout and single-zone resource bound."""
import math
import unittest
from model import packed_byte

class Contract(unittest.TestCase):
    def test_every_weight_has_exactly_one_byte(self):
        addresses = [packed_byte(i,o) for i in range(64) for o in range(128)]
        self.assertEqual(sorted(addresses), list(range(8192)))

    def test_one_word_contains_two_inputs_for_eight_outputs(self):
        for row in range(32):
            for bank in range(16):
                address = [packed_byte(i,o) for i in (2*row,2*row+1)
                    for o in range(8*bank,8*(bank+1))]
                self.assertEqual(address, list(range(row*256+bank*16,row*256+bank*16+16)))

    def test_five_not_four_cores_cover_peak_in_Wd(self):
        per_core = 8192 / ((32+34)*4)
        self.assertLess(4*per_core, 136.4606)
        self.assertGreater(5*per_core, 136.4606)
        self.assertEqual(math.ceil(136.4606/per_core), 5)

if __name__ == '__main__': unittest.main()
