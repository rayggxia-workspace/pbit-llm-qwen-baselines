"""Read exact frozen v6 bytes; never rerun or change a model to make a table."""
import csv
import hashlib
import io
import json
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = 'eb317e4f6fb1b0d8844887401f3275f128ef8a83'
OBS = 'fa4ef7b0a65974e97a72639d277169ab42ab95ec'


def frozen(commit, path):
    return subprocess.check_output(['git', 'show', commit+':'+path], cwd=ROOT)


def collect():
    dirs = ('qwen_20261022_v2', 'llama1_bf16_20261022_v2',
            'llama1_scpv_20261022_v2', 'llama2_bf16_20261022_v2',
            'llama2_scpv_20261022_v2')
    rows, evidence, phases = [], [], []
    for directory in dirs:
        for p in sorted((ROOT/'architecture_tlm/unified_v6/results'/directory).rglob('*.json')):
            if p.name in ('EXECUTION.json', 'ARTIFACT_MANIFEST.json', 'SUMMARY.json'):
                continue
            rel = p.relative_to(ROOT).as_posix()
            raw = frozen(BASE, rel)
            assert p.read_bytes() == raw
            v = json.loads(raw)
            c = v['config']; period = 1e9/c['core_hz']; t = v['metrics']['elapsed_ns']
            assert abs(sum(v['phase_ns'].values())-t) < .001
            model = 'qwen' if v['model']['hidden_size'] == 896 else ('llama2' if 'llama2' in rel else 'llama1')
            row = dict(model=model, context=c['context_tokens'], seed=c['seed'],
                       ffn=c['ffn']['mode'], attention=c['attention']['mode'],
                       core_hz=c['core_hz'], sram_hz=c['sram']['clock_hz'],
                       equivalent_core_cycles=t/period, TPOT_ms=t/1e6,
                       dram_backend=v['DRAM']['backend'],
                       sram_read_bytes=v['SRAM']['traffic']['read_physical_bytes'],
                       sram_write_bytes=v['SRAM']['traffic']['write_physical_bytes'],
                       sampler_cycles=v['resource_busy_ns'].get('sampler', 0)/period,
                       K_read_bytes=v['DRAM']['traffic'].get('K_selected_physical_bytes', 0)+v['DRAM']['traffic'].get('KV_fused_physical_bytes', 0)//2,
                       V_read_bytes=v['DRAM']['traffic'].get('V_sparse_union_physical_bytes', 0)+v['DRAM']['traffic'].get('KV_fused_physical_bytes', 0)//2,
                       config_sha256=v['config_sha256'], source=rel, sha256=hashlib.sha256(raw).hexdigest())
            rows.append(row)
            evidence.append(dict(path=rel, archive_commit=BASE, execution_commit=v['execution_commit'], config_sha256=v['config_sha256'], sha256=row['sha256']))
            for name, ns in v['phase_ns'].items():
                phases.append(dict(model=model, context=row['context'], seed=row['seed'], ffn=row['ffn'],
                                   attention=row['attention'], phase=name, equivalent_core_cycles=ns/period, ms=ns/1e6))
    assert len(rows) == 52
    assert len({(r['model'], r['context'], r['seed'], r['ffn'], r['attention']) for r in rows}) == 52
    return rows, phases, evidence


def main():
    rows, phases, evidence = collect()
    output = HERE/'results'; output.mkdir(exist_ok=True)
    for name, data in [('cycles_52.csv', rows), ('phase_cycles.csv', phases)]:
        s = io.StringIO(newline=''); w = csv.DictWriter(s, fieldnames=list(data[0]), lineterminator='\n'); w.writeheader(); w.writerows(data)
        (output/name).write_text(s.getvalue(), encoding='utf-8', newline='\n')
    grouped = []
    for key in sorted({(r['model'], r['context'], r['ffn'], r['attention']) for r in rows}):
        group = [r for r in rows if (r['model'],r['context'],r['ffn'],r['attention']) == key]
        grouped.append(dict(model=key[0], context=key[1], ffn=key[2], attention=key[3], seeds=len(group),
                            mean_cycles=statistics.mean(r['equivalent_core_cycles'] for r in group),
                            min_cycles=min(r['equivalent_core_cycles'] for r in group),
                            max_cycles=max(r['equivalent_core_cycles'] for r in group)))
    obs_path = 'architecture_tlm/inspector/results/observed_v3/qwen_L2048_seed0_sc_screen_rejection_observed.json'
    raw = frozen(OBS, obs_path); obs = json.loads(raw)
    stage = obs['stage_busy_ns']
    result = dict(schema=1, scope='batch1 one decode token, warm context; no prefill/TTFT; conditional timing, NOT STA-validated chip cycles',
                  archive_commit=BASE, groups=grouped, evidence=evidence,
                  observer=dict(archive_commit=OBS, path=obs_path, sha256=hashlib.sha256(raw).hexdigest(),
                                stage_service_core_cycles={k:v/10 for k,v in stage.items()},
                                query_count=len(obs['sampler_audit']),
                                last_layer_head0=next(x for x in obs['sampler_audit'] if x['layer']==23 and x['head']==0)))
    (output/'CYCLE_AUDIT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n',encoding='utf-8', newline='\n')
    print(json.dumps([r for r in rows if r['model']=='qwen' and r['seed']==0], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
