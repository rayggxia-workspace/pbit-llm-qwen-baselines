import unittest
import numpy as np
from .core import online, softmax, compare, gather, kv_union, bursts, systematic
from .schedule import run, Config


class CoreTests(unittest.TestCase):
    def test_online_stability_partial_tiles(self):
        rng=np.random.default_rng(3)
        for n in (1,65,129):
            q=rng.normal(size=64)*100
            k=rng.normal(size=(n,64));v=rng.normal(size=(n,64))
            np.testing.assert_allclose(online(q,k,v),softmax(k@q/8)@v,rtol=1e-12,atol=1e-12)

    def test_repeated_gather_and_bursts(self):
        v=np.arange(256,dtype=float).reshape(4,64)
        y,c=gather(v,[3,3,0,3]);np.testing.assert_array_equal(y,(v[0]+3*v[3])/4)
        self.assertEqual(c[3],3)
        self.assertEqual(len(bursts(c,64))*64,256)
        self.assertEqual(kv_union([[0,1],[1,2]],64),384)

    def test_systematic_fixed_budget(self):
        for n in (1,7,513):
            p=np.full(n,1/n)
            for s in (1,7,128):
                a=systematic(p,s,np.random.default_rng(4))
                self.assertEqual(len(a),s);self.assertTrue(np.all((a>=0)&(a<n)))

    def test_six_modes_and_shared_candidates(self):
        rng=np.random.default_rng(11)
        q=rng.normal(size=64);k=rng.normal(size=(640,64));v=rng.normal(size=(640,64))
        rows=compare(q,k,v,32,17,budget=4)
        self.assertEqual(len(rows),6)
        self.assertTrue(all(r['status']=='completed' for r in rows))
        for r in rows[2:]:self.assertEqual(r['candidates'],rows[2]['candidates'])
        for r in rows:
            t=run(r,64)
            self.assertEqual(t['memory_link_bytes'],r['K_physical_bytes']+r['V_physical_bytes'])
            self.assertIsNone(t['energy_J'])
            for resource in ('mac','vector','memory_link','local_sram'):
                events=sorted([e for e in t['events'] if e['resource']==resource],key=lambda e:e['start'])
                for a,b in zip(events,events[1:]):self.assertLessEqual(a['issue_end'],b['start'])
            if r['addresses'] is not None:
                self.assertEqual(sum(r['counts'].values()),32)
                self.assertEqual(r['V_adds'],32*64)
        self.assertEqual(rows[0]['squared_error_full'],0)
        self.assertEqual(rows[2]['squared_error_sampling'],0)
        self.assertEqual(rows[0]['PV_MAC'],640*64)
        self.assertGreater(rows[4]['sampler']['actions']['proposal_frames'],0)
        self.assertEqual(rows[5]['sampler']['actions']['algorithm_updates'],64)

    def test_capacity_and_input_contracts(self):
        with self.assertRaises(ValueError):online([1],[[float('nan')]],[[0]])
        rng=np.random.default_rng(4)
        r=compare(rng.normal(size=64),rng.normal(size=(64,64)),rng.normal(size=(64,64)),8,17)[0]
        with self.assertRaises(ValueError):run(r,64,Config(local_capacity=1))

    def test_vector_feedback_is_not_independent_II1(self):
        rng=np.random.default_rng(7)
        row=compare(rng.normal(size=64),rng.normal(size=(64,64)),rng.normal(size=(64,64)),8,17)[1]
        row['counts']={'0':8}
        row['unique_V']=1
        t=run(row,64)
        e=next(e for e in t['events'] if e['name']=='V_repeated_add')
        self.assertGreaterEqual(e['issue_end']-e['start'],8*7)


if __name__=='__main__':unittest.main()
