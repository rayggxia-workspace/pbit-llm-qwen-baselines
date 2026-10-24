import unittest
from summarize import check_time_unit


class TimeUnitsTests(unittest.TestCase):
    def test_synopsys_formats(self):
        for text in ['Time Unit : 1ns', 'Time_unit : 1e-09 Second',
                     'Time_Unit = 1000ps', 'Time Units = 0.001us']:
            check_time_unit(text+'\n')

    def test_still_rejects_other_units(self):
        for text in ['Time_unit : 1ps', 'Time Unit : 1e-12 Second',
                     'Time_unit : nan ns', 'Voltage_unit : 1 Volt']:
            with self.assertRaises(ValueError):check_time_unit(text+'\n')


if __name__ == '__main__':unittest.main()
