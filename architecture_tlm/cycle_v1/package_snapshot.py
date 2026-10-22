"""Package the explicitly declared execution dependency closure and test imports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--check-directory',type=Path,required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[2]
    if args.archive.exists() or args.check_directory.exists(): raise FileExistsError('choose fresh snapshot destinations')
    paths=subprocess.check_output(['git','ls-files','architecture_tlm/cycle_v1','architecture_tlm/random_service','architecture_tlm/unified_v6'],cwd=root,text=True).splitlines()
    paths=[p for p in paths if p.endswith('.py') or '/configs/' in p or p=='architecture_tlm/random_service/shared64_mapping.json']
    if 'architecture_tlm/random_service/shared64_mapping.json' not in paths: raise AssertionError('RNG mapping missing')
    args.archive.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(args.archive,'w:gz') as archive:
        for path in paths: archive.add(root/path,arcname=path,recursive=False)
    args.check_directory.mkdir(parents=True)
    with tarfile.open(args.archive) as archive: archive.extractall(args.check_directory,filter='data')
    env=dict(os.environ);env.pop('PYTHONPATH',None)
    smoke="from architecture_tlm.cycle_v1 import ffn,attention; from architecture_tlm.cycle_v1.run import synthetic_fixture; k=ffn.make_kernel(); s=ffn.build_ffn(k,synthetic_fixture()['ffn']); r=k.run(); assert s['output'] and r.finish_ps>0"
    subprocess.run([sys.executable,'-X','utf8','-c',smoke],cwd=args.check_directory,env=env,check=True)
    manifest={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),
        'files':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths},
        'archive_sha256':hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        'isolated_extraction_smoke':'passed without inherited PYTHONPATH'}
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(paths),'archive':str(args.archive),'sha256':manifest['archive_sha256']}))


if __name__=='__main__': main()
