"""Read-only release index and artifact audit. Writes only the requested report."""
import argparse,gzip,hashlib,json,re,subprocess,tarfile
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath

p=argparse.ArgumentParser()
p.add_argument('--root',required=True)
p.add_argument('--out',required=True)
a=p.parse_args()
root=Path(a.root)
def git(*args,input=None):
    return subprocess.check_output(['git','-C',str(root),*args],input=input)
cache={}
def blob(path):
    if path not in cache: cache[path]=git('show',':'+path)
    return cache[path]
def sha(b):return hashlib.sha256(b).hexdigest()
def data(path):return json.loads(blob(path))
changed=[x for x in git('diff','--cached','--name-only','-z','46804fb3').decode().split('\0') if x]
start_index=sha(git('ls-files','--stage','-z'))
report={'schema':'cycle116.read_only_release_review.1','created_utc':datetime.now(timezone.utc).isoformat(),
        'head':git('rev-parse','HEAD').decode().strip(),'base':'46804fb3',
        'index_listing_sha256':start_index,'changed_files':len(changed),'models_executed':False,
        'root_modified':False,'manifest_checks':[],'issues':[]}
allowed=('architecture_tlm/cycle_v1/','work/amlink1219/116/','digital_circuit_simulation_registry/')
outside=[x for x in changed if not x.startswith(allowed) and x not in ('progress/amlink1219/STATUS.md','.gitignore','.gitattributes')]
forbidden=[x for x in changed if any(y in x.lower().split('/') for y in ('private_fixtures','.venv','venv','env','models','checkpoints'))
           or x.lower().endswith(('.safetensors','.pt','.pth','.ckpt','.pkl'))]
report['outside_scope']=outside
report['forbidden_payload_paths']=forbidden
report['issues']+=outside+forbidden
def check_manifest(path,entries):
    checked=[]
    for entry in entries:
        name=entry['path']
        if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or '\\' in name:
            report['issues'].append('unsafe manifest path: '+path+':'+name)
            continue
        target=(PurePosixPath(path).parent/name).as_posix()
        actual=blob(target)
        raw=(root/target).read_bytes()
        ok=sha(actual)==entry['sha256'] and raw==actual and ('bytes' not in entry or len(actual)==entry['bytes'])
        checked.append({'path':target,'passed':ok,'bytes':len(actual)})
        if not ok:report['issues'].append('manifest mismatch: '+target)
    report['manifest_checks'].append({'manifest':path,'kind':'Git index + raw working bytes','files':len(checked),'passed':all(x['passed'] for x in checked)})
matrix='architecture_tlm/cycle_v1/results/matrix_20261023/'
pub=matrix+'PUBLISHED_MANIFEST.json'
check_manifest(pub,data(pub)['artifacts'])
v6='architecture_tlm/cycle_v1/results/v6_adapter_20261023_v2/MANIFEST.json'
check_manifest(v6,data(v6)['files'])
compat='work/amlink1219/116/pr122_compat/results/MANIFEST.json'
check_manifest(compat,[{'path':k,'sha256':v} for k,v in data(compat).items()])
index=data(matrix+'ARCHIVE_INDEX.json')
archive=Path(index['archive']['local_path'])
archive_ok=sha(archive.read_bytes())==index['archive']['sha256'] and archive.stat().st_size==index['archive']['bytes']
if not archive_ok:report['issues'].append('archive checksum mismatch')
with tarfile.open(archive) as t:
    for file,prefix in [('REAL_ARTIFACT_MANIFEST.json','matrix-real-v5'),('SMOKE_ARTIFACT_MANIFEST.json','matrix-smoke-v5')]:
        entries=data(matrix+file)['artifacts']
        failures=[]
        for entry in entries:
            name=prefix+'/'+entry['path']
            try:
                member=t.getmember(name)
                actual=t.extractfile(member).read()
                ok=sha(actual)==entry['sha256'] and len(actual)==entry['bytes']
            except (KeyError,AttributeError):ok=False
            if not ok:failures.append(name)
        report['manifest_checks'].append({'manifest':matrix+file,'kind':'hashed original archive members',
                                         'files':len(entries),'passed':not failures,'failures':failures})
        report['issues']+=failures
report['archive_sha256_verified']=archive_ok
audit=data('architecture_tlm/cycle_v1/audit/results/matrix_v5_offline_review_final.json')
audit_hashes=[]
for suite in audit['suites']:
    path=matrix+('REAL_ARTIFACT_MANIFEST.json' if suite['suite']=='real' else 'SMOKE_ARTIFACT_MANIFEST.json')
    ok=sha(blob(path))==suite['artifact_manifest_sha256']
    audit_hashes.append({'suite':suite['suite'],'passed':ok})
    if not ok:report['issues'].append('audit manifest link mismatch: '+suite['suite'])
report['audit_manifest_links']=audit_hashes
patterns={
    'github_token':rb'(?:github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{30,})',
    'openai_key':rb'sk-(?:proj-)?[A-Za-z0-9_-]{32,}',
    'aws_key':rb'AKIA[A-Z0-9]{16}',
    'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
    'literal_auth_bearer':rb'Authorization[\s:=]+Bearer [A-Za-z0-9._-]{24,}',
}
secret_hits=[]
model_hits=[]
large=[]
sizes=[]
gzip_scanned=0
for name in changed:
    b=blob(name)
    sizes.append((len(b),name))
    if len(b)>10*1024*1024:large.append({'path':name,'bytes':len(b)})
    if name.endswith('.json.gz'):
        b=gzip.decompress(b);gzip_scanned+=1
    if name.endswith(('.py','.sv','.md','.json','.json.gz','.csv','.txt','.sbatch','.mjs','.html','.log')):
        for kind,pattern in patterns.items():
            if re.search(pattern,b):secret_hits.append({'path':name,'rule':kind})
        if name.endswith(('.json','.json.gz')) and re.search(rb'"(?:wg|wu|wd)"\s*:\s*(?:\[|\{\s*"codes")',b):
            model_hits.append(name)
report['obvious_credential_hits']=secret_hits
report['raw_ffn_weight_payload_candidates']=model_hits
report['over_10MiB_files']=large
report['largest_files']=[{'path':n,'bytes':s} for s,n in sorted(sizes,reverse=True)[:8]]
report['total_changed_blob_bytes']=sum(s for s,n in sizes)
report['compressed_json_payloads_scanned']=gzip_scanned
report['issues']+=secret_hits+model_hits
report['index_unchanged_during_review']=sha(git('ls-files','--stage','-z'))==start_index
if not report['index_unchanged_during_review']:report['issues'].append('index changed during review')
report['passed']=not report['issues']
report['limits']=['Pattern screening is not a formal secret detector; only reported strong patterns were searched.',
    'Historical audit source hashes describe their captured revisions, not the current source.',
    'No model, GPU, simulation, or test suite was executed; this is publication-integrity review.']
Path(a.out).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(report,ensure_ascii=False))
