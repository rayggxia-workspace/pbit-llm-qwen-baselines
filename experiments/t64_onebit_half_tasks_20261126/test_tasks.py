import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('half_task_extension', Path(__file__).with_name('runner.py'))
extension = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extension)


class Tests(unittest.TestCase):
    def plan(self):
        import json
        return json.loads(Path(__file__).with_name('PLAN.json').read_bytes())

    def test_four_cases_only(self):
        cases = extension.cases(self.plan())
        self.assertEqual(len(cases), 4)
        self.assertEqual(len({x['id'] for x in cases}), 4)
        self.assertTrue(all(x['id'].startswith('S2_') for x in cases))

    def test_grid_and_actual_sample_budget(self):
        for c in extension.cases(self.plan()):
            g, h, u = c['grid_g_sig_u']
            self.assertEqual(g*h*u, c['T_and'])
            self.assertIn((c['T_x'], c['T_and']), [(16, 32), (64, 128)])

    def test_work_items_cover_full_documents(self):
        extension.configure_parent()
        plan = self.plan()
        items = extension.previous.work_items(plan)
        self.assertEqual(len(items), 100)
        self.assertEqual(len({x['id'] for x in items}), 100)
        for c in extension.cases(plan):
            for task, config in plan['tasks'].items():
                positions = [i for x in items if x['case']==c and x['task']==task
                             for i in range(x['start'], x['end'])]
                self.assertEqual(positions, list(range(config['count'])))

    def test_scalar_variance_tradeoff(self):
        # IID estimator variance times T, in units S^2. Not a prediction of
        # the actual stratified/joint-grid variance or whole-model PPL.
        a = 3/8
        self.assertEqual(a*(1-a)/(a*(.5-a)), 5)
        a = 1/8
        self.assertLess(a*(.25-a), a*(.5-a))


if __name__ == '__main__':
    unittest.main()
