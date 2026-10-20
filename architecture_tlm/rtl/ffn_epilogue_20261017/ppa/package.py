"""Reproducible, PDK-free upload package and immutable source verification."""
import argparse
import hashlib
import json
import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = 'dac6e0426da6421ccc62077275e236532ca3c3da'


def files():
    names = ['swiglu_epilogue_q10.sv', 'sigmoid_lut.svh', 'sigmoid_lut_q16.json',
             'golden_model.py', 'generate_lut.py', 'README_ZH.md']
    return [ROOT/n for n in names] + sorted(p for p in (ROOT/'ppa').iterdir() if p.suffix in ('.py', '.tcl', '.sh', '.sv', '.md'))


def verify(root):
    root = pathlib.Path(root)
    manifest = json.loads((root/'package_manifest.json').read_text())
    for name, expected in manifest['sha256'].items():
        path = root/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Source checksum mismatch: ' + name)
    print('PACKAGE_OK release=' + manifest['release'])
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify')
    ap.add_argument('--zip')
    args = ap.parse_args()
    if args.verify:
        verify(args.verify)
        return
    if not args.zip:
        ap.error('--verify ROOT or --zip OUTPUT is required')
    paths = files()
    manifest = dict(release='epilogue_ppa100_v1', source_repository='rayggxia-workspace/pbit-llm-qwen-baselines',
                    rtl_base_commit=BASE, branch='task/7-epilogue-ppa100',
                    note='PPA changes identified by exact file SHA256; base commit identifies unchanged arithmetic RTL.',
                    sha256={p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    payload = (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode('ascii')
    (ROOT/'package_manifest.json').write_bytes(payload)
    with zipfile.ZipFile(args.zip, 'w', zipfile.ZIP_DEFLATED) as out:
        for p in paths:
            out.write(str(p), 'ffn_epilogue_ppa100_20261017/'+p.relative_to(ROOT).as_posix())
        out.writestr('ffn_epilogue_ppa100_20261017/package_manifest.json', payload)
    verify(ROOT)
    print('ZIP_SHA256='+hashlib.sha256(pathlib.Path(args.zip).read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
