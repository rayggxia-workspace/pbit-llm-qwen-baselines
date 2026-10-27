"""Exact small-state proofs and explicit counterexamples, not MC-only checks."""
from collections import Counter
from fractions import Fraction
from itertools import product
import unittest


def rank_select(bitmap,rank):
    return [i for i,b in enumerate(bitmap) if b][rank]


class MathTests(unittest.TestCase):
    def test_unbiased_mask_rejection_and_grouped_select(self):
        for n in (4,8):
            for bitmap in product((0,1),repeat=n):
                m=sum(bitmap)
                if not m:continue
                width=(m-1).bit_length()
                accepted=Counter(rank_select(bitmap,r) for r in range(1<<width) if r<m)
                self.assertEqual(set(accepted.values()),{1})
                self.assertEqual(set(accepted),{i for i,b in enumerate(bitmap) if b})
                # group/rank split gives same leaf as independent flat list.
                for rank in range(m):
                    counts=[sum(bitmap[i:i+2]) for i in range(0,n,2)]
                    prefix=0
                    for g,c in enumerate(counts):
                        if prefix<=rank<prefix+c:
                            idx=2*g+rank_select(bitmap[2*g:2*g+2],rank-prefix)
                            self.assertEqual(idx,rank_select(bitmap,rank))
                        prefix+=c

    def test_rotated_priority_is_biased(self):
        active={0,1,3};chosen=[]
        for start in range(4):chosen.append(next((start+i)%4 for i in range(4) if (start+i)%4 in active))
        self.assertEqual(Counter(chosen),Counter({3:2,0:1,1:1}))

    def test_preselect_then_commit_is_same_transition(self):
        # For every bitmap and winner, choosing a rank before reading the
        # previous winner yields exactly the winner-hold transition kernel.
        for bitmap in product((0,1),repeat=5):
            active=[i for i,b in enumerate(bitmap) if b]
            for winner in range(5):
                distribution=Counter()
                for rank in range(max(1,len(active))):
                    selected=active[rank] if active else 0
                    result=winner if not active or bitmap[winner] else selected
                    distribution[result]+=Fraction(1,max(1,len(active)))
                if not active or bitmap[winner]:self.assertEqual(distribution,{winner:1})
                else:self.assertEqual(distribution,{i:Fraction(1,len(active)) for i in active})


if __name__=='__main__':unittest.main()
