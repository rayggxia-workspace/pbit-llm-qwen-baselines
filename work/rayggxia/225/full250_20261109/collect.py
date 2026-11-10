"""Collect completed immutable probability outputs; verify original bytes."""
from pathlib import Path
import hashlib,json,sys,datetime
H=Path(__file__).resolve().parent;ROOT=H.parents[3];WS=ROOT.parents[1]
sys.path.insert(0,str(WS/'local_tools/paracloud_client'));import client
sha=lambda b:hashlib.sha256(b).hexdigest()
plan=json.loads((H/'UPLOAD_PLAN.json').read_bytes());remote=plan['root']
dest=WS/'project_archives/tlm28p250_full225_20261110';dest.mkdir(exist_ok=True)
records=[]
with client.connect(client.load_password()) as s:
    with s.open_sftp() as ftp:
        for case in ('pilot','seed17','seed503','seed1009'):
            folder=dest/case;folder.mkdir(exist_ok=True)
            files={}
            for n in ('SEAL.json','RESULT.json','BUDGET.json','VALIDATION.json'):
                path=remote+'/outputs/'+case+'/'+n
                with ftp.open(path,'rb') as f:raw=f.read()
                out=folder/n
                if out.exists():assert out.read_bytes()==raw
                else:out.write_bytes(raw)
                files[n]=dict(remote=path,local=str(out),bytes=len(raw),sha256=sha(raw))
            for n in ('EXIT.json','INVOCATION.json'):
                with ftp.open(remote+'/work/'+case+'/'+n,'rb') as f:raw=f.read()
                out=folder/n
                if out.exists():assert out.read_bytes()==raw
                else:out.write_bytes(raw)
                files[n]=dict(local=str(out),bytes=len(raw),sha256=sha(raw))
            seal=json.loads((folder/'SEAL.json').read_bytes());result=json.loads((folder/'RESULT.json').read_bytes())
            budget=json.loads((folder/'BUDGET.json').read_bytes());exit_=json.loads((folder/'EXIT.json').read_bytes())
            assert seal['status']==result['status']=='completed' and exit_['exit_code']==0
            for n,h in seal['files_sha256'].items():assert files[n]['sha256']==h
            assert json.loads((folder/'VALIDATION.json').read_bytes())['status']=='PASS'
            if case!='pilot':assert result['scope']=='full' and result['layers']==36 and result['head_probe_rows'] is None
            records.append(dict(case=case,files=files,time_ms=result['time_ms'],job_id=exit_['job_id'],
                head_split=budget.get('lm_head_split'),area_mm2=budget.get('conditional_subsystem_area_mm2'),
                core_mJ=budget.get('conditional_subsystem_energy_mJ'),total_mJ=budget.get('conditional_total_energy_mJ_by_external_pJbit')))
data=dict(status='COLLECTED_SEALED_ORIGINALS',observed_UTC=datetime.datetime.utcnow().isoformat(),records=records)
(H/'COLLECTION.json').write_bytes((json.dumps(data,indent=2)+'\n').encode())
print(json.dumps({k:v for k,v in data.items() if k!='records'}))
for x in records:print(json.dumps({k:v for k,v in x.items() if k!='files'}))
