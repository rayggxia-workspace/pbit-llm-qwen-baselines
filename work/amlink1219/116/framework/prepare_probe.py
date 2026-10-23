"""Record the exact compiler compatibility edit and install the native test extension."""
import hashlib
import json
import os
from pathlib import Path
import shutil

root = Path('/home/Weican_Chen/projects/tlm-cycle-issue116-20261023').resolve(strict=True)
assert root.owner() == 'Weican_Chen'
source = root / 'ONNXim-archive'
header = source / 'extern/ramulator_custom/src/StatType.h'
assert header.resolve().is_relative_to(root)
before = header.read_bytes()
if b'#include <cstdint>' not in before:
    assert b'#include <cstdlib>' in before
    after = before.replace(b'#include <cstdlib>', b'#include <cstdlib>\n#include <cstdint>', 1)
    backup = root / 'StatType.h.before-cstdint'
    if not backup.exists():
        backup.write_bytes(before)
    header.write_bytes(after)
else:
    after = before
gtest = source / 'build/tests/lib/src/GoogleTest/googletest/src/gtest-death-test.cc'
gtest_before = gtest.read_bytes()
assert b'static bool StackGrowsDown()' in gtest_before
gtest_after = gtest_before.replace(b'  int dummy;\n', b'  int dummy = 0;\n')
backup = root / 'gtest-death-test.cc.before-init'
if not backup.exists():
    backup.write_bytes(gtest_before)
gtest.write_bytes(gtest_after)
probe = root / 'PBitThresholdTransportProbeTest.cc'
target = source / 'tests/operatons/PBitThresholdTransportProbeTest.cc'
assert target.resolve().is_relative_to(root)
shutil.copyfile(probe, target)
receipt = {
    'job_id': os.environ['SLURM_JOB_ID'],
    'base_commit': 'a1e86296e080fa1c82f8ad3f1b6de1079c192afc',
    'compatibility_edit': 'extern/ramulator_custom/src/StatType.h: add explicit <cstdint> for GCC 13',
    'header_before_sha256': hashlib.sha256(before).hexdigest(),
    'header_after_sha256': hashlib.sha256(after).hexdigest(),
    'probe_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'probe_target': str(target),
    'gtest_compatibility_edit': 'initialize stack-address probe dummy; preserve address comparison',
    'gtest_before_sha256': hashlib.sha256(gtest_before).hexdigest(),
    'gtest_after_sha256': hashlib.sha256(gtest_after).hexdigest(),
}
(root / f'framework-source-edits-{os.environ["SLURM_JOB_ID"]}.json').write_text(
    json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps(receipt))
