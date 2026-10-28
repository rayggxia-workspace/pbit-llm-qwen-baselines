"""Source audit arithmetic and a fixed-weight linear reassociation probe. No RTL run."""
from pathlib import Path
import hashlib
import json
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LOCAL = Path('C:/Users/86134/Documents/a_P_BIT')
DOC = ROOT / 'architecture_tlm/simulator_survey_20261025'
rtl = LOCAL / 'tmp/calibration-v2-issue193-20261027/architecture_tlm/calibration_v2_20261027/counter/rtl/sc_counter_merged.sv'
b = rtl.read_bytes()
assert b'weights/sign/bin remain stable' in b.lower()
N = 64
geometry = []
for bins, T in ((4, 64), (7, 128)):
    leaf_width = 8 + 2 * (bins - 1)
    acc_width = 1 + (N * 127 * T).bit_length() + 2 * (bins - 1)
    for pipe in (1, 2):
        cuts = [{'level': l, 'nodes': N >> l, 'width': leaf_width + l,
                 'bits': (N >> l) * (leaf_width + l)}
                for l in range(1, 7) if l % pipe == 0 or l == 6]
        tree = sum(x['bits'] for x in cuts)
        geometry.append({'BINS': bins, 'T': T, 'PIPE_EVERY': pipe,
                         'registered_cuts': cuts, 'tree_register_bits': tree,
                         'accumulator_bits': acc_width, 'data_register_bits_per_output': tree + acc_width})
assert geometry[1]['data_register_bits_per_output'] == 374
assert geometry[3]['data_register_bits_per_output'] == 507

probes = []
for bins in (4, 7):
    for T in (32, 64, 128):
        for seed in (17, 503, 1009):
            rng = random.Random(seed + bins * 10000 + T)
            q = [rng.randrange(257) for _ in range(N)]
            q[0], q[1] = 0, 256
            bin_ids = [rng.randrange(bins) for _ in range(N)]
            signs = [rng.choice((-1, 1)) for _ in range(N)]
            weights = [[rng.randrange(-127, 128) for _ in range(N)] for _ in range(8)]
            words = [rng.randrange(256) for _ in range(T)]
            events = [[int(r < qi) for qi in q] for r in words]
            counts = [sum(row[i] for row in events) for i in range(N)]
            weighted_events = [sum(sum(row[i] * signs[i] * w[i] * (1 << (2 * (bins - 1 - bin_ids[i])))
                                       for i in range(N)) for row in events) for w in weights]
            count_weighted = [sum(counts[i] * signs[i] * w[i] * (1 << (2 * (bins - 1 - bin_ids[i])))
                                   for i in range(N)) for w in weights]
            assert weighted_events == count_weighted
            # Third calculation: deterministic bit planes of the SAME sampled counts.
            bitplane = [sum((1 << bit) * sum(((counts[i] >> bit) & 1) * signs[i] * w[i]
                                            * (1 << (2 * (bins - 1 - bin_ids[i]))) for i in range(N))
                            for bit in range(T.bit_length())) for w in weights]
            assert bitplane == weighted_events
            payload = json.dumps({'q': q, 'bins': bin_ids, 'sign': signs, 'weights': weights,
                                  'words': words, 'counts': counts, 'outputs': weighted_events}, separators=(',', ':')).encode()
            probes.append({'BINS': bins, 'T': T, 'seed': seed, 'inputs': N, 'outputs': 8,
                           'same_event_stream_integer_equal': True,
                           'count_bitplanes': T.bit_length(),
                           'fixture_sha256': hashlib.sha256(payload).hexdigest()})
out = {'kind': 'LITERATURE_METRIC_AND_SOFTWARE_IDENTITY_AUDIT_ONLY', 'date': '2026-10-27',
       'counter_source': {'path': str(rtl), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()},
       'geometry': geometry, 'identity_probes': probes,
       'number_of_identity_probes': len(probes),
       'DS_CIM_conditional_bit_normalization': {
           'assumption': 'usual A_bits times W_bits=64 convention; paper full formula not disclosed',
           'DS_CIM2_T64_reported_bit_TOPS_W': 3566.1,
           'conditional_integer_TOPS_W': 3566.1 / 64,
           'DS_CIM2_T256_conditional_integer_TOPS_W': 891.5 / 64,
           'our_T64_integer_TOPS_W': .2687365658883495,
           'our_T64_bit_TOPS_W_if_factor64': .2687365658883495 * 64,
           'divide_by_T_again': False},
       'sources': [
           {'id': 'DS_CIM', 'url': 'https://arxiv.org/html/2601.06724v1',
            'locator': 'III-A/C/D; IV-B/C; V, Tables I-III; PDF pages3,4,6',
            'facts': ['1b input and 1b weight normalization', 'CMR64 replication',
                      'SRR discards low bits', 'LLM accuracy T256, efficiency headline T64',
                      'input row says87.5% sparsity; not automatically ANN zero sparsity']},
           {'id': 'uGEMM', 'url': 'https://jsm.ece.wisc.edu/docs/wu-isca2020.pdf',
            'locator': 'V-C, TablesV/VI; m=k=n=16;45nm400MHz',
            'unipolar_nonscaled_reported_energy_nJ': 70,
            'bipolar_nonscaled_reported_energy_nJ': 130,
            'quality_matched_to_our_LLMS': False},
           {'id': 'SASCHA', 'url': 'https://nanocad.ee.ucla.edu/wp-content/papercite-data/pdf/j72.pdf',
            'locator': 'IV; VII-A/B; binary GEO+, T64 and pruning/training; memory excluded from logic area'},
           {'id': 'tubGEMM', 'url': 'https://arxiv.org/html/2412.17955v1',
            'locator': 'IV-A, TablesI/II;45nm16x16; deterministic temporal unary, not IID SC',
            'unipolar_reported_energy_nJ': 63, 'unipolar_worstcase_latency_us': 5.29}],
       'unverified': ['matched model quality', 'original normalized operation-count formula',
                      'CMR64 utilization for B1 LLM decode', 'new RTL/PPA savings of reassociation'],
       'new_digital_runs': 0, 'no_crossing_nonlinearity_or_feedback': True}
(DOC / 'STOCHASTIC_METRIC_AUDIT.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'geometry': [(x['BINS'], x['PIPE_EVERY'], x['data_register_bits_per_output']) for x in geometry],
                  'same_event_integer_identity_probes': len(probes), 'new_digital_runs': 0}))
