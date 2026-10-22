"""Verify the downloaded archive and copy auditable text artifacts unchanged."""
import hashlib
import io
import json
from pathlib import Path
import tarfile

here = Path(__file__).resolve().parent
repo = here.parents[3]
archive = here / 'rtl-contract-2764-results.tar.gz'
expected = (here / 'rtl-contract-2764-results.tar.gz.sha256').read_text(encoding='utf-8').split()[0]
actual = hashlib.sha256(archive.read_bytes()).hexdigest()
assert actual == expected
destination = repo / 'architecture_tlm/cycle_v1/results/rtl_contract_20261023'
destination.mkdir(parents=True, exist_ok=False)
with tarfile.open(archive, 'r:gz') as source:
    blobs = {}
    for member in source.getmembers():
        if member.isdir():
            continue
        assert member.isfile() and member.name.startswith('results/')
        relative = Path(member.name).relative_to('results')
        assert not relative.is_absolute() and '..' not in relative.parts
        blobs[relative.as_posix()] = source.extractfile(member).read()
report = json.loads(blobs['RTL_CONTRACT_VALIDATION.json'])
assert report['status'] == 'passed' and len(report['cases']) == 9
assert sum(c['checked_handshakes'] for c in report['cases']) == 252
for name, digest in report['artifact_sha256'].items():
    assert hashlib.sha256(blobs[name]).hexdigest() == digest, name
excluded = {}
for name, data in blobs.items():
    if name.endswith('.vvp'):
        excluded[name] = hashlib.sha256(data).hexdigest()
        continue
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
receipt = dict(host='10.129.164.156:21570', account='Weican_Chen', job_id='2764',
               archive_sha256=actual, verified_artifacts=len(report['artifact_sha256']),
               excluded_generated_binaries=excluded,
               original_archive='work/amlink1219/116/rtl/rtl-contract-2764-results.tar.gz',
               remote_root='/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/rtl-contract-2764/results')
(destination / 'LOCAL_RECEIPT.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'archive_sha256': actual, 'verified_artifacts': len(report['artifact_sha256']),
                  'destination': str(destination), 'iverilog': report['iverilog_version']}))
