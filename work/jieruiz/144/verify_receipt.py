"""Read back only receipt delta; scientific 177-file verification is preserved."""
import base64
import hashlib
from publish import api, git, save, PREFIX, BRANCH, allowed

assert api('GET', '/user')['login'] == 'jieruiz'
head = git('rev-parse', 'HEAD').decode().strip()
assert api('GET', PREFIX + '/git/ref/heads/' + BRANCH)['object']['sha'] == head
base = 'b8cc1daaec9bb46d992fb867dc05c117d1e4bd6f'
files = git('diff', '--name-only', base, head).decode().splitlines()
checked = []
for path in files:
    assert allowed(path)
    oid = git('rev-parse', head + ':' + path).decode().strip()
    raw = git('show', head + ':' + path)
    remote = base64.b64decode(api('GET', PREFIX + '/git/blobs/' + oid)['content'])
    assert remote == raw
    checked.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest()))
pr = api('GET', PREFIX + '/pulls/147')
assert pr['head']['sha'] == head and not pr['draft'] and not pr['merged']
save('FINAL_RECEIPT_VERIFY.json', dict(status='PASS', head=head, scientific_head=base,
    scientific_verified_files=177, verified_receipt_files=checked, pr_ready=True))
print('FINAL_RECEIPT_PASS ' + head + ' files=' + str(len(checked)))
