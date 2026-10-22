import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from architecture_tlm.inspector.build import ROOT,BASE,EXEC,audit_case,case_record,source


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.path=ROOT/'architecture_tlm/unified_v6/results/qwen_20261022_v2/qwen/qwen_L2048_seed0_sc_screen_rejection.json'
        self.raw=json.loads(self.path.read_text(encoding='utf-8'))

    def failures(self,r):return [x['name'] for x in audit_case(r,'fixture') if not x['passed']]

    def test_untouched_case_passes(self):self.assertEqual(self.failures(self.raw),[])

    def test_phase_error_is_visible(self):
        r=copy.deepcopy(self.raw);r['phase_ns']['embedding']+=100
        self.assertIn('阶段时间守恒',self.failures(r))

    def test_overlap_is_visible(self):
        r=copy.deepcopy(self.raw);r['SRAM']['layout']['weight_pong']['address']=1
        self.assertIn('SRAM容量及不交叠',self.failures(r))

    def test_sampler_rejections_not_free(self):
        r=copy.deepcopy(self.raw);r['actions']['sampler_proposal_frames']-=1
        self.assertIn('采样提议/接受守恒',self.failures(r))

    def test_cycle_and_lane_work_are_different(self):
        r=self.raw;period=1e9/r['config']['core_hz']
        self.assertEqual(r['actions']['sampler_macro_active_cycles']*period,r['resource_busy_ns']['sampler'])
        self.assertNotEqual(r['random_interface']['demands']['embedded_source_cycles']*period,r['resource_busy_ns']['sampler'])

    def test_sampling_tiles_are_conserved(self):
        r=copy.deepcopy(self.raw);r['FFN_activity']['SC_64x64_tiles']+=1
        self.assertIn('FFN tile/乘积次数',self.failures(r))

    def test_wrong_evidence_is_rejected(self):
        r=copy.deepcopy(self.raw);r['metrics']['full_physical_energy_J']=0
        self.assertIn('未知证据保留null',self.failures(r))

    def test_committed_anchor_matches_git_bytes(self):
        s=source('architecture_tlm/unified_v6/model.py','FullDecode.matrix_sc')
        raw=subprocess.check_output(['git','show',BASE+':'+s['path']],cwd=ROOT)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),s['sha256'])
        self.assertIn('def matrix_sc(',raw.decode().splitlines()[s['line']-1])

    def test_preview_prefix_never_claims_complete(self):
        c=case_record(self.path)
        self.assertEqual(c['saved_event_count'],80)
        self.assertEqual(len(c['events']),10)
        self.assertGreater(c['event_count'],len(c['events']))
        self.assertTrue(c['trace_truncated'])

    def test_all_archived_files_are_bound(self):
        data=json.loads((Path(__file__).parent/'snapshot.json').read_text(encoding='utf-8'))
        self.assertEqual(len(data['cases']),52)
        self.assertEqual(len({c['id'] for c in data['cases']}),52)
        for c in data['cases']:
            self.assertEqual(hashlib.sha256((ROOT/c['path']).read_bytes()).hexdigest(),c['sha256'])
            self.assertEqual(c['execution'],EXEC)
            self.assertTrue(all(x['passed'] for x in c['checks']))


if __name__=='__main__':unittest.main()
