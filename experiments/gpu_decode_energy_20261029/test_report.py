"""Regress the observed Kineto duplicate-range bug and sealed artifact checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from build_report import cpu_kernel_rows,verify

class ReportTest(unittest.TestCase):
    def test_cuda_annotation_must_not_overwrite_kernel_total(self):
        cpu={'category':'Norm','CPU_range_ms_per_decode':7.,'GPU_kernel_ms_per_decode':.7}
        cuda={'category':'Norm','CPU_range_ms_per_decode':0.,'GPU_kernel_ms_per_decode':6.}
        self.assertEqual(cpu_kernel_rows([cpu,cuda],['Norm'])['Norm']['GPU_kernel_ms_per_decode'],.7)
        self.assertEqual(cpu_kernel_rows([cuda,cpu],['Norm'])['Norm']['GPU_kernel_ms_per_decode'],.7)

    def test_ambiguous_duplicate_cpu_category_rejected(self):
        row={'category':'Norm','CPU_range_ms_per_decode':1.}
        with self.assertRaisesRegex(AssertionError,'duplicate'):cpu_kernel_rows([row,row],['Norm'])

    def test_missing_category_rejected(self):
        with self.assertRaisesRegex(AssertionError,'missing'):cpu_kernel_rows([],['Norm'])

    def test_modified_sealed_result_rejected(self):
        # Explicit dir also keeps this test inside its task directory on server.
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as task:
            root=Path(task);data=b'{"value":1}\n';(root/'result.json').write_bytes(data)
            manifest={'result.json':{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}}
            raw=json.dumps(manifest).encode();(root/'ARTIFACT_MANIFEST.json').write_bytes(raw)
            (root/'COMPLETED.json').write_text(json.dumps({'status':'completed','contexts':[2048,8192],
                'artifacts_manifest_sha256':hashlib.sha256(raw).hexdigest()}),encoding='utf-8')
            verify(root)
            (root/'result.json').write_bytes(b'{"value":2}\n')
            with self.assertRaises(AssertionError):verify(root)

if __name__=='__main__':unittest.main()
