"""Collect only completed sealed summaries from the authorized Issue186 run."""
import base64,gzip,hashlib,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
W8='--w8' in sys.argv;BF16='--bf16-8k' in sys.argv
REMOTE='/home/Hongjie_Zeng/projects/pbit-scheduling-issue186-20261025/'+('bf16_8k_bab9721d' if BF16 else 'w8_6b0df70b' if W8 else 'full_bab9721d')
SCRIPT=r'''import pathlib,json,hashlib,gzip,base64,sys
root=pathlib.Path("REMOTE");base=root/'results';files={};done=[];failed=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for folder in sorted(base.glob('case_*')):
 if (folder/'FAILURE.json').exists():failed.append(json.loads((folder/'FAILURE.json').read_text()))
 mf=folder/'MANIFEST.json'
 if not mf.exists():continue
 m=json.loads(mf.read_text());assert m['status']=='completed'
 for name in ['RESULT.json','RESULT_SUMMARY.json','EXECUTION.json']:
  p=folder/name;assert sha(p)==m['files'][name]['sha256'],str(p)
 for name in ['RESULT_SUMMARY.json','EXECUTION.json','MANIFEST.json']:
  files[folder.name+'/'+name]=base64.b64encode((folder/name).read_bytes()).decode()
 done.append({'index':int(folder.name[5:]),'case':m['case'],'manifest_sha256':sha(mf)})
result={'remote':str(root),'completed':done,'failed':failed,'files':files}
sys.stdout.buffer.write(gzip.compress(json.dumps(result).encode()))
'''.replace('REMOTE',REMOTE)
def main():
 r=json.loads(gzip.decompress(subprocess.check_output(['C:/Windows/System32/OpenSSH/ssh.exe','-F','C:/Users/86134/.ssh/lab-server-ai.ssh_config','lab-server-ai','/usr/bin/python3 -'],input=SCRIPT.encode())))
 out=ROOT/'architecture_tlm/unified_v6/results/scheduling_20261025'/('bf16_8k' if BF16 else 'corrected_w8' if W8 else 'full');out.mkdir(parents=True,exist_ok=True)
 for rel,data in r.pop('files').items():
  p=pathlib.PurePosixPath(rel)
  if len(p.parts)!=2 or not p.parts[0].startswith('case_') or p.parts[1] not in ('RESULT_SUMMARY.json','EXECUTION.json','MANIFEST.json'):raise ValueError('invalid collected path')
  dest=out.joinpath(*p.parts);dest.parent.mkdir(exist_ok=True);b=base64.b64decode(data)
  if dest.exists():
   if dest.read_bytes()!=b:raise ValueError('immutable result changed '+str(dest))
  else:dest.write_bytes(b)
 (ROOT/'work/jieruiz/186'/('BF16_8K_COLLECTION.json' if BF16 else 'W8_COLLECTION.json' if W8 else 'COLLECTION.json')).write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({'completed':len(r['completed']),'failed':len(r['failed']),'completed_names':[x['case']['name'] for x in r['completed']],'failures':[x['traceback'][-1200:] for x in r['failed']]}))
if __name__=='__main__':main()
