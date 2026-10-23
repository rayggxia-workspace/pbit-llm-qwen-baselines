"""Build an explicit, checksum-verified handoff ZIP outside the checkout.

Only committed source objects are read. Three authorized public task parquets
are supplied separately and never added to Git. No weights, credentials or env.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

EXP = 'experiments/pdnn20_task_accuracy_20261023/'
SINGLES = [
    'AGENTS.md', 'README.md', 'PROJECT_MEMORY_ZH.md',
    'progress/amlink1219/STATUS.md', 'work/amlink1219/151/HANDOFF.md',
    'work/amlink1219/151/PORTABLE_PROTOCOL_AUDIT_ZH.md',
    'experiments/pdnn_task_accuracy_20261023/pdnn_score.py',
    'experiments/pdnn_task_accuracy_20261023/test_pdnn_score.py',
    'experiments/pdnn_task_accuracy_20261023/runner.py',
    'experiments/pdnn_task_accuracy_20261023/PROTOCOL_ZH.md',
    'experiments/pdnn_ffn/full_path_pdnn_ffn.py',
    'experiments/pdnn_ffn/P_DNN_FFN_DESIGN_ZH.md',
    'experiments/qwen_task_accuracy_20261019/task_data.py',
]


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def build(a):
    checkout = Path(a.checkout).resolve(strict=True)
    target = Path(a.destination).resolve()
    if target.is_relative_to(checkout):
        raise ValueError('archive and staging must remain outside source checkout')
    def git(*args):
        completed = subprocess.run([a.git, '-C', str(checkout), *args], capture_output=True)
        if completed.returncode:
            raise RuntimeError('Git source read failed: ' + completed.stderr.decode('utf-8', errors='replace'))
        return completed.stdout
    commit = git('rev-parse', 'HEAD').decode().strip()
    if git('status', '--porcelain').strip():
        raise ValueError('commit scoped source changes before building immutable bundle')
    all_names = git('ls-tree', '-r', '--name-only', commit, EXP).decode().splitlines()
    # Explicit suffixes under the single reviewed experiment; no raw results.
    names = SINGLES + [n for n in all_names if Path(n).suffix in ('.py','.json','.md','.txt','.expected','.sh','.sbatch')]
    files = {name: git('show', commit + ':' + name) for name in sorted(set(names))}
    for required in ('portable_runner.py', 'test_portable.py', 'portable_reference.expected.json'):
        if EXP+required not in files:
            raise ValueError('portable execution source missing: ' + required)
    data = json.loads(files[EXP + 'portable_datasets.sources.json'])
    for name, entry in data['datasets'].items():
        path = Path(a.data_root) / name / '0000.parquet'
        payload = path.read_bytes()
        if len(payload) != entry['bytes'] or digest(payload) != entry['sha256']:
            raise ValueError('task data bytes mismatch: ' + name)
        files[entry['package_path']] = payload
    files['START_HERE_ZH.md'] = (
        '# 20层 P-DNN 服务器执行交接包\n\n'
        '请先把 [给师弟及agent的入口](experiments/pdnn20_task_accuracy_20261023/handoff/START_HERE_ZH.md) 发给接手者。\n\n'
        '必读：[接手agent规则](experiments/pdnn20_task_accuracy_20261023/handoff/AGENTS.md)、'
        '[服务器执行步骤](experiments/pdnn20_task_accuracy_20261023/handoff/SERVER_RUN_ZH.md)、'
        '[回传清单](experiments/pdnn20_task_accuracy_20261023/handoff/RETURN_CHECKLIST_ZH.md)。\n\n'
        '源码为下面manifest的冻结提交；不含模型/PDNN权重、环境或凭据。'
        '使用接手者自己的账号、个人目录、Slurm分配，先CPU预检后真实GPU smoke。'
        '三项公开任务数据已包含，不能把数据或大权重提交Git。\n'
    ).encode('utf-8')
    manifest = dict(schema_version=1, repository='rayggxia-workspace/pbit-llm-qwen-baselines',
        issue=151, pull_request=155, code_commit=commit, profile='portable_fresh_bf16_v1',
        created_utc=datetime.now(timezone.utc).isoformat(),
        scope='3 fresh BF16 baselines + 9 joint20 N4 seed0/1/2 cases; no training or PPA',
        real_twenty_layer_inference=False, weights_included=False, credentials_included=False,
        files=[dict(path=n, bytes=len(v), sha256=digest(v)) for n,v in sorted(files.items())])
    files['BUNDLE_MANIFEST.json'] = encode(manifest)
    target.mkdir(parents=True, exist_ok=True)
    archive = target / ('PDNN20_服务器交接包_' + commit[:12] + '.zip')
    if archive.exists():
        raise FileExistsError('do not overwrite previous bundle: ' + str(archive))
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, payload in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026,10,23,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 << 16)
            z.writestr(info, payload)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None or len(z.namelist()) != len(files):
            raise ValueError('ZIP integrity failure')
        for name, payload in files.items():
            if z.read(name) != payload:
                raise ValueError('archived byte mismatch: ' + name)
    external = dict(archive=archive.name, bytes=archive.stat().st_size,
        sha256=digest(archive.read_bytes()), code_commit=commit, files=len(files),
        manifest_sha256=digest(files['BUNDLE_MANIFEST.json']),
        datasets_bytes=sum(e['bytes'] for e in data['datasets'].values()),
        weights_included=False, real_twenty_layer_inference=False)
    receipt = target / (archive.name + '.json')
    receipt.write_bytes(encode(external))
    (target / (archive.name + '.sha256')).write_text(external['sha256']+'  '+archive.name+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(**external, local_path=str(archive)), ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--checkout', required=True)
    p.add_argument('--data-root', required=True, help='contains <task>/0000.parquet for exactly three pinned tasks')
    p.add_argument('--destination', required=True)
    p.add_argument('--git', default='git')
    build(p.parse_args())
