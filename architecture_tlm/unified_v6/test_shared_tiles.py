"""Issue186 finite ownership and shared digital/SC schedule checks."""
import unittest
from .model import FullDecode
from .test_memory_pipeline_contracts import case

class SharedTileContracts(unittest.TestCase):
 def make(self, mode='w8', double=True):
  c,m=case(double_buffer=double);c.update(schedule_policy='shared_tiles',macs_per_cycle=1,trace_event_limit=100000)
  c['ffn'].update(mode=mode,prefetch_across_input_groups=True)
  return FullDecode(c,m)
 def test_digital_tail_bytes_work_and_finite_lifecycle(self):
  d=self.make();t=d.matrix(0,'L0/gu');r=d.tile_pipeline.report()['digital'];rows=r['records']
  self.assertGreater(len(rows),2);self.assertEqual(sum(x['bytes'] for x in rows),d.matrix_info['L0/gu']['bytes'])
  self.assertEqual(r['counts']['issued'],r['counts']['retired']);self.assertFalse(r['pending']);self.assertFalse(r['active'])
  self.assertEqual(d.e.actions['bf16_mac'],d.h*2*d.F);self.assertEqual(t,rows[-1]['retire_done_ns'])
  self.assertGreater(r['counts']['issue_during_previous_compute'],0)
  for i,row in enumerate(rows):
   self.assertLessEqual(row['dma_done_ns'],row['fill_done_ns']);self.assertLessEqual(row['fill_done_ns'],row['compute_start_ns'])
   self.assertLessEqual(row['compute_done_ns'],row['retire_done_ns']);self.assertLessEqual(row['bytes'],r['operand_capacity_bytes'])
   if i:self.assertGreaterEqual(row['fill_start_ns'],rows[i-1]['retire_done_ns'])
   if i>=2:self.assertGreater(row['generation'],rows[i-2]['generation']);self.assertGreaterEqual(row['dma_issue_ns'],rows[i-2]['retire_done_ns'])
 def test_single_buffer_never_prefetches_during_compute(self):
  d=self.make(double=False);d.matrix(0,'L0/gu');r=d.tile_pipeline.report()['digital']
  self.assertEqual(r['counts'].get('issue_during_previous_compute',0),0)
  for a,b in zip(r['records'],r['records'][1:]):self.assertGreaterEqual(b['dma_issue_ns'],a['retire_done_ns'])
 def test_buffer_policy_preserves_work_and_bytes(self):
  runs=[]
  for double in (False,True):
   d=self.make(double=double);t=d.matrix(0,'L0/gu');runs.append((t,dict(d.dram.traffic),dict(d.mem.traffic),d.e.actions['bf16_mac']))
  self.assertEqual(runs[0][1:],runs[1][1:]);self.assertLess(runs[1][0],runs[0][0])
 def test_sc_shared_wrapper_preserves_old_timing_and_actions(self):
  runs=[]
  for policy in ('legacy','shared_tiles'):
   c,m=case();c.update(schedule_policy=policy);c['ffn']['prefetch_across_input_groups']=True
   d=FullDecode(c,m);t=d.ffn_latest.gate_up(0,0);runs.append((t,dict(d.metadata),dict(d.e.actions),dict(d.dram.traffic),dict(d.mem.traffic)))
  self.assertEqual(runs[0],runs[1])
 def test_ticket_ownership_capacity_and_premature_fill(self):
  d=self.make();p=d.tile_pipeline
  with self.assertRaises(ValueError):p.issue(0,'L0/gu',0,d.c['weight_chunk_bytes']+1,'digital')
  a=p.issue(0,'L0/gu',0,64,'digital')
  with self.assertRaises(ValueError):p.issue(0,'L0/gu',64,64,'digital')
  with self.assertRaises(ValueError):p.fill(0,dict(a))
  loaded,_=p.fill(0,a);p.compute(a,loaded,loaded+100)
  b=p.issue(loaded,'L0/gu',64,64,'digital')
  with self.assertRaises(ValueError):p.fill(loaded,b)
  with self.assertRaises(ValueError):p.retire(a,loaded)
  p.retire(a,loaded+100);loaded,_=p.fill(loaded+100,b);p.compute(b,loaded,loaded+10);p.retire(b,loaded+10)
  self.assertFalse(p.report()['digital']['active'])
 def test_block_scale_and_partial_storage_are_counted(self):
  d=self.make();d.matrix(0,'L0/gu');groups=(d.h+63)//64;n=2*d.F
  self.assertEqual(d.e.actions['weight_scale_op'],n*groups)
  self.assertEqual(d.e.actions['digital_block_partial_write_byte'],n*groups*4)
  self.assertEqual(d.e.actions['digital_block_partial_read_byte'],n*groups*4)
  self.assertGreater(d.digital_partial_peak,0)
  # Row-dot scaling is generally invalid: two input groups with q=1 and
  # scales 1 and 2 need 64+128=192, not an unscaled row dot of 128.
  self.assertEqual(sum([64*1,64*2]),192)
 def test_local_operand_capacity_is_not_implicit(self):
  c,m=case();c.update(schedule_policy='shared_tiles',digital_operand_bytes=1)
  with self.assertRaisesRegex(ValueError,'operand storage'):FullDecode(c,m)
if __name__=='__main__':unittest.main()
