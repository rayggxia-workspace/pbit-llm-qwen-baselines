import unittest
from controlled_remeasure import stable_temperature, counter_result


class ProtocolTest(unittest.TestCase):
    def test_temperature_requires_five_samples(self):
        self.assertFalse(stable_temperature([{'temperature_C':40}]*4))
        self.assertTrue(stable_temperature([{'temperature_C':40}]*5))

    def test_drifting_temperature_is_not_stable(self):
        self.assertFalse(stable_temperature([{'temperature_C':i} for i in range(40,45)]))

    def test_counter_units(self):
        r=counter_result(100000,160000,20.,30.,2000)
        self.assertEqual(r['average_W'],6.)
        self.assertEqual(r['energy_mJ_per_item'],30.)
        self.assertEqual(r['wall_ms_per_item'],5.)

    def test_reject_bad_counter(self):
        with self.assertRaises(ValueError):
            counter_result(100,99,1.,2.,10)


if __name__=='__main__':
    unittest.main()
