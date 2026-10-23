"""Recover receipts for an already pushed ref; never repeats GitHub writes."""
import control,json,subprocess
ROOT=control.ROOT; TREE=ROOT.parents[1]/'workspace_projects/sq157'
intent=json.loads((ROOT/'PUSH_INTENT.json').read_text(encoding='utf-8'))
s=control.client();base='https://api.github.com/repos/'+control.REPO+'/'
def get(path):
    r=s.get(base+path,timeout=45);r.raise_for_status();return r.json()
ref=get('git/ref/heads/task/157-sparq-qwen3');pr=get('pulls/163')
assert ref['object']['sha']==intent['head']
assert pr['head']['ref']=='task/157-sparq-qwen3' and pr['head']['repo']['full_name']==control.REPO
subprocess.run(['git','-C',str(TREE),'merge-base','--is-ancestor',pr['head']['sha'],intent['head']],check=True)
synced=pr['head']['sha']==intent['head']
value=dict(head=intent['head'],ref_verified=True,pr=pr['html_url'],pr_number=163,
           pr_head_verified=intent['head'] if synced else None,pr_head_observed=pr['head']['sha'],
           pr_projection_synced=synced,files=intent['files'],state='draft_open_unmerged' if synced else 'ref_uploaded_pr_projection_pending',
           recovery='read-only verification; no repeated push')
control.save('PUBLICATION.json',value)
control.save('WATCH_PUBLICATION_RECOVERY_RECEIPT.json',value)
print(json.dumps(dict(head=value['head'],pr_projection_synced=synced)))
