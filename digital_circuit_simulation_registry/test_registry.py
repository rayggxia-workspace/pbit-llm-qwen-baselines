import copy
from pathlib import Path
import unittest
import registry


class RegistryChecks(unittest.TestCase):
    def setUp(self):
        self.r=registry.read(Path(__file__).parent/'templates/record.template.json')

    def test_pending_allowed(self):
        self.assertTrue(registry.validate(self.r))

    def test_functional_not_power(self):
        self.r['stages']['power']='calculated'
        with self.assertRaises(ValueError):registry.validate(self.r)

    def test_library_not_pt(self):
        self.r['evidence_level']='LIBRARY_EXTRACTION';self.r['stages']['power']='calculated'
        with self.assertRaises(ValueError):registry.validate(self.r)

    def test_need_hash_for_present(self):
        self.r['artifacts'][0]['present_at_registration']=True
        with self.assertRaises(ValueError):registry.validate(self.r)

    def test_missing_needs_reason(self):
        self.r['artifacts'][0].pop('missing_reason')
        with self.assertRaises(ValueError):registry.validate(self.r)

    def test_stages_separate(self):
        self.r['stages'].pop('sta')
        with self.assertRaises(ValueError):registry.validate(self.r)

    def test_members_need_independent_sha(self):
        self.r['artifacts'][0]['member']='foo/summary.json'
        with self.assertRaises(ValueError):registry.validate(self.r)

    def test_all_registered(self):
        self.assertGreaterEqual(len(registry.records()),35)


if __name__=='__main__':unittest.main()
