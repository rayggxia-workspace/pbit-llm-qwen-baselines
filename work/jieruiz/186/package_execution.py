import pathlib,subprocess,hashlib,json,tarfile,sys,datetime
root=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root))
from architecture_tlm.unified_v6.run import source_record

def main():
 work=root/'work/jieruiz/186';record=source_record();head=record['commit']
 for rel in ['work/jieruiz/186/run_schedule_case.py','work/jieruiz/186/RUN_MATRIX.json']:
  p=root/rel;data=p.read_bytes();assert subprocess.check_output(['git','show',head+':'+rel],cwd=root)==data
  record['files'][rel]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
 record['scope']='frozen Issue186 synthetic full-model schedule; no model weights or test corpus'
 manifest=work/('SOURCE_'+head[:8]+'.json')
 manifest.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 package=work/('execution_'+head[:8]+'.tar.gz')
 with tarfile.open(package,'x:gz') as tar:
  for rel in record['files']:tar.add(root/rel,arcname=rel,recursive=False)
  tar.add(manifest,arcname='work/jieruiz/186/SOURCE.json')
 print(json.dumps(dict(commit=head,files=len(record['files']),manifest=str(manifest),package=str(package),bytes=package.stat().st_size,sha256=hashlib.sha256(package.read_bytes()).hexdigest())))
if __name__=='__main__':main()
