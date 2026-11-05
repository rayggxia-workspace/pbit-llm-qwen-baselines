"""No hidden PRNG, array PPA claims, or system-default changes.

Shared-bank estimates use phase-separated LOAD then SAMPLE. Their q/bit holding
fees are mapping residuals of measured kernels, never standalone register PPA.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
from functools import lru_cache

HERE = Path(__file__).resolve().parent


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name)
    return value


def compare8(r8, q):
    """Exact q/256 endpoint contract; rejects out-of-contract inputs."""
    _integer(r8, 0, 255, 'r8 must be unsigned8')
    _integer(q, 0, 256, 'q must be in0..256; probability1 needs a ninth storage bit')
    return int(r8 < q)


@lru_cache(maxsize=1)
def _lut_values():
    return tuple(json.loads((HERE / 'catalog.json').read_text(encoding='utf-8'))['sigmoid_q9'])


def sigmoid_code(drive8):
    """Integer signed8 log-odds code /8; no hidden floating point conversion."""
    _integer(drive8, -128, 127, 'drive8 must be signed8')
    return _lut_values()[drive8 + 128]


class ThresholdBank:
    """Transactional reference, not a new cycle-accurate RTL implementation.

    configure() models an atomic LOAD phase of ceil(nodes/lut_lanes) clocks.
    sample() consumes a caller-supplied random byte for EVERY node. Sampling
    never generates randomness, treats sharing as IID, or modifies the cache.
    """
    def __init__(self, nodes=128, lut_lanes=8, storage_bits=9, clip_p1=False):
        _integer(nodes, 1, 1_000_000, 'nodes')
        _integer(lut_lanes, 1, nodes, 'lut_lanes')
        if storage_bits not in (8, 9) or type(storage_bits) is not int:
            raise ValueError('storage_bits must be8 or9')
        if storage_bits == 8 and not clip_p1:
            raise ValueError('q8 cannot store256; explicitly set clip_p1=True or use q9')
        self.nodes, self.lut_lanes = nodes, lut_lanes
        self.storage_bits, self.clip_p1 = storage_bits, clip_p1
        self._q = None

    def configure(self, drives):
        if len(drives) != self.nodes:
            raise ValueError('one drive per node')
        values = [sigmoid_code(x) for x in drives]
        self._q = tuple(min(q, 255) if self.storage_bits == 8 else q for q in values)
        return {'load_cycles': math.ceil(self.nodes / self.lut_lanes),
                'thresholds': self._q, 'threshold_storage_bits': self.nodes * self.storage_bits,
                'p1_clipped_nodes': sum(q == 256 for q in values) if self.storage_bits == 8 else 0}

    def sample(self, random_words):
        if self._q is None:
            raise RuntimeError('configure before sample')
        if len(random_words) != self.nodes:
            raise ValueError('one externally supplied r8 per node; no implicit broadcast')
        return tuple(compare8(r, q) for r, q in zip(random_words, self._q))


class Catalog:
    """Read-only source data; cost estimates never instantiate a PRNG backend."""
    def __init__(self):
        self.data = json.loads((HERE / 'catalog.json').read_text(encoding='utf-8'))
        source = HERE / 'evidence' / '38427136_SUMMARY.json'
        if hashlib.sha256(source.read_bytes()).hexdigest() != self.data['source']['summary_sha256']:
            raise ValueError('archived summary hash mismatch')
        self._designs = {(d['top'], d['corner']): d for d in self.data['designs']}

    def component(self, top, corner='tt', mode='random', clock_mhz=100,
                  allow_above_reference=False):
        if isinstance(clock_mhz, bool) or not math.isfinite(clock_mhz) or clock_mhz <= 0:
            raise ValueError('positive finite clock_mhz')
        if clock_mhz > 100 and not allow_above_reference:
            raise ValueError('above100MHz is unverified; opt in to algebraic projection explicitly')
        d = self._designs[(top, corner)]
        p = d['modes'][mode]
        # Preserve measured total at100MHz, including report rounding residuals.
        watts = (p['total_W'] - p['leakage_W']) * clock_mhz / 100 + p['leakage_W']
        return {'top': top, 'corner': corner, 'mode': mode,
                'raw_area_um2': d['area_um2'],
                'equivalent55_area_um2': d['area_um2'] * self.data['area_factor'],
                'power_W': watts, 'clock_mhz': clock_mhz,
                'reference_clock_mhz': 100,
                'frequency_evidence': 'measured100MHz_block' if clock_mhz == 100 else 'dynamic_only_frequency_projection',
                'setup_slack_ns_at_reference': d['setup_slack_ns'],
                'hold_slack_ns_at_reference': d['hold_slack_ns'],
                'warnings': deepcopy(d['review_flags']),
                'includes_PRNG': False, 'postlayout': False}

    def _fees(self, corner, clock_mhz, allow_above_reference):
        tops = ['pbit_sigmoid8_lut', 'pbit_sigmoid8_reg', 'pbit_compare8_q256', 'pbit_sample8_reg']
        rows = {t: {m: self.component(t, corner, m, clock_mhz, allow_above_reference)
                    for m in ['idle', 'random']} for t in tops}
        names = dict(zip(['lut', 'reg_lut', 'compare', 'fused'], tops))
        period = 1e-6 / clock_mhz
        def area(n):
            return rows[names[n]]['random']['raw_area_um2']
        def idle(n):
            return rows[names[n]]['idle']['power_W']
        def inc(n):
            return (rows[names[n]]['random']['power_W'] - idle(n)) * period
        fees = {'lut': (area('lut'), idle('lut'), inc('lut')),
                'compare': (area('compare'), idle('compare'), inc('compare')),
                'q_hold_proxy': (area('reg_lut') - area('lut'), idle('reg_lut') - idle('lut'), inc('reg_lut') - inc('lut')),
                'bit_hold_proxy': (area('fused') - area('lut') - area('compare'), idle('fused') - idle('lut') - idle('compare'), inc('fused') - inc('lut') - inc('compare'))}
        if any(v < -1e-20 for triple in fees.values() for v in triple):
            raise ValueError('negative mapping residual; this proxy is not usable')
        return fees, period

    def estimate_window(self, implementation='full_lut', nodes=128, lut_lanes=8,
                        samples_per_configuration=1, corner='tt', clock_mhz=100,
                        inputs_held=False, storage_bits=9, clip_p1=False,
                        allow_above_reference=False):
        """Window with parallel N outputs per SAMPLE clock, LOAD has no outputs.

        Modes: full_lut (existing fused kernel), shared_lut_cached (unmeasured
        composition). Shared cache uses free-running CE clocks; no ICG discount.
        q8 is functionally explicit but pays the SAME q9+valid proxy: no invented
        bit-width scaling or independent8bit bank measurement is implied.
        """
        _integer(nodes, 1, 1_000_000, 'nodes')
        _integer(samples_per_configuration, 1, 1_000_000_000, 'samples_per_configuration')
        if implementation not in ['full_lut', 'shared_lut_cached']:
            raise ValueError('implementation')
        if implementation == 'shared_lut_cached':
            _integer(lut_lanes, 1, nodes, 'lut_lanes')
        if storage_bits not in (8, 9) or type(storage_bits) is not int:
            raise ValueError('storage_bits')
        if implementation == 'shared_lut_cached' and storage_bits == 8 and not clip_p1:
            raise ValueError('q8 loses p=1; acknowledge clip_p1=True or use q9')
        k = samples_per_configuration
        if implementation == 'full_lut' and k > 1 and not inputs_held:
            raise ValueError('reused full LUT requires upstream x retention; acknowledge inputs_held=True and price it upstream')
        fees, period = self._fees(corner, clock_mhz, allow_above_reference)
        shared = implementation == 'shared_lut_cached'
        nlut = lut_lanes if shared else nodes
        load = math.ceil(nodes / nlut) if shared else 0
        cycles = load + k
        counts = {'lut': nodes, 'compare': nodes * (k + int(shared)),
                  'q_hold_proxy': nodes if shared else 0, 'bit_hold_proxy': nodes * k}
        replicas = {'lut': nlut, 'compare': nodes,
                    'q_hold_proxy': nodes if shared else 0, 'bit_hold_proxy': nodes}
        area = sum(replicas[n] * fees[n][0] for n in fees)
        baseline = sum(replicas[n] * fees[n][1] for n in fees)
        increments = {n: counts[n] * fees[n][2] for n in fees}
        baseline_energy = baseline * cycles * period
        energy = baseline_energy + sum(increments.values())
        samples = nodes * k
        evidence = 'shared_composition_proxy_no_array_PPA' if shared else (
            'replicated_measured_fused_kernel' if k == 1 and clock_mhz == 100 else 'field_reuse_or_frequency_projection')
        return {'implementation': implementation, 'evidence': evidence,
                'nodes': nodes, 'lut_replicas': nlut, 'corner': corner, 'clock_mhz': clock_mhz,
                'load_cycles': load, 'sample_cycles': k, 'total_cycles': cycles,
                'latency_first_output_cycles': load + 1,
                'raw_cell_area_um2': area, 'equivalent55_cell_area_mm2': area * self.data['area_factor'] / 1e6,
                'baseline_clock_and_leakage_J': baseline_energy,
                'incremental_operation_J': increments, 'total_window_J': energy,
                'average_power_W': energy / (cycles * period),
                'pJ_per_output_bit': energy / samples * 1e12,
                'outputs': samples, 'effective_per_node_Msample_s': clock_mhz * k / cycles,
                'effective_array_Mbit_s': nodes * clock_mhz * k / cycles,
                'threshold_storage_bits': nodes * storage_bits if shared else 0,
                'q8_price_policy': 'same_q9_valid_proxy_no_width_discount' if shared and storage_bits == 8 else None,
                'p1_max_absolute_probability_error_from_clipping': 1 / 256 if shared and storage_bits == 8 else 0,
                'clock_policy': 'free_running_CE_no_ICG',
                'input_retention': 'external_existing_required' if not shared and k > 1 else 'caller_supplied_during_acceptance',
                'output_retention': 'one_bit_plus_valid_mapping_proxy_per_node',
                'excludes': deepcopy(self.data['excludes']),
                'limits': ['shared selector/write decoder/bank routing not measured or separately priced',
                           'LOAD and SAMPLE do not overlap; adding overlap/double-buffer costs requires another model',
                           'random-budget comparison activity is not a measured constant-q arbitrary-distribution workload',
                           'no array STA, CTS, SPEF, silicon measurement, PRNG or joint-independence claim',
                           'full LUT field retention must actually exist upstream; LUT itself does not store x',
                           'shared q/bit holding fees are arithmetic mapping residuals, not independent-register PPA']}
