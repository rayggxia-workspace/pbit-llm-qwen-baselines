"""Selection isolation and TLM boundary tests; no foundry accuracy claim."""
import copy
import json
import math
import unittest
from pathlib import Path
from sram_cacti_calibration_v1 import fit_metric, macro_lookup, predict_unseen

REFERENCE=Path(__file__).parent/'results/sram_calibration_v1_20261016/reference_points.json'


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.model={'reference':json.loads(REFERENCE.read_text())}

    def test_holdout_cannot_change_model_selection_or_coefficients(self):
        geometries=[('A',32,144),('B',256,144),('C',2048,144),
                    ('D',256,64),('E',256,128),('F',4096,128),('H',4096,144)]
        rows=[dict(id=i,depth=d,width=w,base=1.,
                   truth=2.*(d/256.)**.2*(w/128.)**.1) for i,d,w in geometries]
        first=fit_metric(rows)
        rows[-1]['truth']*=100
        second=fit_metric(rows)
        for key in ('kind','coefficients','candidates','train_mape','loo_mape'):
            self.assertEqual(first[key],second[key])
        self.assertNotEqual(first['H_ape'],second['H_ape'])

    def test_exact_lookup_and_period_not_access_latency(self):
        tt=macro_lookup(self.model,4096,128,'TT',100e6)
        ss=macro_lookup(self.model,4096,128,'SS',100e6)
        self.assertTrue(tt['period_only_eligible'])
        self.assertFalse(ss['period_only_eligible'])
        self.assertLess(ss['read_access_ns'],10.)
        self.assertGreater(ss['minimum_cycle_ns'],10.)
        self.assertTrue(macro_lookup(self.model,4096,128,'SS',80e6)['period_only_eligible'])
        self.assertEqual(tt['area_mm2'],ss['area_mm2'])
        self.assertEqual(ss['source'],'exact_vendor_library')

    def test_missing_geometry_fails_instead_of_zero(self):
        with self.assertRaises(ValueError):macro_lookup(self.model,8192,128,'SS')
        with self.assertRaises(ValueError):macro_lookup(self.model,256,512,'TT')

    def test_calibrated_predictions_and_guards(self):
        model=copy.deepcopy(self.model)
        model['models']={c:{k:dict(kind='constant_residual',coefficients=[math.log(2)],
                                  H_ape=.1,loo_mape=.2) for k in
                               model['reference']['points'][0]['target']} for c in ('TT','SS')}
        raw={'TT':dict(depth=1024,width=128,raw=dict(area_mm2=.1,read_pJ=10,
            write_pJ=20,leakage_W=.001,access_ns=2,cycle_ns=3)),
             'SS':dict(depth=1024,width=128,raw=dict(area_mm2=.3,read_pJ=8,
            write_pJ=16,leakage_W=.002,access_ns=4,cycle_ns=6))}
        tt=predict_unseen(model,1024,128,'TT',raw)
        ss=predict_unseen(model,1024,128,'SS',raw)
        self.assertEqual(tt['prediction']['area_mm2'],ss['prediction']['area_mm2'])
        self.assertAlmostEqual(ss['prediction']['read_internal_pJ'],16.)
        self.assertFalse(ss['extrapolation'])
        with self.assertRaises(ValueError):predict_unseen(model,8192,128,'SS',raw)
        with self.assertRaises(ValueError):predict_unseen(model,512,128,'SS',raw)

    def test_actual_fit_preserves_area_and_reference(self):
        model=json.loads((REFERENCE.parent/'calibration.json').read_text())
        self.assertEqual(len(model['raw_cacti']['rows']),14)
        self.assertEqual(model['reference']['verified_file_count'],56)
        self.assertEqual(model['models']['TT']['area_mm2'],model['models']['SS']['area_mm2'])
        for corner in ('TT','SS'):
            for metric,fit in model['models'][corner].items():
                self.assertTrue(math.isfinite(fit['H_prediction']))
                self.assertGreater(fit['H_prediction'],0)
                self.assertEqual(len(fit['candidates']),2)
                self.assertEqual(len(fit['candidates'][0]['loo_apes']),6)


if __name__=='__main__':unittest.main()
