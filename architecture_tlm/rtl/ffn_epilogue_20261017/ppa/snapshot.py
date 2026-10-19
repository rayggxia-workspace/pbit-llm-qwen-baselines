import pathlib
import shutil
import sys
from package import verify

src, dst = map(pathlib.Path, sys.argv[1:])
manifest = verify(src)
for name in list(manifest['sha256']) + ['package_manifest.json']:
    target = dst/name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src/name), str(target))
verify(dst)
