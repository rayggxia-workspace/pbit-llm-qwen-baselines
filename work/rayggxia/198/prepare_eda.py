"""Build an immutable minimal server source snapshot; never include private libs."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import zipfile

R=Path(__file__).resolve().parents[3]
C=R/'architecture_tlm/attention_compare_20261027/control_v2'
W=Path(__file__).parent

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--version',default='v1');a=p.parse_args()
    snap=W/('.eda_private/snapshot_'+a.version);snap.mkdir(exist_ok=False)
    (snap/'rtl').mkdir()
    bundle=C/'results/ppa_bundle_final'
    for p in (bundle/'rtl').glob('*.sv'):shutil.copyfile(p,snap/'rtl'/p.name)
    for name in ['ac_scan.sv','ac_winner.sv','ac_rejection.sv']:shutil.copyfile(C/'rtl'/name,snap/'rtl'/name)
    shutil.copyfile(bundle/'CASES.json',snap/'CASES.json')
    for p in (C/'eda_20261028').glob('*'):
        if p.is_file():shutil.copyfile(p,snap/p.name)
    if a.version not in ('v1','v2'):
        shutil.copytree(W/'.eda_private/vectors_v3',snap/'vectors')
    manifest=dict(source_commit='157e19c6823b2cd3434ed6cd99ff1786e07824f0',
        new_driver='exact files below, working patch; rejection coin_mask declaration moved before use for DC2018 compatibility, no equations changed',
        files={p.relative_to(snap).as_posix():dict(sha256=digest(p),bytes=p.stat().st_size) for p in snap.rglob('*') if p.is_file()})
    (snap/'SOURCE.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode())
    package=snap.with_suffix('.zip')
    with zipfile.ZipFile(package,'x',zipfile.ZIP_DEFLATED) as z:
        for p in snap.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(snap).as_posix())
    with zipfile.ZipFile(package) as z:assert z.testzip() is None
    print(json.dumps(dict(path=str(package),sha256=digest(package),bytes=package.stat().st_size,source_sha256=digest(snap/'SOURCE.json'))))

if __name__=='__main__':main()
