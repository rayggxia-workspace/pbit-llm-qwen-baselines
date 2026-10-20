"""Archive unique state of completed own worktrees before explicit cleanup."""
import base64
import datetime
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import zipfile

ROOT=pathlib.Path(r'C:\Users\86134\Documents\a_P_BIT').resolve()
REPO=ROOT/'pbit-llm-qwen-baselines'
AUDIT=pathlib.Path(__file__).resolve().parent
ARCHIVES=ROOT/'project_archives/cleanup_20261019_round2'
ARCHIVES.mkdir(parents=True,exist_ok=True)
if (AUDIT/'round2_delete_plan.json').exists():
    raise SystemExit('Existing plan: inspect instead of overwriting')
audit=json.loads((AUDIT/'round2_audit_agent.json').read_text(encoding='utf-8'))
issues=json.loads((AUDIT/'round2_remote_issues.json').read_text(encoding='utf-8-sig'))
issue_map={x['number']:x for x in issues}
closed_scope={3,5,9,12,14,16,23,26,30,32,39,46,51,55}
base=audit['base']

def run(path,*args,check=True):
    p=subprocess.run(['git','-C',str(path),*args],capture_output=True,timeout=120)
    if check and p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8',errors='replace'))
    return p

def text(path,*args):return run(path,*args).stdout.decode('utf-8').strip()
def names(data):return [x.decode('utf-8') for x in data.split(b'\0') if x]
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024**2),b''):h.update(block)
    return h.hexdigest()
def is_cache(name):return any(x in pathlib.PurePosixPath(name).parts for x in ('__pycache__','.pytest_cache','.mypy_cache','.ruff_cache'))
def safe_file(root,rel):
    path=root.joinpath(*pathlib.PurePosixPath(rel).parts)
    resolved=path.resolve()
    if not resolved.is_relative_to(root):raise RuntimeError('Path escape')
    for p in (path,*path.parents):
        if p==ROOT:break
        if p.exists() and p.lstat().st_file_attributes&stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise RuntimeError('Reparse point')
    return path

selected=[];skipped=[]
for row in audit['records']:
    path=pathlib.Path(row['path']).resolve();name=path.name
    issue=row.get('issue_inferred')
    review=name.startswith(('pr-backlog-','pr-review-r2-','pr47-review-'))
    helper=name=='qwen-fixedw-multiscale-kernel-20261019'
    if not (issue in closed_scope or review or helper):continue
    if path.parent!=ROOT/'tmp':continue
    if name=='pr47-review-main-20261019' or any(x!='jieruiz' for x in row.get('dirty_owner_dirs',[])):
        skipped.append(dict(directory=name,reason='other owner state; retained'));continue
    scope_issue=55 if review else 46 if helper else issue
    state=issue_map[scope_issue]
    if state['state']!='closed' or state['owner']!='jieruiz':
        skipped.append(dict(directory=name,reason='not completed own issue'));continue
    head=text(path,'rev-parse','HEAD')
    if head!=row['head']:raise RuntimeError('HEAD changed '+name)
    porcelain=run(path,'status','--porcelain=v1','-z','--untracked-files=all').stdout
    diff=run(path,'diff','--binary','HEAD').stdout
    staged=run(path,'diff','--cached','--binary').stdout
    changed=names(run(path,'diff','--name-only','-z','HEAD').stdout)
    untracked=names(run(path,'ls-files','--others','--exclude-standard','-z').stdout)
    ignored=names(run(path,'ls-files','--others','--ignored','--exclude-standard','-z').stdout)
    preserve=sorted(set(changed+untracked+[x for x in ignored if not is_cache(x)]))
    all_unknown=set(untracked+ignored)
    other_owner=[x for x in preserve if (x.startswith('progress/') or x.startswith('work/')) and x.split('/')[1] not in ('jieruiz',)]
    if other_owner:
        skipped.append(dict(directory=name,reason='other owner uncommitted files',paths=other_owner));continue
    missing=[x for x in preserve if not safe_file(path,x).is_file()]
    if missing:
        skipped.append(dict(directory=name,reason='deleted/renamed or non-file state requires manual recovery',paths=missing));continue
    manifest=[]
    for rel in preserve:
        p=safe_file(path,rel)
        manifest.append(dict(relative=rel,bytes=p.stat().st_size,sha256=digest(p)))
    if any(x['bytes']>100*1024**2 for x in manifest):
        skipped.append(dict(directory=name,reason='large unique artifact retained'));continue
    recovery_ref='refs/heads/archive/cleanup-20261019/'+name
    prior=run(REPO,'rev-parse','--verify',recovery_ref,check=False)
    if prior.returncode==0 and prior.stdout.decode().strip()!=head:raise RuntimeError('Recovery ref collision')
    if prior.returncode:run(REPO,'update-ref',recovery_ref,head)
    ancestor=run(REPO,'merge-base','--is-ancestor',head,base,check=False).returncode==0
    bundle=None
    if not ancestor:
        bundle=ARCHIVES/(name+'.bundle')
        if bundle.exists():raise RuntimeError('Recovery bundle exists')
        run(REPO,'bundle','create',str(bundle),recovery_ref,'^'+base)
        run(REPO,'bundle','verify',str(bundle))
    zip_path=None
    if manifest or diff or staged:
        zip_path=ARCHIVES/(name+'.zip')
        if zip_path.exists():raise RuntimeError('Recovery archive exists')
        with zipfile.ZipFile(zip_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for f in manifest:z.write(safe_file(path,f['relative']),f['relative'])
            z.writestr('_cleanup_git_state/working_vs_HEAD.patch',diff)
            z.writestr('_cleanup_git_state/staged.patch',staged)
            z.writestr('_cleanup_git_state/manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(zip_path) as z:
            for f in manifest:
                with z.open(f['relative']) as member:
                    h=hashlib.sha256()
                    for b in iter(lambda:member.read(8*1024**2),b''):h.update(b)
                if h.hexdigest()!=f['sha256']:raise RuntimeError('Archive hash mismatch')
    size=0;files=0;reparse=[]
    for p,dirs,fs in os.walk(path,followlinks=False):
        dirs[:]=[d for d in dirs if d!='.git']
        for n in fs:
            f=pathlib.Path(p)/n;s=f.lstat()
            if s.st_file_attributes&stat.FILE_ATTRIBUTE_REPARSE_POINT:reparse.append(str(f));continue
            size+=s.st_size;files+=1
    if reparse:raise RuntimeError('Unexpected link in candidate')
    current_status=run(path,'status','--porcelain=v1','-z','--untracked-files=all').stdout
    if current_status!=porcelain or run(path,'diff','--binary','HEAD').stdout!=diff:
        raise RuntimeError('Worktree changed while archiving')
    selected.append(dict(path=str(path),issue=scope_issue,owner='jieruiz',head=head,
        branch=row.get('branch'),recovery_ref=recovery_ref,ancestor=ancestor,base=base,
        status_base64=base64.b64encode(porcelain).decode(),diff_sha256=hashlib.sha256(diff).hexdigest(),
        all_unknown=sorted(all_unknown),ignored_caches=[x for x in ignored if is_cache(x)],
        preserved_files=manifest,bytes=size,files=files,
        zip=str(zip_path) if zip_path else None,zip_sha256=digest(zip_path) if zip_path else None,
        bundle=str(bundle) if bundle else None,bundle_sha256=digest(bundle) if bundle else None))
    print(json.dumps(dict(prepared=name,MiB=round(size/2**20,2),unique_files=len(manifest),bundle=bool(bundle)),ensure_ascii=True),flush=True)

plan=dict(created=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
    root=str(ROOT),base=base,records=selected,skipped=skipped,archive_root=str(ARCHIVES),
    planned_bytes=sum(x['bytes'] for x in selected))
(AUDIT/'round2_delete_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(prepared_count=len(selected),planned_GiB=plan['planned_bytes']/2**30,skipped=skipped),ensure_ascii=True,indent=2))
