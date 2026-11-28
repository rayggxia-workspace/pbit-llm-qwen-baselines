from pathlib import Path
import importlib.util,json,unittest
import torch
from x_onebit import encode_x,FROZEN_X_ENCODE

class Tests(unittest.TestCase):
    def test_disabled_equals_shared_single_scale(self):
        gen=torch.Generator().manual_seed(225)
        for exponent in [-9,-6,-5,0,5,10]:
            v=torch.randn(3,128,generator=gen)*2.**exponent
            a=encode_x(v,False);b=FROZEN_X_ENCODE(v,64,512.)
            for key,value in zip(['q','sign','exponent','shift','scale'],b):
                self.assertTrue(torch.equal(a[key],value),key)

    def test_half_boundary_and_full_bypass(self):
        v=torch.zeros(64);v[:5]=torch.tensor([1.,.5,-.5,.5009765625,0.])
        a=encode_x(v)
        self.assertEqual(a['small'][:5].tolist(),[False,True,True,False,True])
        self.assertEqual(a['q'][:5].tolist(),[256,256,256,128,0])

    def test_group_baseline_and_floor(self):
        v=torch.full((2,64),2.**-10);v[0,0]=2.**-6;v[1,0]=4.
        a=encode_x(v)
        self.assertFalse(bool(a['small'][0].any()))
        self.assertEqual(a['base_exponent'][:,0].tolist(),[-6,2])
        self.assertTrue(bool(a['small'][1,1:].all()))

    def test_integer_x_restore_before_gu_sum(self):
        gen=torch.Generator().manual_seed(225)
        x=torch.randn(2,128,generator=gen)*3
        a=encode_x(x);count=torch.randint(17,a['q'].shape,generator=gen)
        w=torch.randint(-127,128,(32,128),generator=gen,dtype=torch.int64)
        rr=int(a['shift'].max())
        aligned=(count*a['sign'])<<(rr-a['shift'])
        actual=torch.ldexp((aligned@w.T).double(),torch.tensor(9-rr))
        expected=(count*a['sign']*a['scale'].double())@w.double().T
        self.assertTrue(torch.equal(actual,expected))

    def test_one_task_case_and_complete_dataset_partition(self):
        spec=importlib.util.spec_from_file_location('x_task_extension',Path(__file__).with_name('runner.py'))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.configure()
        p=json.loads(Path(__file__).with_name('PLAN.json').read_bytes())
        jobs=m.tasks.work_items(p)
        self.assertEqual(len(jobs),25)
        self.assertEqual(m.cases(p)[0]['grid_g_sig_u'],[4,2,4])
        for task,t in p['tasks'].items():
            pos=[i for j in jobs if j['task']==task for i in range(j['start'],j['end'])]
            self.assertEqual(pos,list(range(t['count'])))

if __name__=='__main__':unittest.main()
