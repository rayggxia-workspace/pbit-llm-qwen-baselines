"""Independent arithmetic and storage checks for the proposal, not PPL/RTL."""
from collections import Counter
from fractions import Fraction
from itertools import product
import random
import unittest
from address_plan import AddressSampler, StripeLayout, count_pulses


class AddressPlanTests(unittest.TestCase):
    def test_exact_ticket_histogram_with_different_scales(self):
        s=AddressSampler([1,2,0,3,1],[0,1,7,0,2],[1,-1,1,1,-1],group=2)
        counts=Counter(s.select_ticket(i) for i in range(s.total))
        self.assertEqual([counts[i] for i in range(5)],list(s.masses))
        self.assertNotIn(2,counts)

    def test_full_one_and_zero_input(self):
        s=AddressSampler([0,256],[0,0],[1,-1])
        r=s.draw(128,random.Random(17))
        self.assertEqual(r['entries'],[dict(input_index=1,count=128,sign=-1,original_input_group=0)])
        z=AddressSampler([0,0],[-2,3],[1,1]).draw(64,random.Random(19))
        self.assertTrue(z['zero_input']);self.assertEqual(z['random_bits'],0)
        self.assertEqual(z['effective_samples'],0);self.assertEqual(z['entries'],[])

    def test_unbiased_quantized_linear_estimator_exhaustively(self):
        s=AddressSampler([1,2,3],[-2,0,-1],[1,-1,1],fractional_bits=2,group=2)
        w=[[2,-3,1],[-1,4,2]]
        unit=Fraction(2)**(s.minimum_exponent-s.fractional_bits)
        expected=[sum(unit*s.signs[i]*s.masses[i]*row[i]
                      for i in range(3)) for row in w]
        observed=[Fraction(0),Fraction(0)]
        for tickets in product(range(s.total),repeat=2):
            counts=Counter(s.select_ticket(t) for t in tickets)
            for o,row in enumerate(w):
                y=unit*Fraction(s.total,2)*sum(s.signs[i]*c*row[i] for i,c in counts.items())
                observed[o]+=y/Fraction(s.total**2)
        self.assertEqual(observed,expected)

    def test_rejected_ticket_is_counted_not_modulo_mapped(self):
        class Bits:
            def __init__(self):self.values=iter([3,2,3,0])
            def getrandbits(self,n):assert n==2;return next(self.values)
        s=AddressSampler([1,2],[0,0],[1,1],group=1)
        r=s.draw(2,Bits())
        self.assertEqual(r['proposals'],4);self.assertEqual(r['random_bits'],8)
        self.assertEqual([(x['input_index'],x['count']) for x in r['entries']],[(0,1),(1,1)])

    def test_qwen_shapes_and_transfer_units(self):
        gu=StripeLayout(2560,9728,projections=2)
        wd=StripeLayout(9728,2560,base=gu.storage_bytes)
        self.assertEqual((gu.strips,gu.packet_bytes,gu.storage_bytes),(19,1024,49807360))
        self.assertEqual((wd.strips,wd.packet_bytes,wd.storage_bytes),(5,512,24903680))
        e=[dict(input_index=7,count=2,sign=-1),dict(input_index=500,count=1,sign=1)]
        for layout in [gu,wd]:
            reads=layout.reads(e)
            self.assertEqual(len(reads),layout.strips*2)
            self.assertEqual({r['input_index'] for r in reads},{7,500})
            self.assertTrue(all(r['address']%512==0 for r in reads))

    def test_layout_reconstructs_signed_weights_and_tail_padding(self):
        layout=StripeLayout(5,7,projections=2,output_chunk=4)
        memory=bytearray(layout.storage_bytes)
        locations=set()
        def value(p,o,i):return p*35+o*5+i-35
        for p,o,i in product(range(2),range(7),range(5)):
            a=layout.address(i,o,p);self.assertNotIn(a,locations);locations.add(a)
            memory[a]=value(p,o,i)&255
        entries=[dict(input_index=4,count=1,sign=-1),dict(input_index=1,count=3,sign=1)]
        reads=layout.reads(entries)
        for r in reads:
            for p,lane in product(range(2),range(4)):
                raw=memory[r['address']+p*4+lane];v=raw if raw<128 else raw-256
                if lane<r['valid_outputs']:
                    self.assertEqual(v,value(p,r['output_start']+lane,r['input_index']))
                else:self.assertEqual(raw,0)
        self.assertGreater(sum(r['bytes'] for r in reads),sum(r['useful_bytes'] for r in reads))

    def test_count_pulses_equal_signed_weighted_count(self):
        counts=[0,3,1,2];sign=[1,-1,1,-1];weight=[7,-2,4,3]
        expected=sum(c*s*w for c,s,w in zip(counts,sign,weight))
        pulses=list(count_pulses(counts))
        observed=sum(sum(b*s*w for b,s,w in zip(bits,sign,weight)) for bits in pulses)
        self.assertEqual(len(pulses),3);self.assertEqual(observed,expected)

    def test_original_weight_scale_groups_survive_compaction(self):
        entries=[dict(input_index=i,count=1,sign=1) for i in [1,63,64,2559]]
        read=StripeLayout(2560,9728,projections=2).reads(entries)
        self.assertEqual({(r['input_index'],r['original_input_group']) for r in read},
                         {(1,0),(63,0),(64,1),(2559,39)})

    def test_sampler_tree_group_does_not_change_weight_scale_groups(self):
        s=AddressSampler([0]*64+[1],[0]*65,[1]*65,group=8)
        e=s.draw(1,random.Random(17))['entries'][0]
        self.assertEqual((e['input_index'],e['original_input_group']),(64,1))

    def test_invalid_inputs(self):
        for action in [lambda:AddressSampler([257],[0],[1]),
                       lambda:AddressSampler([1],[.5],[1]),
                       lambda:StripeLayout(2,3,base=1),
                       lambda:StripeLayout(2,3).reads([dict(input_index=2,count=1,sign=1)]),
                       lambda:list(count_pulses([-1]))]:
            with self.assertRaises(ValueError):action()


if __name__=='__main__':unittest.main()
