"""Independent read-only Issue182 cross-k audit. Prints small-case receipts."""
import collections
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
COMMIT = 'baf0aab1c20712d666bea40716d5cffde3df6e24'
sys.path.insert(0, str(ROOT))
from architecture_tlm.unified_v6.config import tiny
from architecture_tlm.unified_v6.ffn_latest import defaults
from architecture_tlm.unified_v6.model import FullDecode

EPS = 1e-5
SOURCES = ['architecture_tlm/unified_v6/' + f for f in
           ('ffn_latest.py', 'memory_profiles.py', 'model.py', 'core.py',
            'rng_integrated.py', 'config.py')]


def source_check():
    answer = {}
    for rel in SOURCES:
        raw = (ROOT / rel).read_bytes()
        git_raw = subprocess.check_output(['git', 'show', COMMIT + ':' + rel], cwd=ROOT)
        assert raw == git_raw, ('source is not reviewed commit', rel)
        answer[rel] = hashlib.sha256(raw).hexdigest()
    return answer


def run(h, f, engines, source, cross, double):
    c, m = tiny()
    m.update(hidden_size=h, intermediate_size=f, num_hidden_layers=2,
             vocab_size=384)
    c.update(decode_tokens=2, trace_event_limit=500000,
             weight_chunk_bytes=max(65536, engines * 4096), double_buffer=double)
    c['ffn'].update(defaults())
    c['ffn'].update(engines=engines, local_weight_bytes=engines * 4096,
                    weight_schedule='dma_prefetch',
                    prefetch_across_input_groups=cross,
                    local_weight_load_bytes_per_cycle=1024)
    c['sram'].update(capacity_bytes=8 * 1024**2, banks=64, fabric_GBs=64.)
    c['random']['backend'] = source
    c['attention']['mode'] = 'exact'
    d = FullDecode(c, m)
    owner = d.ffn_latest
    original = owner.prefetched_group
    group_receipts = []

    def group(t, name, k, groups, E, frame, nl=False):
        if owner.pending_ticket is not None:
            p = owner.pending_ticket
            assert (p['name'], p['k'], p['j'], p['n']) == (name, k, 0, min(E, groups))
        if group_receipts:
            assert t + EPS >= group_receipts[-1]['restore_end']
        end = original(t, name, k, groups, E, frame, nl=nl)
        should_pending = bool(cross and double and k + 1 < d.matrix_info[name]['inp'] // 64)
        assert (owner.pending_ticket is not None) == should_pending
        if should_pending:
            p = owner.pending_ticket
            assert (p['name'], p['k'], p['j'], p['n']) == (name, k + 1, 0, min(E, groups))
            assert p['n'] * 4096 <= owner.local['dma_prefetch_buffer_bytes']
        group_receipts.append(dict(name=name, k=k, input_ready=t, restore_end=end))
        return end

    with patch.object(owner, 'prefetched_group', side_effect=group):
        r = d.run()
    assert not r['trace_truncated']
    assert owner.pending_ticket is None
    assert owner.rng.saved is None
    if source == 'integrated_service':
        assert d.rng.ffn_frame is None
    pipe = r['FFN_contract']['weight_pipeline']
    records = pipe['records']
    mult = m['num_hidden_layers'] * c['decode_tokens']
    gu = (h // 64) * ((2 * f // 64 + engines - 1) // engines)
    down = (f // 64) * ((h // 64 + engines - 1) // engines)
    wave_count = mult * (gu + down)
    expected_cross = mult * (h // 64 + f // 64 - 2) if cross and double else 0
    assert pipe['counts'].get('cross_input_group_prefetches', 0) == expected_cross
    assert len(records) == pipe['counts']['waves'] == wave_count
    assert pipe['counts']['prefetch_bytes'] == 3 * h * f * mult
    assert r['FFN_activity']['SC_64x64_tiles'] == 3 * h * f * mult // 4096
    assert len(group_receipts) == mult * (h // 64 + f // 64)
    by_slot = {}
    for i, rec in enumerate(records):
        ts = [rec[key] for key in ('issue_ns', 'dram_done_ns', 'fill_done_ns',
                                  'program_start_ns', 'program_done_ns',
                                  'coeff_done_ns', 'array_start_ns',
                                  'array_done_ns', 'restore_done_ns')]
        assert ts == sorted(ts), ('invalid ticket dependency', rec)
        if i:
            assert rec['program_start_ns'] + EPS >= records[i - 1]['restore_done_ns']
        previous = by_slot.get(rec['slot'])
        if previous:
            assert rec['generation'] == previous['generation'] + 1
            assert rec['issue_ns'] + EPS >= previous['array_done_ns']
        by_slot[rec['slot']] = rec
    # Inputs are changed only after the preceding SC wave finishes, including
    # any integrated-source backpressure extension.
    input_stages = {'sram_SC_BF16_x', 'sram_SC_x_code',
                    'sram_SC_x_code_to_local', 'sram_SC_joint_codes_to_local'}
    for event in r['events']:
        if event['stage'] in input_stages:
            for rec in records:
                assert event['end_ns'] <= rec['array_start_ns'] + EPS or event['start_ns'] + EPS >= rec['array_done_ns'], ('input overwrite', event, rec)
    by_resource = collections.defaultdict(list)
    for event in r['events']:
        for key in event['resources']:
            by_resource[key].append((event['start_ns'], event['end_ns']))
    for key, intervals in by_resource.items():
        intervals.sort()
        for previous, current in zip(intervals, intervals[1:]):
            assert previous[1] <= current[0] + EPS, ('resource overlap', key)
    assert abs(max(e['end_ns'] for e in r['events']) - r['metrics']['elapsed_ns']) < EPS
    r['_sequence'] = [(x['name'], x['k'], x['j'], x['n']) for x in records]
    print(json.dumps(dict(shape=[h, f], engines=engines, source=source,
                         cross=cross, double=double, layers=2, tokens=2,
                         waves=wave_count, cross_prefetches=expected_cross,
                         groups=len(group_receipts), events=len(r['events']),
                         status='passed')), flush=True)
    return r


def main():
    before = source_check()
    total = 0
    for h, f, E in ((192, 320, 2), (128, 192, 8), (192, 320, 8)):
        for source in ('local_prng_interface', 'integrated_service'):
            baseline = run(h, f, E, source, False, True)
            for cross, double in ((True, True), (True, False)):
                r = run(h, f, E, source, cross, double)
                for key in ('model', 'FFN_activity', 'attention_activity',
                            'row_receipts', '_sequence'):
                    assert baseline[key] == r[key], ('work differs', key)
                for key in ('SRAM', 'DRAM'):
                    assert baseline[key]['traffic'] == r[key]['traffic'], ('traffic differs', key)
                assert baseline['FFN_contract']['nonlinear_random']['counts'] == r['FFN_contract']['nonlinear_random']['counts']
                if source == 'integrated_service':
                    assert baseline['random_interface']['source_counts'] == r['random_interface']['source_counts']
                else:
                    assert baseline['random_interface']['demands'] == r['random_interface']['demands']
                    assert baseline['random_interface']['requests'] == r['random_interface']['requests']
            total += 3
    assert source_check() == before
    print(json.dumps(dict(status='passed', cases=total, commit=COMMIT,
                         sources_sha256=before,
                         boundary='small synthetic schedule checks; no new full-model/DRAMSys/PPL/PPA claim')), flush=True)


if __name__ == '__main__':
    main()
