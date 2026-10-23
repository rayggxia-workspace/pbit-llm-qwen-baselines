"""Recover verified uploaded object after failed pre-ref GET; no blob re-upload."""
from publish import api, git, save, PREFIX, BRANCH

assert api('GET', '/user')['login'] == 'jieruiz'
head = 'b8cc1daaec9bb46d992fb867dc05c117d1e4bd6f'
previous = '601104554e4aae0b4badcdda1984d0fc29b204c2'
assert git('rev-parse', 'HEAD').decode().strip() == head
remote = api('GET', PREFIX + '/git/commits/' + head)
assert remote['sha'] == head
assert remote['tree']['sha'] == git('rev-parse', head + '^{tree}').decode().strip()
assert [p['sha'] for p in remote['parents']] == [previous]
current = api('GET', PREFIX + '/git/ref/heads/' + BRANCH)['object']['sha']
assert current in (previous, head)
if current != head:
    result = api('PATCH', PREFIX + '/git/refs/heads/' + BRANCH, dict(sha=head, force=False))
    assert result['object']['sha'] == head
assert api('GET', PREFIX + '/git/ref/heads/' + BRANCH)['object']['sha'] == head
save('PUSH.json', dict(repo='rayggxia-workspace/pbit-llm-qwen-baselines', branch=BRANCH,
    head=head, previous=previous, exact_objects=True, recovered_after='read-only pre-ref GET RemoteDisconnected'))
print('RESULT_REF_RECOVERED ' + head)
