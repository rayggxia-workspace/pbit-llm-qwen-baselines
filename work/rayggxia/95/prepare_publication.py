"""Prepare explicit staged UTF-8 files for authenticated GitHub connector upload.

No credentials, Git writes, or network requests. Refuses paths outside Issue95 scope.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


paths = git('diff', '--cached', '--name-only', '-z').decode('utf-8').strip('\0').split('\0')
elements = []
for path in paths:
    if not path or not (path.startswith('architecture_tlm/random_service/') or
                        path.startswith('work/rayggxia/95/') or
                        path in ('architecture_tlm/parallel_sampler_v5.py', 'progress/rayggxia/STATUS.md')):
        raise ValueError('out of scope staged path: '+path)
    data = git('show', ':'+path)
    if data != (ROOT/path).read_bytes():
        raise ValueError('staged and working bytes differ: '+path)
    elements.append(dict(path=path,mode='100644',type='blob',content=data.decode('utf-8')))
payload = dict(base_tree_sha=git('rev-parse','HEAD^{tree}').decode().strip(), tree_elements=elements)
(WORK/'publish_payload.json').write_text(json.dumps(payload,ensure_ascii=True),encoding='ascii',newline='\n')
print(json.dumps(dict(files=len(elements), bytes=(WORK/'publish_payload.json').stat().st_size,
                     tree=git('write-tree').decode().strip()),indent=2))
