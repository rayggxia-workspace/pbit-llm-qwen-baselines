"""Server-side personal staging; never alter a submitted execution snapshot."""
import hashlib,json,os,shutil,subprocess,sys,tarfile
from pathlib import Path
root=Path('/home/Hongjie_Zeng/projects/pbit-qwen-sampler-ppl-20261023-issue141')
sha,expected=sys.argv[1:3]
assert len(sha)==40 and all(x in '0123456789abcdef' for x in sha)
archive=root/'incoming'/('source-'+sha+'.tar')
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
snapshot=root/'snapshots'/sha
snapshot.mkdir(exist_ok=False)
with tarfile.open(archive) as tar:
    for m in tar.getmembers():
        assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
    tar.extractall(snapshot)
old=Path('/home/Hongjie_Zeng/projects/pbit-qwen-joint-ffn-attention-20261019-issue50/snapshots/c0fd54446d843f0b21e94bf138c692048e518c86/experiments/qwen_dual_iid_exact_20261018')
area=snapshot/'experiments/qwen_dual_iid_exact_20261018'
frozen=json.loads((area/'frozen_manifest.json').read_text())
assets={}
for name in ('calibration.json','sz_calibration.json'):
    rel='vendor/frozen/results/'+name
    source=old/rel;entry=frozen['files'][rel]
    assert source.stat().st_size==entry['bytes'] and hashlib.sha256(source.read_bytes()).hexdigest()==entry['sha256']
    dest=area/rel;dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,dest)
    assets[rel]=dict(entry,source=str(source))
(root/('assets-'+sha+'.json')).write_text(json.dumps(assets,indent=2)+'\n')
env=dict(os.environ,PBIT_PROJECT_ROOT=str(root),PBIT_SNAPSHOT=str(snapshot),PBIT_CODE_COMMIT=sha,PBIT_ACTION='prepare')
cmd=['/opt/slurm/21.08.8/bin/sbatch','--parsable','--export=ALL','--output='+str(root/'logs/prepare-%j.out'),str(snapshot/'experiments/qwen_parallel_sampler_ppl_20261023/run.sbatch')]
r=subprocess.run(cmd,env=env,text=True,capture_output=True,check=True)
receipt=dict(code_commit=sha,archive_sha256=expected,snapshot=str(snapshot),job_id=r.stdout.strip(),command=cmd,assets=assets)
(root/('submission-'+sha+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
