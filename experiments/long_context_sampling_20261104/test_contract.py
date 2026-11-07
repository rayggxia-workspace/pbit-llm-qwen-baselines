import json
from pathlib import Path
import unittest
from .contract import common_plan,cases,ids_sha,lut_reference,scalar_front


class Tests(unittest.TestCase):
    def test_same_targets_across_lengths(self):
        plans = [common_plan(299078,n) for n in (8192,32768)]
        targets = [[p for row in plan for p in range(row['first_target'],row['last_target_exclusive'])]
                   for plan in plans]
        self.assertEqual(targets[0], targets[1])
        self.assertEqual(len(targets[0]),128)
        self.assertEqual(len(set(targets[0])),128)
        self.assertEqual(ids_sha(targets[0]),ids_sha(targets[1]))
        for context,plan in zip((8192,32768),plans):
            for r in plan:
                self.assertEqual(r['end']-r['begin'],context+32)
                self.assertEqual(r['prefill_tokens'],context-1)
                self.assertEqual(r['first_target']-1-r['begin'],context-1)

    def test_budget_is_bounded(self):
        for n in (8192,32768):
            rows=cases(n,0)
            self.assertEqual(len(rows),8)
            self.assertEqual([r['s'] for r in rows if r['s'] and r['k']==rows[1]['k']],
                             [32,64,128,256])
            self.assertEqual(len(cases(n,1)),6)
        self.assertEqual(sum(len(cases(n,s)) for n in (8192,32768) for s in (0,1,2)),40)

    def test_lut_matches_frozen_hardware_table(self):
        table=json.loads((Path(__file__).parent/'sigmoid_table.json').read_bytes())['values']
        self.assertEqual(table,lut_reference())
        self.assertEqual(table[0],128)
        self.assertEqual(table[-1],0)

    def test_max_after_wide_quantization(self):
        table=lut_reference()
        codes,addresses,thresholds=scalar_front([37.5,37.,-17.5],table)
        self.assertEqual(codes,[600,592,-280])
        self.assertEqual(addresses,[0,8,255])
        self.assertEqual(thresholds,[128,table[8],0])
        self.assertEqual(scalar_front([0.,1/32,3/32],table)[0],[0,0,2])

    def test_bad_plans_rejected(self):
        for args in ((100,8192),(40000,40000),(32780,32768)):
            with self.assertRaises(ValueError):common_plan(*args)


if __name__=='__main__':unittest.main()
