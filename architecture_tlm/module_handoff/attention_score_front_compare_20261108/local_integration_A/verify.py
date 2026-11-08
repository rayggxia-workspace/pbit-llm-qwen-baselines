"""Read archived fixtures; write results only beside this script. Python 3.8+."""
import hashlib
import json
import random
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from adapter import forward_a, legacy_s12_payload, standalone_front_quote, integration_contract, lut, SAMPLER
from architecture_tlm.attention_score_front_20261108 import oracle

FRONT = ROOT / 'architecture_tlm/attention_score_front_20261108'
sources = {}


def read(path):
    data = path.read_bytes()
    sources[str(path.relative_to(ROOT)).replace('\\', '/')] = dict(
        bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    return data.decode('utf-8-sig')


def mem(path):
    return [int(x, 16) for x in read(path).split()]


def independent_a(words, masks):
    # FP32 -> Python double is exact; scaling by 16 is exact, round() is ties-even.
    values = [struct.unpack('<f', struct.pack('<I', u))[0] for u in words]
    active = [bool(m) and ((u >> 23) & 255) != 255 for u, m in zip(words, masks)]
    raw = [round(v * 16) if a else 0 for v, a in zip(values, active)]
    q = [min(2047, max(-2048, v)) for v in raw]
    maximum = max((v for v, a in zip(q, active) if a), default=0)
    gaps = [min(255, maximum - v) if a else 255 for v, a in zip(q, active)]
    flags = (4 * any(m and not a for m, a in zip(masks, active))
             + 2 * any(a and v != r for a, v, r in zip(active, q, raw))
             + int(not any(active)))
    return q, gaps, list(map(int, active)), flags


def replay(threshold, frames, ranks):
    # Functional winner-hold recurrence, NOT GF64/RTL cycle simulation.
    winner = 0
    out = []
    for words, rank in zip(frames, ranks):
        active = [i for i, (r, t) in enumerate(zip(words, threshold)) if r < t]
        if active and winner not in active:
            winner = active[rank % len(active)]
        out.append(winner)
    return out


def main():
    for path in [FRONT / 'profile.py', FRONT / 'oracle.py', FRONT / 'front.sv',
                 FRONT / 'RESULTS_v3.json', FRONT / 'RESULTS_v5.json',
                 SAMPLER / 'sampler.sv', SAMPLER / 'sigmoid.vh', SAMPLER / 'ac_winner128.sv',
                 HERE / 'adapter.py', HERE / 'verify.py']:
        read(path)
    table = lut()
    queries = lanes = legacy_queries = outputs = 0
    for seed in (17, 503, 1009):
        d = FRONT / 'fixtures' / ('s' + str(seed))
        words, masks = mem(d / 'scores.mem'), mem(d / 'mask.mem')
        expected_gap, expected_active, expected_flags = mem(d / 'gap0.mem'), mem(d / 'active0.mem'), mem(d / 'flags0.mem')
        for i in range(len(expected_flags)):
            sl = slice(i * 128, (i + 1) * 128)
            w, m = words[sl], masks[sl]
            q, g, a, f = independent_a(w, m)
            assert (g, a, f) == (expected_gap[sl], expected_active[sl], expected_flags[i])
            result = forward_a(w, m)
            assert (result['gap_u8'], result['active_mask']) == (g, a)
            assert (result['numeric_error'], result['input_saturated'], result['skip_sampler']) == (bool(f & 4), bool(f & 2), bool(f & 1))
            assert result['threshold_p8'] == [table[x] if valid else 0 for x, valid in zip(g, a)]
            if all(a):
                oldq = legacy_s12_payload(w, m)
                assert oldq == q
                oldp8 = [table[min(max(oldq) - v, 255)] for v in oldq]
                assert oldp8 == result['threshold_p8']
                rng = random.Random(seed * 1000 + i)
                frames = [[rng.randrange(256) for _ in range(128)] for _ in range(256)]
                ranks = [rng.getrandbits(32) for _ in frames]
                assert replay(oldp8, frames, ranks) == replay(result['threshold_p8'], frames, ranks)
                legacy_queries += 1
                outputs += 256
            else:
                try:
                    legacy_s12_payload(w, m)
                except ValueError:
                    pass
                else:
                    raise AssertionError('unsupported legacy mask was accepted')
            queries += 1
            lanes += 128
    # A/B discriminating case ensures the wrapper cannot silently take default B.
    w = [oracle.bits(256 + i / 16) for i in range(128)]
    assert set(forward_a(w, [1] * 128)['gap_u8']) == {0}
    assert len(set(oracle.query(w, [1] * 128, 1)[0])) == 128
    cards = {}
    for mhz in (100, 250):
        q = standalone_front_quote(mhz, 1)
        many = standalone_front_quote(mhz, 32, physical_instances=4)
        assert abs(many['work_gross_nJ'] - 32 * q['work_gross_nJ']) < 1e-10
        assert abs(many['area55_mm2'] - 4 * q['area55_mm2']) < 1e-10
        assert many['nominal_input_score_words'] == 1024
        assert q['integrated_query_nJ'] is None
        cards[str(mhz)] = q
    report = dict(status='PASS', scope='CPU_numerical_and_accounting_regression',
                  queries=queries, lanes=lanes, legacy_all_valid_queries=legacy_queries,
                  winner_recurrence_outputs=outputs, seeds=[17, 503, 1009],
                  recurrence_randomness='fixed Python stimulus; modulo rank only for equivalence, not a fair hardware RNG model',
                  RTL_simulated=False, new_PPA=False, new_PPL=False, host_TLM_modified=False,
                  cards=cards, contract=integration_contract(), sources=sources)
    (HERE / 'VALIDATION.json').write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({k: report[k] for k in ('status', 'scope', 'queries', 'lanes', 'legacy_all_valid_queries', 'winner_recurrence_outputs')}))


if __name__ == '__main__':
    main()
