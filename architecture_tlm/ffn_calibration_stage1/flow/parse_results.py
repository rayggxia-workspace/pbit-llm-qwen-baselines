"""Fail-closed DC/PT timing receipts. No activity => no power number."""
import json
import math
from pathlib import Path
import re


class EvidenceError(ValueError):
    pass


def number(text, label):
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', text.strip()):
        raise EvidenceError('Missing/invalid numeric evidence: ' + label)
    value = float(text)
    if not math.isfinite(value):
        raise EvidenceError('Nonfinite ' + label)
    return value


def kv(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        if '=' not in line:
            raise EvidenceError('Malformed key/value evidence')
        key, value = line.split('=', 1)
        if key in result:
            raise EvidenceError('Duplicate evidence key: ' + key)
        result[key] = value.strip()
    return result


def parse_stage(folder, log_path, corner, tool):
    folder = Path(folder)
    def read(name):
        path = folder / name
        if not path.is_file() or not path.stat().st_size:
            raise EvidenceError('Missing report: ' + name)
        return path.read_text(encoding='utf-8', errors='strict')
    if read('STAGE_COMPLETE').strip() != tool:
        raise EvidenceError('Missing/incorrect completed stage marker')
    pvt = kv(read('pvt.txt'))
    voltage, temperature = {'ss': (1.08, 125.), 'tt': (1.20, 25.)}[corner]
    if pvt.get('corner') != corner or not pvt.get('library') or not pvt.get('condition'):
        raise EvidenceError('Unknown PVT identity')
    if abs(number(pvt.get('voltage_V', ''), 'voltage') - voltage) > 1e-6:
        raise EvidenceError('Wrong voltage')
    if abs(number(pvt.get('temperature_C', ''), 'temperature') - temperature) > 1e-6:
        raise EvidenceError('Wrong temperature')
    if pvt.get('time_unit') != 'ns' or pvt.get('capacitance_unit') != 'pF':
        raise EvidenceError('Unknown/incompatible library units')
    if not re.search(r'ss|slow' if corner == 'ss' else r'tt|typ', pvt['condition'], re.I):
        raise EvidenceError('Operating-condition name mismatches corner')
    setup = number(read('setup_slack_ns.txt'), 'setup slack')
    hold = number(read('hold_slack_ns.txt'), 'hold slack')
    timing = read('check_timing.rpt')
    # Real 2018 reports have these checking headings, even when no warning exists.
    for heading in ('no_clock', 'unconstrained_endpoints', 'no_input_delay'):
        if not re.search(r"Checking\s+['\"]" + heading + r"['\"]", timing, re.I):
            raise EvidenceError('check_timing did not cover ' + heading)
    if not re.search(r'^RETURN:\s*1\s*$', timing, re.M):
        raise EvidenceError('check_timing did not return success')
    if re.search(r'^\s*(?:Warning:|Error:|Fatal:)', timing, re.M | re.I):
        raise EvidenceError('check_timing warning/error requires review')
    log = Path(log_path).read_text(encoding='utf-8', errors='replace')
    reports = '\n'.join(read(x) for x in ('setup.rpt', 'hold.rpt', 'constraints.rpt', 'check_design.rpt'))
    if re.search(r'^\s*(?:Error:|Fatal:|Error-)', log + '\n' + reports, re.M | re.I):
        raise EvidenceError('Tool error found despite exit status')
    if re.search(r'\b(?:unconstrained\s+(?:endpoint|path)|not\s+constrained)\b', reports, re.I):
        raise EvidenceError('Unconstrained timing evidence')
    mapping = kv(read('mapping_audit.txt'))
    cells = number(mapping.get('mapped_leaf_cells', ''), 'mapped cells')
    if cells < 1 or cells != int(cells):
        raise EvidenceError('No valid mapped leaf cells')
    for key in ('unmapped_leaf_cells', 'nonlibrary_leaf_cells'):
        if number(mapping.get(key, ''), key) != 0:
            raise EvidenceError('Unmapped/unknown cell remains')
    area = number(mapping.get('area_library_units', ''), 'mapped area')
    if area <= 0:
        raise EvidenceError('Nonpositive mapped area')
    area_report = read('area.rpt')
    values = re.findall(r'Total cell area\s*:\s*([0-9.eE+\-]+)', area_report, re.I)
    if not values:
        raise EvidenceError('No total cell area in report')
    report_area = number(values[-1], 'report area')
    if abs(report_area-area) > max(0.01, abs(area)*0.01):
        raise EvidenceError('report_area and mapped-cell inventory disagree >1%')
    violated = setup < 0 or hold < 0 or bool(re.search(r'\bVIOLATED\b', read('constraints.rpt'), re.I))
    return dict(status='not_met' if violated else 'met', tool=tool,
                setup_slack_ns=setup, hold_slack_ns=hold,
                mapped_leaf_cells=int(cells), area_library_units=area,
                area_um2=area, area_unit_basis='existing 55nm library area-unit convention; no LEF extraction this run',
                pvt=pvt, frequency_MHz=100, timing_boundary='prelayout; no CTS/SPEF/SDF',
                power_W=None, energy_J=None,
                power_status='not_run_no_activity_based_power_analysis')


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('folder'); p.add_argument('--log', required=True)
    p.add_argument('--corner', choices=['ss', 'tt'], required=True)
    p.add_argument('--tool', choices=['dc', 'pt'], required=True)
    args = p.parse_args()
    try:
        result = parse_stage(args.folder, args.log, args.corner, args.tool)
    except (OSError, ValueError, UnicodeError) as exc:
        result = {'status': 'failed', 'error': str(exc)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return {'met': 0, 'not_met': 3, 'failed': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
