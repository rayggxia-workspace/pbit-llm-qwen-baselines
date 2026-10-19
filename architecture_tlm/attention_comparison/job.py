"""One CPU allocation: verify immutable snapshot, run tests, then finite TLM cases."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,pwd,subprocess,sys,traceback

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    home=Path('/home/Weican_Chen');snapshot=a.snapshot.resolve();output=a.output.resolve()
    assert pwd.getpwuid(os.getuid()).pw_name=='Weican_Chen'
    assert Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()==home
    assert snapshot.is_relative_to(home) and output.is_relative_to(home)
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    assert os.environ.get('SLURM_JOB_ID','').isdigit()
    output.mkdir(parents=True,exist_ok=False)
    state=dict(job_id=int(os.environ['SLURM_JOB_ID']),host=os.uname().nodename,allocation=os.environ.get('SLURM_JOB_NODELIST'),python=sys.version,device='CPU',cuda_visible_devices=os.environ['CUDA_VISIBLE_DEVICES'],started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='running')
    def save():
        (output/'job_state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        manifest=json.loads((snapshot/'source_manifest.json').read_text(encoding='utf-8'))
        for r in manifest['files']:
            path=(snapshot/r['path']).resolve();assert path.is_relative_to(snapshot)
            assert digest(path)==r['sha256'],r['path']
        state['source_commit']=manifest['code_commit'];state['source_files_verified']=len(manifest['files']);save()
        commands=[('tests',[sys.executable,'-X','utf8','-m','unittest','discover','-s','architecture_tlm/attention_comparison','-p','test_evaluate.py','-v']),
                  ('batch',[sys.executable,'-X','utf8','architecture_tlm/attention_comparison/evaluate.py','--batch-config','architecture_tlm/attention_comparison/comparison_config.json','--source-commit',manifest['code_commit'],'--output',str(output/'results')])]
        for name,command in commands:
            state['stage']=name;save()
            with (output/(name+'.stdout.txt')).open('w',encoding='utf-8') as stdout,(output/(name+'.stderr.txt')).open('w',encoding='utf-8') as stderr:
                result=subprocess.run(command,cwd=snapshot,stdout=stdout,stderr=stderr,timeout=1500)
            state[name+'_command']=command;state[name+'_exit_code']=result.returncode;save()
            if result.returncode:raise RuntimeError(name+' failed; inspect persisted stage logs')
        state['status']='completed';state['exit_code']=0
    except BaseException:
        state['status']='failed';state['exit_code']=1;state['error']=traceback.format_exc()
        raise
    finally:
        state['finished_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
        records=[dict(path=str(path.relative_to(output)),bytes=path.stat().st_size,sha256=digest(path)) for path in sorted(output.rglob('*')) if path.is_file() and path.name!='RESULT_MANIFEST.json']
        (output/'RESULT_MANIFEST.json').write_text(json.dumps(dict(source_commit=state.get('source_commit'),job_id=state['job_id'],files=records),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(state,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
