"""Register five GQA configurations; independent audits remain validation evidence."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BASE = 'architecture_tlm/cycle_v1/results/gqa_real_20261023/'
ID = 'cycle-116-gqa-conditional-model'


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-root', type=Path, required=True,
                        help='Existing stable local checkout; read-only byte verification')
    args = parser.parse_args()
    artifact_root = args.artifact_root.resolve(strict=True)
    manifest = read(BASE + 'PUBLIC_MANIFEST.json')
    for name, expected in manifest['files'].items():
        assert sha((ROOT / BASE / name).read_bytes()) == expected, name
    capture_name = 'work/amlink1219/116/gqa_capture_v1/PUBLIC_RECEIPT.json'
    source_name = 'work/amlink1219/116/gqa_validation_v1/SOURCE_MANIFEST.json'
    capture, source = read(capture_name), read(source_name)
    audit = read(BASE + 'public_audit.json')
    assert audit['passed'] and len(audit['cases']) == 6
    assert sum(len(c['numeric']['heads']) for c in audit['cases']) == 42
    assert all(c['config']['samples'] == 16 and c['cycle_event_equal']
               and c['all_credits_returned']
               and all(h['bit_equal'] for h in c['numeric']['heads'])
               for c in audit['cases'])
    fixture_sha = capture['artifact']['sha256']
    assert audit['fixture_sha256'] == fixture_sha
    cases = []
    for name in ('exact', 'pv', 'winner', 'rejection', 'exact_narrow'):
        report = read(BASE + name + '.json')
        assert report['status'] == 'passed' and report['mode_equivalence']['equal']
        assert report['fixture_sha256'] == fixture_sha
        assert report['query_heads'] == 7 and report['KV_heads'] == 1
        assert all(c['samples'] == 32 for c in report['query_configs'])
        cases.append(dict(case_id='gqa64/' + name, operator='gqa_group',
            mode=report['query_configs'][0]['mode'], functional='pass',
            cycle_event_equal=True, configured_samples=32,
            samples_note='S32 configuration; exact modes do not draw samples',
            query_configs=report['query_configs'], group_config=report['group_config'],
            memory_window=1 if name == 'exact_narrow' else 4,
            latency_ns=report['latency_ns'], operations=report['operations'],
            latency_evidence='configured cycle simulation; not measured hardware',
            area_um2=None, power_uW=None, energy_pJ=None,
            shared_K_rows=report['shared']['K_union_count'],
            shared_V_rows=report['shared']['V_union_count'],
            output_sha256=[q['output_sha256'] for q in report['queries']],
            numerical_validation=[q['numeric_validation'] for q in report['queries']],
            report_repository_path=BASE + name + '.json',
            report_sha256=manifest['files'][name + '.json']))
    assert cases[0]['output_sha256'] == cases[-1]['output_sha256']
    names = [(BASE + name + '.json', 'configuration_summary')
             for name in ('exact', 'pv', 'winner', 'rejection', 'exact_narrow')]
    names += [(BASE + 'public_audit.json', 'independent_validation'),
              (BASE + 'PUBLIC_MANIFEST.json', 'publication_manifest'),
              (BASE + 'SOURCE_VERIFIED.json', 'execution_source_verification'),
              (BASE + 'terminal.json', 'application_terminal'),
              ('work/amlink1219/116/gqa_validation_v1/FIRST_TERMINAL_SCHEDULER.txt', 'scheduler_terminal'),
              (source_name, 'source_manifest'), (capture_name, 'capture_provenance'),
              ('architecture_tlm/cycle_v1/audit/results/gqa_root_integrated_public_review.json', 'independent_publication_validation'),
              ('work/amlink1219/116/gqa_capture_v1/validation.sbatch', 'execution_command')]
    artifacts = []
    for name, role in names:
        payload = (ROOT / name).read_bytes()
        path = artifact_root / name
        assert path.read_bytes() == payload, 'stable artifact copy differs: ' + name
        artifacts.append(dict(path=path.as_posix(), repository_path=name, role=role,
            required=True, present_at_registration=True, sha256=sha(payload), bytes=len(payload)))
    record = dict(schema_version=1, id=ID, name='真实7查询头共享KV条件周期模型（context64）',
        family='周期执行条件模型', registered_on='2026-10-23', owner='amlink1219', issue=116,
        evidence_level='DESIGN_PROOF', status='conditional_model_verified',
        stages=dict(functional='pass', synthesis='not_run', sta='not_run', power='not_run', postlayout='not_run'),
        boundary='Qwen2.5-0.5B第12层预投影7查询头/1共享KV头，context64、D64；5个S32配置双模式执行。6个S16独审配置/42个配置-查询头仅作为验证，不计入cases。',
        conditions=dict(model='Qwen/Qwen2.5-0.5B', layer=12, context=64, query_heads=7,
            KV_heads=1, head_dimension=64, query_token_position=63, candidate_policy='all 64 causal keys',
            execution_job_id=2782, capture_job_id=2781, configured_samples=32,
            query_seeds=[c['seed'] for c in cases[0]['query_configs']],
            numeric_boundary=capture['provenance']['dtype'],
            timing_kind='configured cycle model, not measured hardware',
            memory_backend='finite banked descriptor model; not online DRAM commands',
            physical_area=None, physical_power=None, physical_energy=None),
        source=dict(git_commit=source['core_commit'], audit_commit=source['audit_commit'],
            capture_commit=capture['provenance']['execution_commit'],
            source_manifest_repository_path=source_name,
            source_manifest_sha256=sha((ROOT / source_name).read_bytes()),
            source_archive_sha256=source['archive_sha256'], fixture_sha256=fixture_sha,
            binding='74 staged source/data SHA-256 verified inside CPU allocation; public reports preserve private artifact hashes'),
        validation_evidence=dict(independent_audit_configurations=6, configured_samples=16,
            case_head_checks=42, execution_modes_per_configuration=2, all_scalar_outputs_bit_equal=True,
            trace_operations=sum(c['trace_check']['operations'] for c in audit['cases']),
            trace_events=sum(c['trace_check']['events'] for c in audit['cases']),
            shared_row_payload_checks=sum(c['numeric']['actual_shared_reads_checked'] for c in audit['cases']),
            all_credits_returned=True, counted_as_experiment_cases=False,
            repository_path=BASE + 'public_audit.json', sha256=manifest['files']['public_audit.json']),
        limitations=[
            '5个cases是配置行，不是5次独立模型或硬件实测；cycle/event双执行与6个独审配置不重复计数。',
            'BF16投影导出后CPU FP32 RoPE边界；QKV投影、RoPE、KV追加、筛选、Wo及其余模型不计入GQA周期。',
            '不同采样模式数值契约不同；按观察到的本地PRNG轨迹验证数学，不证明分布/IID或全模型PPL。',
            'latency/II/端口配置未经完整目标工艺STA标定，面积/功率/能量未知；禁止从该时间列宣称物理PPA优势。',
            'context2048/完整注意力层/完整模型未执行；每头独立源状态不等于全局共享随机网络闭合。',
            '私有激活与完整轨迹留服务器，公开字段仅配置/计数/误差/散列；不导出原始payload。'],
        artifacts=artifacts, cases=cases,
        next_action='待正式固定调度优化版后评估更长上下文并独立验收；真实全层、共享随机网络及目标工艺PPA分别补证。')
    output = ROOT / 'work/amlink1219/116/gqa_conditional_model_record.json'
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(output=str(output), id=ID, cases=len(cases),
                         validation_configurations=6, validation_case_heads=42, artifacts=len(artifacts))))


if __name__ == '__main__':
    main()
