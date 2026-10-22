"""Validate this small published delivery using only the Python standard library."""
from pathlib import Path
import ast, hashlib, json, re, subprocess

ROOT=Path(__file__).resolve().parents[3]
WORK=ROOT/'work/amlink1219/90'
DOC=ROOT/'maintenance/llm_env_4090_20261022'
SOURCE_STAGES=['SOURCE_MANIFEST.json','COMPAT_STAGE.json','GPU_V2_STAGE.json','EXPORT_STAGE.json','EXPORT_V2_STAGE.json','RECOVERY_STAGE.json','RECOVERY_V2_STAGE.json']

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    verified={}
    for name in SOURCE_STAGES:
        for item in json.loads((WORK/name).read_text(encoding='utf-8'))['files']:
            path=ROOT/item['path']
            assert path.is_file() and path.stat().st_size==item['bytes'],item['path']
            assert digest(path)==item['sha256'],item['path']
            verified[item['path']]=item['sha256']
    result=json.loads((WORK/'RESULT_MANIFEST.json').read_text(encoding='utf-8'))
    for item in result['published_files']:
        path=ROOT/item['path']
        assert path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],item['path']
    freeze=(DOC/'pip_freeze.txt').read_text(encoding='utf-8').splitlines()
    assert len(freeze)==94 and all('==' in line for line in freeze)
    assert digest(DOC/'pip_freeze.txt')==result['same_freeze_sha256']=='636ea0599fc983e7c003c3a8881aefa2f05d8167f2877dcab8992dfc3f145ae5'
    gpu=[]
    for name in ['A_GPU_V2_SUMMARY.json','B_GPU_V2_SUMMARY.json']:
        public=json.loads((WORK/name).read_text(encoding='utf-8'))
        report=next(iter(public['reports'].values()))
        assert report['status']=='passed' and len(report['checks'])==6
        assert all(item['status']=='passed' for item in report['checks'])
        details=report['checks'][2]['details']
        assert details['state_roundtrip']['parameters']==27 and details['state_roundtrip']['buffers']==3
        assert details['roundtrip_logits_max_abs_error']==0.0
        assert details['roundtrip_logits_tolerance']=={'rtol':0.001,'atol':0.001}
        gpu.append(report['slurm_job_id'])
    for name in ['A_CPU_RECOVERY_SUMMARY.json','B_CPU_SUMMARY.json']:
        public=json.loads((WORK/name).read_text(encoding='utf-8'))
        report=public['reports']['cpu_check_compat.json']
        assert report['status']=='passed' and len(report['checks'])==19
        assert all(item['status']=='passed' for item in report['checks'])
    ast_count=0;links=0
    forbidden=rb'162\.105\.201|10\.129\.164|[CE]:\\(?:Users|BaiduSyncdisk)|id_ed25519|known_hosts|authorized_keys|PKUpwmat|1Ding'
    for directory in [ROOT/'scripts/llm_env_4090_20261022',DOC,WORK]:
        for path in directory.rglob('*'):
            if not path.is_file():continue
            raw=path.read_bytes()
            assert path.stat().st_size<100000,path
            # This validator itself contains the literal deny-list markers.
            if path.resolve()!=Path(__file__).resolve():assert not re.search(forbidden,raw),path
            if path.suffix=='.py':
                assert path.name not in {'inspect.py','json.py','requests.py'}
                ast.parse(raw.decode('utf-8'),filename=path.name);ast_count+=1
            if path.suffix=='.md':
                for target in re.findall(r'\]\(([^)]+)\)',raw.decode('utf-8')):
                    if '://' not in target:
                        assert (path.parent/target).exists(),(path,target);links+=1
    subprocess.run(['git','-C',str(ROOT),'diff','--check'],check=True,capture_output=True)
    return {'status':'passed','unique_source_hashes':len(verified),'published_report_and_freeze_hashes':len(result['published_files']),'exact_private_original_files_verified_before_view_creation':sum(len(x['raw_files_verified']) for x in result['collections']),'package_count':94,'same_freeze_sha256':result['same_freeze_sha256'],'CPU_checks_each':19,'GPU_checks_each':6,'GPU_jobs':gpu,'strict_state_parameters':27,'strict_state_buffers':3,'roundtrip_logits_max_error_each':0.0,'python_AST_files':ast_count,'relative_links':links,'privacy_scan':'passed','git_diff_check':'passed','real_model_quality_training_PPA':'not run'}

if __name__=='__main__':print(json.dumps(main(),ensure_ascii=False,indent=2))
