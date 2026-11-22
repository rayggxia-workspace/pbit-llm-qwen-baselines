import unittest
from submit_followups import select


class SelectionChecks(unittest.TestCase):
    def setUp(self):
        self.settings=dict(absolute_max_ppl_ratio=1.10,preferred_max_ppl_ratio=1.05,
                           minimum_relative_unique_address_reduction=.05,max_full_candidates=2)

    def row(self,name,family,ppl,address,status='completed'):
        return dict(case=name,family=family,ppl_ratio=ppl,unique_address_ratio=address,
                    relative_address_reduction=1-address,status=status)

    def test_qualified_distinct_families_and_cap(self):
        rows=[self.row('pot2','pot',1.01,.9),self.row('pot4','pot',1.04,.6),
              self.row('cat64','categorical',1.2,.01),self.row('cat256','categorical',1.04,.1),
              self.row('norm','normalized_bernoulli',1.02,.2)]
        self.assertEqual([r['case'] for r in select(rows,self.settings)],['pot4','cat256'])

    def test_bad_quality_no_read_saving_and_failed_rejected(self):
        rows=[self.row('bad','pot',1.11,.1),self.row('dense','categorical',1.,.99),
              self.row('failed','pot',1.,.1,'not_completed')]
        self.assertEqual(select(rows,self.settings),[])

    def test_fallback_prefers_quality_when_no_five_percent_candidate(self):
        rows=[self.row('a','pot',1.06,.5),self.row('b','pot',1.09,.1)]
        self.assertEqual(select(rows,self.settings)[0]['case'],'a')


if __name__=='__main__':unittest.main()
