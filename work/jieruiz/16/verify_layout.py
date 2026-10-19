"""Verify model directory routing and byte preservation; no GPU/DRAM jobs."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
BASE='7a506365cce42fd257f2645aa589b624e7d77116'
AUX=Path(__file__).resolve().parent


def verify(record=False,staged=False):
    env=dict(os.environ,PYTHONIOENCODING='utf-8')
    commands=[]
    def run(args,cwd=ROOT):
        res=subprocess.run([sys.executable,*args],cwd=cwd,env=env,capture_output=True)
        assert res.returncode==0,(args,res.stdout.decode('utf-8'),res.stderr.decode('utf-8'))
        commands.append({'argv':args,'cwd':str(cwd),'exit_code':res.returncode})
        return res.stdout.decode('utf-8')
    spec=importlib.util.spec_from_file_location('model_workspace_audit',ROOT/'scripts/model_workspace.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    anchor_count=0
    for name in module.MODELS:
        data=module.load_project(name)
        checked=json.loads(run([name+'/run.py','check']))
        anchor_count+=checked['anchors_verified']
        info=json.loads(run([str(ROOT/name/'run.py'),'info'],ROOT.parent))
        assert info==data
        # Check each mapped command and ensure arguments containing spaces remain
        # distinct argv elements even from outside the repository.
        for action,row in data['commands'].items():
            args=['--output','a folder/result.json','--seed','2']
            dry=json.loads(run([str(ROOT/name/'run.py'),'--dry-run',action,*args],ROOT.parent))
            assert Path(dry['command'][1])==ROOT/row['script']
            assert dry['command'][2:]==args and Path(dry['cwd'])==ROOT.parent
        help_text=run([str(ROOT/name/'run.py'),'tlm','--help'],ROOT.parent)
        assert '--output' in help_text
        if name=='llama2':assert '--identity-manifest' in help_text and '--synthetic' in help_text
        if name=='qwen':assert '--modes' in help_text
        with patch.object(module.subprocess,'run') as mocked:
            mocked.return_value.returncode=13
            actual=module.main(name,['tlm','--output','a folder/result.json'])
            assert actual==13
            expected=[sys.executable,str(ROOT/data['commands']['tlm']['script']),'--output','a folder/result.json']
            mocked.assert_called_once_with(expected,check=False)
    for bad in ('../outside','/outside','C:/outside','a\\b'):
        try:module.project_path(bad)
        except ValueError:pass
        else:raise AssertionError('Accepted unsafe path '+bad)
    for model in ('llama1','llama2'):
        run([model+'/run.py','verify'])
    link_count=0
    for path in [ROOT/'README.md',*[p for name in module.MODELS for p in (ROOT/name).rglob('*.md')]]:
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            if '://' in target or target.startswith('#'):continue
            assert (path.parent/target.split('#',1)[0]).exists(),(path,target)
            link_count+=1
    diff=subprocess.check_output(['git','diff','--name-only',BASE],cwd=ROOT,text=True).splitlines()
    allowed=('qwen/','llama1/','llama2/','work/jieruiz/16/')
    assert all(p in ('README.md','progress/jieruiz/STATUS.md','scripts/model_workspace.py') or p.startswith(allowed) for p in diff)
    old=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE],cwd=ROOT,text=True).splitlines()
    # Existing tracked files may only change in the root navigation and our own STATUS.
    assert not (set(old)&set(diff)-{'README.md','progress/jieruiz/STATUS.md'})
    files=[]
    for rel in diff:
        if rel=='work/jieruiz/16/manifest.json':continue
        raw=(ROOT/rel).read_bytes()
        assert len(raw)<2**20
        files.append({'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
        if staged:
            assert subprocess.check_output(['git','show',':'+rel],cwd=ROOT)==raw,rel
    value={'repository':'rayggxia-workspace/pbit-llm-qwen-baselines','owner':'jieruiz',
        'issue':16,'branch':'task/16-model-folders','base_commit':BASE,
        'scope':'Model directory navigation/command routing only; no model or hardware algorithm changes.',
        'data_model_config':'Original inputs unchanged; identity/config/result hashes indexed by model project.json and frozen execution manifests.',
        'new_training_or_gpu_runs':False,'mutable_source_patch':'This PR only; old execution snapshots unchanged.',
        'verification':{'models':3,'anchors':anchor_count,'links':link_count,'frozen_Llama1_inputs':62,'frozen_Llama2_inputs':57,
            'command_checks':len(commands),'commands':commands,'argv_space_and_exitcode_forwarding_models':3,'unsafe_paths_rejected':4},
        'artifacts':files}
    p=AUX/'manifest.json'
    if record:p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    if p.exists():
        stored=json.loads(p.read_text(encoding='utf-8'))
        assert stored['artifacts']==files,'Regenerate release manifest after changing files'
        if staged:assert subprocess.check_output(['git','show',':work/jieruiz/16/manifest.json'],cwd=ROOT)==p.read_bytes()
    print(json.dumps({'models':3,'anchors':anchor_count,'links':link_count,'frozen_inputs':119,
        'commands':len(commands),'release_files':len(files),'staged_bytes_verified':staged}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--record',action='store_true');parser.add_argument('--staged',action='store_true')
    args=parser.parse_args();verify(args.record,args.staged)
