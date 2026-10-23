"""Reject changed publication bindings without weakening frozen source hashes."""
import copy
import json
from pathlib import Path
import unittest

from .verify_gqa_public_receipts import fixed_git_sources


class PublishedSourceMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[3]
        cls.source = json.loads((cls.root / 'work/amlink1219/116/gqa_validation_v1/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        cls.mapping = json.loads((cls.root / 'work/jieruiz/55/round8/GQA_PUBLIC_SOURCE_MAP.json').read_text(encoding='utf-8'))

    def test_all_published_blobs_match_frozen_execution(self):
        fixed_git_sources(self.source, self.root, self.mapping)

    def test_changed_hash_is_rejected(self):
        mapping = copy.deepcopy(self.mapping)
        mapping['matched_files'][next(iter(mapping['matched_files']))]['sha256'] = '0' * 64
        with self.assertRaisesRegex(AssertionError, 'hash binding'):
            fixed_git_sources(self.source, self.root, mapping)

    def test_missing_file_is_rejected(self):
        mapping = copy.deepcopy(self.mapping)
        mapping['matched_files'].pop(next(iter(mapping['matched_files'])))
        with self.assertRaisesRegex(AssertionError, 'source closure'):
            fixed_git_sources(self.source, self.root, mapping)

    def test_wrong_published_blob_is_rejected(self):
        mapping = copy.deepcopy(self.mapping)
        mapping['matched_files']['architecture_tlm/cycle_v1/run_gqa.py']['commit'] = mapping['published_ancestor_of']
        with self.assertRaisesRegex(AssertionError, 'source differs'):
            fixed_git_sources(self.source, self.root, mapping)
