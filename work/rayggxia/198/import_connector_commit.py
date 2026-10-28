"""Import an unsigned connector-created commit only if its exact Git SHA matches."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import subprocess
import sys

p = Path(sys.argv[1])
d = json.loads(p.read_text(encoding='utf-8'))
assert d['verification']['reason'] == 'unsigned'
def ident(x, zone):
    stamp = int(datetime.fromisoformat(x['date'].replace('Z', '+00:00')).timestamp())
    return f"{x['name']} <{x['email']}> {stamp} {zone}"
prefix = 'tree ' + d['tree']['sha'] + '\n'
prefix += ''.join('parent ' + x['sha'] + '\n' for x in d['parents'])
zones = ['-0000'] + [f"{'-' if n < 0 else '+'}{abs(n)//60:02d}{abs(n)%60:02d}" for n in range(-720, 841, 15)]
matches = []
# REST normalizes time zones. Recover only a byte sequence verified by the Git SHA.
for za in zones:
    for zc in zones:
        for encoding in ['', 'encoding UTF-8\n']:
            body = prefix + 'author ' + ident(d['author'], za) + '\ncommitter ' + ident(d['committer'], zc) + '\n' + encoding + '\n' + d['message']
            for suffix in ['', '\n', '\n\n']:
                b = (body + suffix).encode('utf-8')
                s = hashlib.sha1(b'commit ' + str(len(b)).encode() + b'\0' + b).hexdigest()
                if s == d['sha']:
                    matches.append(b)
assert len(matches) == 1, 'Cannot reconstruct exact remote commit; do not update refs'
b = matches[0]
def git(*args, data=None):
    return subprocess.check_output(['git', *args], input=data).decode().strip()
assert git('write-tree') == d['tree']['sha'], 'Local staged tree must match remote'
old = git('rev-parse', 'HEAD')
assert old == d['parents'][0]['sha'], 'Only advance this checkout from its expected parent'
assert git('symbolic-ref', '--short', 'HEAD') == 'task/198-attention-compare'
assert git('hash-object', '-t', 'commit', '-w', '--stdin', data=b) == d['sha']
git('update-ref', 'HEAD', d['sha'], old)
git('update-ref', 'refs/remotes/workspace/task/198-attention-compare', d['sha'])
print(json.dumps({'imported_sha':d['sha'],'tree_equal':True}))
