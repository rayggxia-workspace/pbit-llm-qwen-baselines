import unittest
from meter import integrate,summarize

class MeterTests(unittest.TestCase):
    def test_constant_power_and_clipped_boundaries(self):
        self.assertAlmostEqual(integrate([(0.,100.),(1.,100.),(2.,100.)],.25,1.75),150.)
    def test_linear_ramp(self):
        self.assertAlmostEqual(integrate([(0.,0.),(2.,200.)],.5,1.5),100.)
    def test_refuses_extrapolation(self):
        with self.assertRaises(ValueError):integrate([(1.,100.),(2.,100.)],0.,2.)
    def test_independent_repeat_summary(self):
        x=summarize([{'energy_J':1.,'average_W':100.},{'energy_J':3.,'average_W':150.}])
        self.assertEqual(x['energy_J']['mean'],2.)
        self.assertEqual(x['average_W']['mean'],125.)

if __name__=='__main__':unittest.main()
