"""Source-only portable package, with offline reference vectors. Python 3.6+."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

RELEASE = 'digital_ppa8_ss_tt_100_20261023_v1'
HERE = Path(__file__).resolve().parent
KINDS = (0, 2, 4, 5, 6, 7, 8, 21)


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def verify(root=HERE):
    m = json.loads((root/'package_manifest.json').read_text())
    if m['release'] != RELEASE:
        raise ValueError('Wrong release')
    for name, digest in m['files'].items():
        if sha(root/name) != digest:
            raise ValueError('Package mismatch: '+name)
    print('PACKAGE_OK '+RELEASE)
    return m


def build(destination):
    import subprocess
    source = HERE.parent
    repo = source.parents[1]
    target = destination/RELEASE
    target.mkdir(parents=True, exist_ok=False)
    for p in HERE.iterdir():
        if p.is_file() and p.suffix in ('.py', '.tcl', '.sv', '.sh', '.txt'):
            shutil.copyfile(str(p), str(target/p.name))
    for folder, src in [('rtl', source/'rtl'), ('conversion', repo/'format_conversion_rtl_20261016/rtl')]:
        (target/folder).mkdir()
        for p in src.iterdir():
            if p.suffix in ('.sv', '.svh'):
                shutil.copyfile(str(p), str(target/folder/p.name))
    (target/'reference').mkdir()
    shutil.copyfile(str(source/'sim/validate.py'), str(target/'reference/original_validate.py'))
    shutil.copyfile(str(repo/'format_conversion_rtl_20261016/sim/reference.py'), str(target/'reference/reference.py'))
    # Generator loads the original reference without modifying archived source bytes.
    from generate_vectors import generate
    generate(target)
    manifest = dict(release=RELEASE, source_git_head=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=str(repo)).decode().strip(),
        rtl_origin_commit='23e8d65fbd84cf548ab82a6c9cfe423d37e59ae4',
        files={p.relative_to(target).as_posix(): sha(p) for p in sorted(target.rglob('*')) if p.is_file()})
    (target/'package_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    verify(target)
    archive = destination/(RELEASE+'.zip')
    with zipfile.ZipFile(str(archive), 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(target.rglob('*')):
            if p.is_file():
                z.write(str(p), p.relative_to(destination).as_posix())
    print(str(archive)+' SHA256='+sha(archive))


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', type=Path)
    args = ap.parse_args()
    build(args.build.resolve()) if args.build else verify()
