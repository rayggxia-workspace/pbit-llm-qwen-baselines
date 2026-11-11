"""Replay supplied verification in an isolated small snapshot;keep originals."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3];PROJECT=ROOT.parents[1]
REL=Path('architecture_tlm/module_handoff/attention_score_front_compare_20261108/local_integration_A')
SOURCE=PROJECT/REL;SANDBOX=HERE/'adapter_review_runtime'
if SANDBOX.exists():raise RuntimeError('Review snapshot exists;read receipt,do not blindly rerun')
provided=(SOURCE/'VALIDATION.json').read_bytes();m=json.loads(provided);sources=m['sources']
def sha(b):return hashlib.sha256(b).hexdigest()
assert m['status']=='PASS' and m['queries']==192 and m['legacy_all_valid_queries']==27
SANDBOX.mkdir();index={}
for rel,identity in sources.items():
 p=PROJECT/rel;b=p.read_bytes();assert sha(b)==identity['sha256'] and len(b)==identity['bytes'],rel
 q=SANDBOX/rel;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b);index[rel]=identity
(SANDBOX/'INPUTS.json').write_bytes((json.dumps(dict(provided_result_sha256=sha(provided),sources=index),indent=2)+'\n').encode())
env=dict(__import__('os').environ);env.update(PYTHONDONTWRITEBYTECODE='1')
p=subprocess.run([sys.executable,'-X','utf8','-B',str(SANDBOX/REL/'verify.py')],cwd=SANDBOX,env=env,
 stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
(HERE/'ADAPTER_REVIEW_STDOUT.txt').write_bytes(p.stdout);(HERE/'ADAPTER_REVIEW_STDERR.txt').write_bytes(p.stderr)
assert p.returncode==0,p.stderr.decode(errors='replace')
new=(SANDBOX/REL/'VALIDATION.json').read_bytes();actual=json.loads(new)
assert new==provided,'Preserve both receipts;inspect scope/source differences'
assert actual['winner_recurrence_outputs']==6912 and not actual['RTL_simulated'] and not actual['new_PPA']
assert actual['contract']['all_valid_only_old_backend'] and not actual['contract']['integrated_sampler_replacement_ready']
assert (SOURCE/'VALIDATION.json').read_bytes()==provided
receipt=dict(status='PASS_ISOLATED_CPU_REPLAY_IDENTICAL_RECEIPT',sources_SHA_verified=len(index),
 provided_result_sha256=sha(provided),replayed_result_sha256=sha(new),originals_unchanged=True,
 summary={k:actual[k] for k in ('queries','lanes','legacy_all_valid_queries','winner_recurrence_outputs')},
 general_mask_backend_supported=False,integrated_PPA_ready=False,new_RTL_PT_GPU_PPL=False,
 source_directory=str(SOURCE),isolated_snapshot=str(SANDBOX),command=[sys.executable,'-X','utf8','-B','verify.py'])
(HERE/'ADAPTER_REVIEW.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode());print(json.dumps(receipt))
