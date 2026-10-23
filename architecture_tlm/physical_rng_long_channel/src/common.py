"""Immutable byte snapshots and bounded-memory result archives."""
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile

SOURCE=Path(__file__).resolve().parent


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def save(path,value):
    with Path(path).open('w',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def verify():
    m=json.loads((SOURCE/'package_manifest.json').read_text(encoding='utf-8'))
    for n,h in m.items():
        p=PurePosixPath(n)
        if p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n or digest(SOURCE/n)!=h:
            raise ValueError('Source hash/path mismatch: '+n)
    return m


def copy_source(target):
    m=verify();target=Path(target);target.mkdir(parents=True,exist_ok=False)
    for n in list(m)+['package_manifest.json']:
        dst=target/n;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(str(SOURCE/n),str(dst))  # Never preserve read-only modes.


def pack(directory):
    directory=Path(directory).resolve()
    if not directory.is_dir() or directory.parent.name!='results':raise ValueError('Expected results/JOB_MODE')
    target=directory.parent.parent/('long_channel_'+directory.name+'.tar.gz')
    partial=Path(str(target)+'.partial')
    if target.exists() or partial.exists() or Path(str(target)+'.sha256').exists():
        raise ValueError('Archive/partial already exists; refusing overwrite')
    manifest={}
    for p in sorted(directory.rglob('*')):
        if p.is_symlink():raise ValueError('No symlinks in result package')
        if p.is_file() and p.name!='result_manifest.json':
            manifest[p.relative_to(directory).as_posix()]=dict(bytes=p.stat().st_size,sha256=digest(p))
    save(directory/'result_manifest.json',manifest)
    expected=dict(manifest)
    expected['result_manifest.json']=dict(bytes=(directory/'result_manifest.json').stat().st_size,sha256=digest(directory/'result_manifest.json'))
    with tarfile.open(str(partial),'w:gz',compresslevel=1) as tar:
        for n,info in sorted(expected.items()):
            p=directory/n
            if p.stat().st_size!=info['bytes'] or digest(p)!=info['sha256']:raise ValueError('Result changed during packing')
            tar.add(str(p),arcname=directory.name+'/'+n,recursive=False)
    seen=set()
    with gzip.open(str(partial),'rb') as payload:
        with tarfile.open(fileobj=payload,mode='r|') as tar:
            for m in tar:
                n=PurePosixPath(m.name).relative_to(directory.name).as_posix()
                if n not in expected or n in seen or not m.isfile():raise ValueError('Archive member mismatch')
                h=hashlib.sha256();count=0;stream=tar.extractfile(m)
                for b in iter(lambda:stream.read(1024*1024),b''):h.update(b);count+=len(b)
                if dict(bytes=count,sha256=h.hexdigest())!=expected[n]:raise ValueError('Archive hash mismatch')
                seen.add(n)
        for b in iter(lambda:payload.read(1024*1024),b''):pass
    if seen!=set(expected):raise ValueError('Archive incomplete')
    # publish_exclusive uses exclusive-create fallback on unsupported hardlinks.
    import zero_core
    zero_core.publish_exclusive(partial,target);partial.unlink()
    with Path(str(target)+'.sha256').open('x',encoding='ascii',newline='\n') as f:
        f.write(digest(target)+'  '+target.name+'\n')
    return target
