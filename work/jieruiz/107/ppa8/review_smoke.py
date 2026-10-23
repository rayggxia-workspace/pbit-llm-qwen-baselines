"""Read-only raw-archive review; writes only small derived audit/registry JSON."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys
import tarfile
import zipfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'architecture_tlm/digital_ppa_v1/ppa8'))
from cell_report_parser import rows
from report_helpers import totals, library_units, coverage


def sha(data):
    return hashlib.sha256(data).hexdigest()


class TextMember:
    def __init__(self, text):
        self.text = text

    def open(self, **kwargs):
        return io.StringIO(self.text)


def main():
    local = Path('C:/Users/86134/Documents/a_P_BIT')
    with zipfile.ZipFile(local / 'digital_ppa8_ss_tt_100_20261023_v1.zip') as z:
        manifest = z.read('digital_ppa8_ss_tt_100_20261023_v1/package_manifest.json')
    artifacts, cases, audits = [], [], []
    for job in ('38339971_7', '38339971_15'):
        path = Path('C:/Users/86134/Documents/10月_MPW/APR_results') / (job+'_reports.tar.gz')
        with tarfile.open(path) as t:
            contents = {m.name[len(job)+1:]: t.extractfile(m).read() for m in t.getmembers() if m.isfile()}
        text = lambda p: contents[p].decode('utf-8-sig')
        obj = lambda p: json.loads(text(p))
        index = obj('RESULT_INDEX.json')
        checked = 0
        for name, entry in index.items():
            if name == 'stage_status':
                continue
            assert sha(contents[name]) == entry['sha256'], name
            assert len(contents[name]) == entry['bytes'], name
            checked += 1
        assert contents['source_manifest.json'] == manifest
        cfg = obj('configuration.json')
        assert cfg['source_manifest_sha256'] == sha(manifest)
        functional = sorted(n for n in contents if n.endswith('/FUNCTION_PASS'))
        assert len(functional) == 12
        for marker in functional:
            log = text(marker.rsplit('/', 1)[0]+'/simulation.log')
            assert 'DIGITAL_PPA_PASS' in log and 'Fatal:' not in log
        summary = obj('summary.json')
        assert len(summary) == 9
        for row in summary:
            name = 'k21_s{}_{}'.format(row['seed'], row['mode'])
            pt, sim = 'power/'+name+'/', 'gate/'+name+'/'
            audit, workload = obj(sim+'wave_audit.json'), obj(sim+'workload.json')
            assert audit['xz_signals'] == 0
            assert pt+'POWER_CALCULATED' in contents
            power, scales = totals(text(pt+'power.rpt'))
            library_units(text(pt+'units.rpt'))
            assert coverage(text(pt+'activity.rpt'))['net_coverage_percent'] == 100
            inv = {r['name']: r for r in csv.DictReader(io.StringIO(text(pt+'inventory.tsv')), delimiter='\t')}
            sums, seen = [0.]*4, set()
            for cell, raw, flags in rows(TextMember(text(pt+'cells.rpt'))):
                if cell is None:
                    assert raw[0] == len(seen)
                    break
                assert cell not in seen and cell in inv
                seen.add(cell)
                for j in range(4):
                    sums[j] += raw[j]*scales[j]
            assert seen == set(inv)
            assert all(math.isclose(a, b, rel_tol=.025, abs_tol=1e-10) for a,b in zip(sums,power))
            assert math.isclose(sum(float(r['area']) for r in inv.values()), row['area_um2'])
            assert math.isclose(power[3]*1e6, row['total_uW'])
            assert math.isclose(power[3]*audit['duration_ns']*1000, row['window_pJ'])
            if row['completed_outputs']:
                assert row['completed_outputs'] == workload['outputs']
                assert math.isclose(row['window_pJ']/workload['outputs'], row['pJ_per_completed_output'])
            assert float(text(pt+'setup_slack_ns.txt')) == row['setup_slack_ns'] > 0
            assert float(text(pt+'hold_slack_ns.txt')) == row['hold_slack_ns'] > 0
        breakdown = list(csv.DictReader(io.StringIO(text('power_breakdown.csv'))))
        means = {}
        for mode in ('stream','burst','idle'):
            rr = [r for r in summary if r['mode']==mode]
            means[mode] = {k: statistics.mean(r[k] for r in rr) for k in ('area_um2','total_uW','internal_uW','switching_uW','leakage_uW')}
            means[mode]['pJ_per_completed_output'] = statistics.mean(r['pJ_per_completed_output'] for r in rr) if mode!='idle' else None
            means[mode]['category_uW'] = {cat: statistics.mean(float(r['total_uW']) for r in breakdown if r['category']==cat and r['mode']==mode) for cat in sorted({r['category'] for r in breakdown})}
        artifacts.append(dict(path=path.as_posix(), role='raw_report_archive', present_at_registration=True, required=True, sha256=sha(path.read_bytes()), bytes=path.stat().st_size,
                              member=job+'/RESULT_INDEX.json', member_sha256=sha(contents['RESULT_INDEX.json']), member_bytes=len(contents['RESULT_INDEX.json'])))
        audits.append(dict(job=job, config=cfg, indexed_members_verified=checked, source_manifest_equal_to_delivered_package=True,
                           functional_passes=12, power_windows_reconciled=9, averages=means,
                           warnings_example={k:text('power/k21_s17_stream/'+k) for k in ('checks.rpt','activity.rpt')}))
        cases.extend(dict(job=job, **r) for r in summary)
    result = dict(audit_date='2026-10-23', method='archive hash and report reconciliation; no EDA rerun; original VCD/netlist not included', runs=audits)
    output = ROOT/'architecture_tlm/digital_ppa_v1/results/PPA8_SMOKE_38339971_AUDIT.json'
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    record = json.loads((ROOT/'digital_circuit_simulation_registry/records/digital-ppa8-20261023-prepared.json').read_text(encoding='utf-8'))
    record.update(id='digital-ppa8-38339971-smoke', name='FP32到BF16：SS/TT 100MHz首轮DC/VCS/PT结果', evidence_level='DC_GATE_PT_PRELAYOUT', status='calculated_provisional',
                  stages=dict(functional='pass', synthesis='completed', sta='reported_nonnegative', power='calculated', postlayout='not_run'),
                  boundary='KIND21 FP32到BF16转换器，含输入/输出及控制寄存器；不是其余7类模块，也不含PLL/SRAM/RNG/CTS/布线', artifacts=artifacts, cases=cases,
                  limitations=['PWR-981 result[2047:0]部分映射；100%覆盖率不证明所有bit映射正确，原VCD/网表未在包内。',
                               '每窗口2个load及1个ramp超库表范围；功耗仅初步值，未量化误差。',
                               '零延迟门级，无SDF/SPEF/CTS；面积为单元面积。三seed为合成输入，不是真实模型激活。',
                               'DC宽测试壳未使用输入/常量输出警告保留；面积与功耗包含边界寄存器，不能冒称纯组合核。'],
                  next_action='保留通过结果；复核16位有效输出的VCD映射及库表范围告警；remaining为其余14个工艺配置。')
    record['source']['binding'] = '两个结果source_manifest原字节与已交付包完全一致；每份RESULT_INDEX逐成员SHA校验，24功能场景/18功耗窗口核对。'
    (Path(__file__).parent/'SMOKE_RECORD.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({a['job']:dict(checked=a['indexed_members_verified'], averages=a['averages']) for a in audits}, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
