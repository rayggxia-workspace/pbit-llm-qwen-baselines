"""Change only this task's private recipe source URLs, retaining exact hashes."""
import hashlib
import json
import os
from pathlib import Path
import sys
import yaml

task_root = Path('/home/Weican_Chen/projects/tlm-cycle-issue116-20261023').resolve()
job_id, port = sys.argv[1:]
assert job_id.isdigit() and port.isdigit()
cache = (task_root / 'cache/conan/.conan/data').resolve()
assert cache.is_relative_to(task_root) and os.getuid() == cache.stat().st_uid
packages = [('fmt', '10.0.0', 'fmt-10.0.0.zip'), ('spdlog', '1.11.0', 'spdlog.tar.gz'),
            ('boost', '1.79.0', 'boost_1_79_0.tar.bz2'), ('zlib', '1.3.1', 'zlib-1.3.1.tar.gz'),
            ('libbacktrace', 'cci.20210118', 'libbacktrace.tar.gz'), ('b2', '5.2.1', 'b2-5.2.1.tar.bz2')]
receipt = []
for name, version, filename in packages:
    recipe = (cache / name / version / '_/_/export/conandata.yml').resolve()
    assert recipe.is_relative_to(cache) and recipe.stat().st_uid == os.getuid()
    original = recipe.read_bytes()
    data = yaml.safe_load(original)
    source = data['sources'][version]
    archive = task_root / 'archives' / filename
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert actual == source['sha256'], (name, actual, source['sha256'])
    old_url = source['url']
    new_url = f'http://127.0.0.1:{port}/{filename}'
    backup = recipe.with_name(f'conandata.before-job-{job_id}.yml')
    assert not backup.exists()
    backup.write_bytes(original)
    source['url'] = new_url
    recipe.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
    receipt.append(dict(package=f'{name}/{version}', original_url=old_url, mirrored_url=new_url,
                        archive_sha256=actual, recipe_before_sha256=hashlib.sha256(original).hexdigest(),
                        recipe_after_sha256=hashlib.sha256(recipe.read_bytes()).hexdigest()))
(task_root / f'framework-mirror-{job_id}.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
