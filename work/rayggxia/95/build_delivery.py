"""Create a portable user delivery and a lossless archive of task-only raw traces.

No deletion, network access or PDK access. All outputs must be new paths.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
PROJECT = ROOT.parent.parent
DEST = PROJECT / '远端上传/rng_service_v1_20261022'
ARCHIVE = PROJECT / 'project_archives/rng_service_issue95_20261022'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def checked_zip(output, root, paths):
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in paths:
            z.write(p, p.relative_to(root).as_posix())
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for p in paths:
            assert hashlib.sha256(z.read(p.relative_to(root).as_posix())).hexdigest() == sha(p)
    return dict(path=str(output), bytes=output.stat().st_size, sha256=sha(output), files=len(paths))


def main():
    DEST.mkdir(parents=True, exist_ok=False)
    ARCHIVE.mkdir(parents=True, exist_ok=False)
    raw_names = ['rtl_validation', 'rtl_validation_v2', 'rtl_final', 'power_stream']
    raw = sorted(p for n in raw_names for p in (WORK/n).rglob('*') if p.is_file())
    receipt = checked_zip(ARCHIVE/'verification_raw.zip', WORK, raw)
    receipt['members'] = {p.relative_to(WORK).as_posix(): sha(p) for p in raw}
    write(ARCHIVE/'RESTORE_INDEX.json', receipt)
    write(WORK/'RAW_ARCHIVE.json', receipt)
    for p in (ROOT/'architecture_tlm/random_service').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            copy(p, DEST/p.relative_to(ROOT))
    # Dependencies required for the 19 scoped tests and optional Attention adapter.
    for name in ['parallel_sampler_v5.py', 'winner_hold_tlm_v5.py',
                 'corrected_rejection_tlm_v5.py', 'rng_reference.py']:
        copy(ROOT/'architecture_tlm'/name, DEST/'architecture_tlm'/name)
    for name in ['rng32x64.sv', 'manifest.json']:
        copy(ROOT/'rng32x64_design_20261015'/name, DEST/'rng32x64_design_20261015'/name)
    for name in ['VALIDATION.json', 'RTL_VALIDATION.json', 'ACTIVITY_VALIDATION.json',
                 'python_tests.log', 'statistical_diagnostics.json', 'demo_os.json']:
        copy(WORK/name, DEST/'validation'/name)
    for p in (WORK/'power_stream').rglob('*'):
        if p.is_file() and p.suffix != '.vvp':
            copy(p, DEST/'examples/power_stream'/p.relative_to(WORK/'power_stream'))
    (DEST/'START_HERE_ZH.md').write_text('''# 随机源模型与数字RTL初版交付

2026-10-22，Issue95。源码基线83e15289434af50fc09c35e699d8b39965389d98；新增源码以MANIFEST.json逐文件SHA为准。
任务PR见 https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/issues/95 。

先读 architecture_tlm/random_service/README_ZH.md；功耗仿真按 POWER_SIM_ZH.md；疑点在 DESIGN_QUESTIONS_ZH.md。
rtl/内7个SystemVerilog文件可交给数字仿真/综合工具。优先综合rng_seeded_top的KIND=0/1/2，再测rng_ffn_shared64。
基础LFSR输出1字；GF共享扩展输出64字但不是64路联合独立；Bivium输出20字。三者均需新外部种子。
10ns参考时钟下默认约1秒换种，参数0仅启动换种；FFN保存/重放窗口延后换种并记录延期。

从本包根运行（Python >=3.10，无第三方依赖）：

    python -m unittest discover -s architecture_tlm/random_service/tests -v
    python -m architecture_tlm.random_service.demo --output my_run/demo.json
    python -m architecture_tlm.random_service.verification --output my_rtl --iverilog iverilog --vvp vvp --vcd

验证回执在validation/；19项新增测试的依赖已包含。仓库中的47项总检查还包含旧架构测试，旧测试数据不在精简包中。
三后端9组8100沿压力测试及3组6000沿连续活动对照通过，FFN前端250沿/120帧通过。
examples/power_stream含2000拍的3种RTL活动/VCD、输入与期望向量、操作数，以及FFN示例波形。
这些是合成事务活动，不是实际LLM轨迹，也不是门级功耗结果。现有回执中的绝对路径记录原验证环境，复跑请使用本包相对入口。

本轮没有DC/PT/PPL/新Spectre结果。面积和能耗字段为null，留给你用自己的库测量。
软件默认OS新随机种子不等于物理熵；硬件需接你自己的合格物理随机字输出。模拟读出、健康调理、CDC、共享总线仲裁器及sigmoid LUT完整RTL不在本包。
源码、测试和说明SHA见MANIFEST.json，ZIP校验见旁边的SHA256文件。请先复制到自己的仿真目录后编辑，保留原始交付字节。
''', encoding='utf-8', newline='\n')
    env = dict(__import__('os').environ, PYTHONDONTWRITEBYTECODE='1')
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
                           'architecture_tlm/random_service/tests', '-v'], cwd=DEST,
                          env=env, capture_output=True, text=True)
    (DEST/'validation/portable_tests.log').write_text(test.stdout+test.stderr, encoding='utf-8', newline='\n')
    if test.returncode:
        raise RuntimeError(test.stderr)
    check = WORK/'package_verify'
    check.mkdir(exist_ok=False)
    demo = subprocess.run([sys.executable, '-m', 'architecture_tlm.random_service.demo',
                           '--mode', 'fixture', '--fixture-seed', '17', '--output', str(check/'demo.json')],
                          cwd=DEST, env=env, capture_output=True, text=True)
    if demo.returncode:
        raise RuntimeError(demo.stderr)
    copy(check/'demo.json', DEST/'validation/portable_fixture_demo.json')
    files = sorted(p for p in DEST.rglob('*') if p.is_file())
    write(DEST/'MANIFEST.json', dict(baseline='83e15289434af50fc09c35e699d8b39965389d98',
        issue=95, files={p.relative_to(DEST).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}))
    zip_receipt = checked_zip(DEST.with_suffix('.zip'), DEST,
                             sorted(p for p in DEST.rglob('*') if p.is_file()))
    DEST.with_suffix('.zip.sha256').write_text(zip_receipt['sha256']+'  '+DEST.with_suffix('.zip').name+'\n',
                                             encoding='ascii',newline='\n')
    write(WORK/'DELIVERY.json', dict(package=zip_receipt, raw_archive=receipt['path'],
          raw_archive_sha256=receipt['sha256'], portable_tests=19, portable_fixture_demo='PASS'))
    print(json.dumps(zip_receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
