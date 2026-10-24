"""Standalone import boundary and sealed artifact verification."""
import hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[3]
BASE='fae12982e0a92dea1f81648a5eeee148974c4a87'
SOURCE='d6d33995754fcdcea99286e4ce43f91647aa231a'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def main():
 assert not git('diff','--name-only','--diff-filter=D',BASE,'HEAD').strip()
 imported=json.loads((ROOT/'work/jieruiz/179/IMPORT_MANIFEST.json').read_text())
 changed={'architecture_tlm/unified_v6/'+x for x in ('config.py','model.py','run.py')}
 unchanged=[]
 for entry in imported['files']:
  p=entry['path'];original=git('show',SOURCE+':'+p)
  assert hashlib.sha256(original).hexdigest()==entry['sha256']
  if p not in changed:
   assert (ROOT/p).read_bytes()==original,p
   unchanged.append(p)
 artifacts=[]
 for p in (ROOT/'architecture_tlm/unified_v6/results').rglob('MANIFEST.json'):
  d=json.loads(p.read_text());assert d['status']=='completed'
  for name,expected in d['files'].items():
   assert hashlib.sha256((p.parent/name).read_bytes()).hexdigest()==expected
  artifacts.append(p.relative_to(ROOT).as_posix())
 r=dict(status='passed',unchanged_imports=unchanged,changed_imports=sorted(changed),
        no_base_file_deletions=True,sealed_manifests=artifacts,
        numerical_alignment='GU integer macro equivalence pending; no quality claim')
 (ROOT/'work/jieruiz/179/DELIVERY_AUDIT.json').write_bytes((json.dumps(r,indent=2)+'\n').encode())
 print('unchanged imports',len(unchanged),'sealed runs',len(artifacts),'no deletions')
if __name__=='__main__':main()
