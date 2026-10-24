import json
from pathlib import Path
import shutil
import sys
from package import verify

root, target = [Path(x).resolve() for x in sys.argv[1:]]
m = verify(root)
for name in list(m['files'])+['package_manifest.json']:
    dest = target/name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(root/name), str(dest))
    dest.chmod(0o444)
verify(target)
