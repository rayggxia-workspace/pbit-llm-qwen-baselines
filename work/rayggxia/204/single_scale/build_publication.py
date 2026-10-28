"""Verify staged blobs and frozen input packages; prepare connector payload."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def main():
 index={}
 for x in git('ls-files','--stage','-z').split(b'\0'):
  if not x:continue
  meta,path=x.split(b'\t',1);mode,h,stage=meta.decode().split();assert stage=='0';index[path.decode()]=(mode,h)
 paths=git('diff','--cached','--name-only','--diff-filter=ACM','-z').decode().split('\0');files=[]
 for path in filter(None,paths):
  assert '/private/' not in path and '__pycache__' not in path and not path.endswith(('.zip','.gz','.vcd','.db'))
  b=(ROOT/path).read_bytes();mode,h=index[path];assert blob(b)==h,path
  files.append({'path':path,'mode':mode,'type':'blob','content':b.decode('utf-8'),'sha':h})
 verified=0
 for p in sorted((HERE/'private').glob('matrix204_single_v*.zip')):
  with zipfile.ZipFile(p) as z:
   m=json.loads(z.read(p.stem+'/EXECUTION_MANIFEST.json'))
   for n,h in m['files'].items():
    path='architecture_tlm/matrix_single_scale_20261028/'+n;b=z.read(p.stem+'/'+n)
    assert hashlib.sha256(b).hexdigest()==h and blob(b)==index[path][1],(p.name,n)
    verified+=1
 payload={'parent':git('rev-parse','HEAD').decode().strip(),'base_tree':git('rev-parse','HEAD^{tree}').decode().strip(),
  'tree':git('write-tree').decode().strip(),'files':files,'verified_frozen_input_blobs':verified}
 target=HERE/'private/publish_parts';target.mkdir(exist_ok=True)
 data=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
 for i in range(0,len(data),20000):(target/('%04d.jsonpart'%(i//20000))).write_text(data[i:i+20000],encoding='utf-8',newline='\n')
 print(json.dumps({'files':len(files),'payload_characters':len(data),'parts':(len(data)+19999)//20000,'tree':payload['tree'],'parent':payload['parent'],'verified_frozen_input_blobs':verified}))
if __name__=='__main__':main()
