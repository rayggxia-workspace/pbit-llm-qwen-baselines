import base64,hashlib,json,pathlib,subprocess,sys
path=pathlib.Path(sys.argv[1]).resolve()
audit=pathlib.Path(__file__).resolve().parent
plan=json.loads((audit/'round2_delete_plan.json').read_text(encoding='utf-8'))
entry=next(x for x in plan['records'] if pathlib.Path(x['path']).resolve()==path)
def git(*args):
    p=subprocess.run(['git','-C',str(path),*args],capture_output=True,timeout=60)
    if p.returncode:raise SystemExit('Git validation error')
    return p.stdout
if base64.b64encode(git('status','--porcelain=v1','-z','--untracked-files=all')).decode()!=entry['status_base64']:
    raise SystemExit('Working status changed')
if hashlib.sha256(git('diff','--binary','HEAD')).hexdigest()!=entry['diff_sha256']:
    raise SystemExit('Working diff changed')
unknown=set(x.decode('utf-8') for x in (git('ls-files','--others','--exclude-standard','-z')+git('ls-files','--others','--ignored','--exclude-standard','-z')).split(b'\0') if x)
if sorted(unknown)!=entry['all_unknown']:raise SystemExit('Untracked/ignored set changed')
