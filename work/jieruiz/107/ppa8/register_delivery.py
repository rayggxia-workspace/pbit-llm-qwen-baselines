"""Register this prepared batch, never mark remote EDA as completed."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

REPO = Path(__file__).resolve().parents[4]
HOME = REPO.parents[1]
ARCHIVE = HOME/'project_archives/digital_ppa8_20261023'
RELEASE = 'digital_ppa8_ss_tt_100_20261023_v1'
KINDS = (0, 2, 4, 5, 6, 7, 8, 21)
RECORD = 'digital-ppa8-20261023-prepared'


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def artifact(p, role):
    return dict(path=p.as_posix(), role=role, present_at_registration=True,
                required=True, sha256=sha(p), bytes=p.stat().st_size)


def main():
    if (REPO/'digital_circuit_simulation_registry/records'/(RECORD+'.json')).exists():
        raise ValueError('Already registered; do not rewrite archived evidence')
    final = ARCHIVE/'validation_final/VALIDATION.json'
    validation = json.loads(final.read_text())
    assert validation['status'] == 'PASS' and len(validation['cases']) == 96
    extracted = ARCHIVE/'extracted_final'/RELEASE
    manifest = json.loads((extracted/'package_manifest.json').read_text())
    assert validation['package_manifest_sha256'] == sha(extracted/'package_manifest.json')
    for name, digest in manifest['files'].items():
        assert sha(extracted/name) == digest, name
    package = HOME/(RELEASE+'.zip')
    shutil.copyfile(str(ARCHIVE/'delivery_final'/(RELEASE+'.zip')), str(package))
    raw = ARCHIVE/'LOCAL_VALIDATION_RAW.tar.gz'
    with tarfile.open(str(raw), 'w:gz') as t:
        for dirname in ('validation_v1', 'validation_v2', 'validation_final'):
            for p in sorted((ARCHIVE/dirname).rglob('*')):
                if p.is_file():
                    t.add(str(p), arcname=p.relative_to(ARCHIVE).as_posix())
    formal = REPO/'architecture_tlm/digital_ppa_v1/results/PPA8_LOCAL_VALIDATION.json'
    write(formal, validation)
    cases = [dict(index=i+8*j, kind=k, corner=c, voltage_V=v, temperature_C=temp,
                  clock_MHz=100, status='pending_remote_eda', area_um2=None, power_uW=None)
             for j, (c, v, temp) in enumerate([('SS', 1.08, 125), ('TT', 1.2, 25)]) for i, k in enumerate(KINDS)]
    record = dict(schema_version=1, id=RECORD, name='8类数字算子SS/TT 100MHz脚本包与本地功能验证',
        family='转换/FFN/Attention数字算术', registered_on='2026-10-23', owner='jieruiz', issue=107,
        evidence_level='RTL_FUNCTIONAL', status='prepared_pending_remote_eda',
        stages=dict(functional='pass', synthesis='not_run', sta='not_run', power='not_run', postlayout='not_run'),
        boundary='KIND0/2/4/5/6/7/8/21；nr_digital_probe含输入输出/控制寄存器及核心；没有SRAM/PLL/PRNG/随机矩阵/CTS/布线',
        conditions=dict(node_nm=55, corner=['SS','TT'], voltage_V=[1.08,1.2], temperature_C=[125,25],
                        clock_MHz=100, seeds=[17,43,101], window_ns='由固定事务行数和16拍排空确定；idle256拍',
                        load_pF=.02, sdf=False, spef=False, cts=False),
        source=dict(git_commit=manifest['source_git_head'], source_manifest_sha256=sha(extracted/'package_manifest.json'),
                    binding='包内package_manifest.json逐文件SHA；RTL原件23e8d65f；当前本地测试未调用DC/VCS/PT'),
        artifacts=[artifact(package,'self_contained_source_package'), artifact(raw,'local_validation_raw'),
                   artifact(formal,'local_rtl_validation_summary')], cases=cases,
        limitations=['96场景是本地Icarus数值检查，不是96次工艺仿真；SS/TT各8项尚待用户提交。',
                     '零延迟门级VCD不含真实毛刺/CTS/布线；单元面积非版图面积，负slack必须保留。',
                     'SwiGLU近似PWL不继承模型PPL；混合帧合成流量不等于真实模型激活或单独S128成本。',
                     'KIND4/5按64元素组，KIND6输出已包含四档恢复，不能再次乘64/72。'],
        next_action='用户先submit.sh smoke验证KIND21的SS/TT，再remaining；回传reports.tar.gz和Slurm日志后新增真实run记录。')
    record_path = Path(__file__).parent/'REGISTRY_RECORD.json'
    write(record_path, record)
    registry = REPO/'digital_circuit_simulation_registry'
    subprocess.run([__import__('sys').executable, str(registry/'registry.py'), 'add', str(record_path)], check=True)
    inventory = registry/'archive_inventory.csv'
    with inventory.open(encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fields, entries = reader.fieldnames, list(reader)
    entries.append(dict(path=raw.as_posix(), bytes=raw.stat().st_size, sha256=sha(raw), linked_records=RECORD,
                        review_state='local_rtl_validated', note='本地功能/失败原件；没有DC/VCS/PT结果'))
    with inventory.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fields, lineterminator='\n')
        w.writeheader()
        w.writerows(entries)
    write(Path(__file__).parent/'DELIVERY.json', dict(package=artifact(package,'upload_package'),
        validation_cases=96, outputs=sum(x['outputs'] for x in validation['cases']),
        execution_source=manifest['source_git_head'], package_manifest_sha256=sha(extracted/'package_manifest.json'),
        runtime_python36_syntax='PASS', python38_flow_tests='6 PASS', tcl_guards='PASS', bash_syntax='PASS',
        dc_vcs_pt='NOT_RUN', registry_base='PR111@2b7935f4bbb16c37cb1f59c5a2a394ae005e2b8b',
        raw_validation=artifact(raw,'local_validation_raw')))
    print(json.dumps(dict(package=str(package), sha256=sha(package), registry_record=RECORD)))


if __name__ == '__main__':
    main()
