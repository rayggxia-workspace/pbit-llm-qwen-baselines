"""Synthetic shared-input projection fixtures and exact-word references.

This module builds operands once, outside timed execution. Counter construction
compresses each input's accepted sample count; a separate temporal direct-dot
reference checks that transformation. All output values are raw FP32 uint32.
SC and digital W8 consume identical FP32 inputs, signed-W8 weights and per-tile
scale words. SC sampling error is expected: numerical equality between methods
is not an acceptance requirement and these fixtures establish no model PPL.

W8 reference order is explicit: 64 non-fused FP32 multiply/add pairs in input
order, one FP32 scale multiply, then ordered FP32 cross-k block additions.
SC keeps PR122's original FUSED=0 per-bin conversion/scale/add order. Both reuse
its pinned exact dyadic arithmetic oracle; no second independent FP32 oracle is
claimed. Integer direct-dot and temporal references are independent of planes.
"""

import hashlib
import json
import random
import struct


REPRESENTATION = 'input_sign_twos_complement'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode('utf-8')).hexdigest()


def word(value):
    """Round a finite fixture literal to a raw FP32 word."""
    return int.from_bytes(struct.pack('<f', value), 'little')


def _positive(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(name + ' must be a positive integer')


def _row_inputs(weights, encoded, thresholds, samples):
    if len(weights) != 64 or any(type(w) is not int or not -128 <= w <= 127 for w in weights):
        raise ValueError('one full row of 64 signed-W8 weights required')
    if samples not in (16, 32, 64) or len(thresholds) != samples:
        raise ValueError('explicit T16/T32/T64 threshold frame required')
    if any(type(t) is not int or not 0 <= t <= 255 for t in thresholds):
        raise ValueError('thresholds must be raw 8-bit integers')
    for field in ('q', 'bins', 'input_sign', 'true_one'):
        if len(encoded[field]) != 64:
            raise ValueError('one full encoded group required: ' + field)
    if any(type(q) is not int or not 0 <= q <= 255 for q in encoded['q']):
        raise ValueError('invalid q')
    if any(type(b) is not int or not 0 <= b <= 3 for b in encoded['bins']):
        raise ValueError('invalid bin')
    if any(type(v) not in (int, bool) or v not in (0, 1)
           for field in ('input_sign', 'true_one') for v in encoded[field]):
        raise ValueError('invalid sign/true-one bit')


def acceptance_counts(encoded, thresholds):
    """Shared sample multiplicity, computed once per input group, never per row."""
    return [len(thresholds) if one else sum(t < q for t in thresholds)
            for q, one in zip(encoded['q'], encoded['true_one'])]


def temporal_direct_bins(weights, encoded, thresholds):
    """Independent small-fixture reference: explicit time/input signed-W8 dot.

    This intentionally does not call acceptance_counts, normalize_counts or
    either plane-counter implementation. It is for checks, not full fixture
    generation or a claim about a physical arithmetic implementation.
    """
    _row_inputs(weights, encoded, thresholds, len(thresholds))
    bins = [0, 0, 0, 0]
    for threshold in thresholds:
        for i, weight in enumerate(weights):
            if encoded['true_one'][i] or threshold < encoded['q'][i]:
                bins[encoded['bins'][i]] += -weight if encoded['input_sign'][i] else weight
    return bins


def count_packet(restore, weights, encoded, thresholds, weight_scale_word,
                 *, samples=32, representation=REPRESENTATION, multiplicities=None):
    """Return raw [bin][rail][plane] counts, direct signed bins and FP32 partial."""
    _row_inputs(weights, encoded, thresholds, samples)
    if representation not in ('input_sign_twos_complement', 'product_sign_magnitude'):
        raise ValueError('explicit supported counter representation required')
    counts_per_input = acceptance_counts(encoded, thresholds)
    if multiplicities is not None:
        if list(multiplicities) != counts_per_input:
            raise ValueError('cached multiplicities differ from actual frozen sample frame')
        counts_per_input = multiplicities
    counters = [[[0] * 8 for _ in range(2)] for _ in range(4)]
    direct_bins = [0, 0, 0, 0]
    for i, weight in enumerate(weights):
        count = counts_per_input[i]
        b, sign = encoded['bins'][i], encoded['input_sign'][i]
        direct_bins[b] += (-weight if sign else weight) * count
        if representation == REPRESENTATION:
            rail, code = int(sign), weight & 255
        else:
            rail, code = int(bool(sign) ^ (weight < 0)), abs(weight)
        for plane in range(8):
            counters[b][rail][plane] += count * ((code >> plane) & 1)
    width = (64 * samples).bit_length()
    normalized = list(restore.normalize_counts(counters, representation=representation,
                      count_width=width, samples=samples))
    if normalized != direct_bins:
        raise AssertionError('bit-plane reconstruction differs from direct signed dot')
    partial = restore.restore_bins(direct_bins, top_exp=encoded['top_exp'],
                                   weight_scale_word=weight_scale_word, samples=samples)
    return dict(counts=counters, signed_bins=direct_bins, top_exp=encoded['top_exp'],
                weight_scale_word=weight_scale_word, sc_word=partial,
                representation=representation, count_width=width)


def w8_dot(restore, words, weights):
    """Declared 64-input non-FMA FP32 dot before the separate tile scale."""
    if len(words) != 64 or len(weights) != 64:
        raise ValueError('digital W8 block must have 64 input values and weights')
    if any(type(v) is not int or not 0 <= v < (1 << 32) or ((v >> 23) & 255) == 255 for v in words):
        raise ValueError('digital inputs must be finite raw FP32 words')
    if any(type(w) is not int or not -128 <= w <= 127 for w in weights):
        raise ValueError('digital weights must be signed W8')
    # The dependency's private oracle is pinned by dependencies.py together with
    # its source SHA. It supplies multiplication not exposed by add_words.
    oracle = restore._oracle()
    accumulator = 0
    for x, w in zip(words, weights):
        accumulator = restore.add_words(accumulator, oracle.mul(x, word(w)))
    return accumulator


def scale_word(restore, unscaled_word, weight_scale_word):
    """One separate FP32 scale multiply via the pinned exact dyadic oracle."""
    if type(unscaled_word) is not int or not 0 <= unscaled_word < (1 << 32):
        raise ValueError('unscaled result must be a raw FP32 word')
    if type(weight_scale_word) is not int or not 0 < weight_scale_word < 0x7f800000:
        raise ValueError('positive finite FP32 weight scale required')
    return restore._oracle().mul(unscaled_word, weight_scale_word)


def w8_partial(restore, words, weights, weight_scale_word):
    """Declared non-FMA FP32 dot followed by one separate FP32 W8 scale."""
    return scale_word(restore, w8_dot(restore, words, weights), weight_scale_word)


def build_fixture(restore, *, seed=0, groups=4, tiles=8, rows_per_tile=64,
                  samples=32, representation=REPRESENTATION):
    """Create one immutable-by-contract operand set for all resource schedules.

    ``packets[k][row]`` and all partial/expected arrays use absolute output row
    ``tile * rows_per_tile + local_row``. A distinct FP32 scale is attached to
    every (k,tile), and the same T/K=T thresholds feed all rows in group k.
    Main runs use 64 rows/tile; smaller row counts are only test fixtures.
    """
    if type(seed) is not int or seed < 0:
        raise ValueError('seed must be a nonnegative integer')
    for name, value in (('groups', groups), ('tiles', tiles), ('rows_per_tile', rows_per_tile)):
        _positive(value, name)
    if rows_per_tile > 64 or samples not in (16, 32, 64):
        raise ValueError('rows_per_tile must be <=64 and samples T16/T32/T64')
    if representation not in ('input_sign_twos_complement', 'product_sign_magnitude'):
        raise ValueError('explicit supported counter representation required')
    rows = tiles * rows_per_tile
    rng = random.Random(seed)
    inputs, packets, sc_partials, w8_partials, w8_unscaled = [], [], [], [], []
    expected_sc, expected_w8 = [0] * rows, [0] * rows
    for k in range(groups):
        words = [word(rng.uniform(-8., 8.)) for _ in range(64)]
        # Shared true-one and W8 signed endpoint probes are present in every
        # workload. Subnormal rounding is tested separately to avoid changing
        # the whole group's dynamic scale into a nonrepresentative fixture.
        words[:8] = [word(v) for v in (8., -8., 2., -2., .5, -.5, 0., -0.)]
        encoded = restore.encode(words, frac=23)
        strata_width = 256 // samples
        thresholds = [s * strata_width + rng.randrange(strata_width) for s in range(samples)]
        scales = [word((1 + rng.randrange(7)) / 256.) for _ in range(tiles)]
        weights = [[rng.randrange(-128, 128) for _ in range(64)] for _ in range(rows)]
        weights[0][:4] = [-128, -128, 127, -127]
        shared_counts = acceptance_counts(encoded, thresholds)
        group_packets, sc_words, digital_words, dot_words = [], [], [], []
        for row in range(rows):
            scale = scales[row // rows_per_tile]
            packet = count_packet(restore, weights[row], encoded, thresholds, scale,
                samples=samples, representation=representation, multiplicities=shared_counts)
            sc = packet['sc_word']
            dot = w8_dot(restore, words, weights[row])
            digital = scale_word(restore, dot, scale)
            group_packets.append(packet)
            sc_words.append(sc)
            digital_words.append(digital)
            dot_words.append(dot)
            expected_sc[row] = restore.add_words(expected_sc[row], sc)
            expected_w8[row] = restore.add_words(expected_w8[row], digital)
        inputs.append(dict(words=words, encoded=encoded, thresholds=thresholds,
                           weights=weights, scale_words=scales,
                           accepted_counts=shared_counts, group=k))
        packets.append(group_packets)
        sc_partials.append(sc_words)
        w8_partials.append(digital_words)
        w8_unscaled.append(dot_words)
    result = dict(schema_version=1, seed=seed, groups=groups, tiles=tiles, rows=rows,
        rows_per_tile=rows_per_tile, samples=samples, strata=samples, representation=representation,
        count_width=(64 * samples).bit_length(), inputs=inputs, packets=packets,
        sc_partials=sc_partials, w8_partials=w8_partials, w8_unscaled=w8_unscaled,
        expected_sc=expected_sc, expected_w8=expected_w8,
        numerical_contract=dict(input='FP32 raw words; no hidden BF16 conversion', weights='signed W8',
            thresholds='one frozen stratified T/K=T frame per k, shared across all output rows/tiles',
            sc='four separate bin conversion/divideT, scale multiply and ordered FP32 bin sum; ordered cross-k add',
            w8='input-order FP32 multiply then FP32 add (non-FMA), one tile-scale multiply, ordered cross-k add',
            reference='shared pinned exact dyadic FP32 oracle; direct integer and temporal dot checks are separate',
            scope='synthetic short projection; no model/PPL/physical IID claim'))
    result['hashes'] = dict(inputs=digest(inputs), packets=digest(packets),
        expected_sc=digest(expected_sc), expected_w8=digest(expected_w8),
        sc_partials=digest(sc_partials), w8_partials=digest(w8_partials),
        w8_unscaled=digest(w8_unscaled))
    result['fixture_sha256'] = digest(result)
    return result
