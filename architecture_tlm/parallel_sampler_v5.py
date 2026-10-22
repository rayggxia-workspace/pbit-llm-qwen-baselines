"""Backend-neutral, full-width sampler transactions (Python LT, not RTL).

One query uses all required biased-bit lanes in ONE source transaction.
Source technology and physical costs are deliberately unspecified.  The
behavioral source is an independent sigmoid oracle, not a timed PRNG circuit.
"""
import copy
import hashlib
import json
import math
from collections import Counter


DEFAULT = dict(
    clock_ns=10., drive_bits=32, drive_step=None, drive_max_code=255,
    score_lanes=64, config_bits_per_cycle=256, config_setup_cycles=1,
    source_command_cycles=1, source_settle_cycles=2, source_capture_cycles=1,
    source_min_interval_cycles=1, tree_levels_per_cycle=2,
    decision_cycles=1, commit_cycles=1, fair_capture_cycles=1,
    offset_feedback_cycles=1, offset_update_mode='per_candidate',
    burn_updates=0, winner_shift=0., rank_retry_cap=1024,
    external_source_programming=False,
    max_proposals_per_sample=64, max_shift=24, record_events=False,
    # These are NOT zero-cost defaults. Unknown terms produce null totals.
    energy_pJ={}, idle_W=None, area={},
)
ENERGY_ACTIONS = (
    'biased_bit_draws', 'source_slot_cycles', 'fair_bit_draws',
    'config_bits', 'score_ops', 'winner_count_nodes', 'rejection_flag_nodes',
    'rank_node_visits', 'control_ops', 'buffer_bit_accesses', 'output_indices',
    'macro_active_cycles',
)
AREA_KEYS = ('biased_lane_mm2', 'fair_lane_mm2', 'digital_base_mm2', 'buffer_bit_mm2')


def sigmoid(x):
    if x >= 0:
        return 1. / (1. + math.exp(-x))
    a = math.exp(x)
    return a / (1. + a)


class IdealBitSource:
    """Functional oracle only. draw() is a simultaneous independent vector.

    A future DAC/p-bit or PRNG/comparator backend implements the same two calls.
    Local random.Random is only the numerical driver; its CPU instructions,
    word width and wall time are never used as hardware costs.
    """
    kind = 'ideal_independent_sigmoid_behavior'

    def __init__(self, rng):
        self.rng = rng

    def draw(self, drives):
        return [self.rng.random() < sigmoid(x) for x in drives]

    def fair(self, width):
        return self.rng.getrandbits(width)


class SamplingCapError(RuntimeError):
    """Failed transactions remain charged; partial addresses are NOT returned."""
    def __init__(self, message, receipt):
        super().__init__(message)
        self.receipt = receipt


class Session:
    def __init__(self, module, ready, logits, samples, identity, candidates, output_ns):
        self.module = module
        self.c = module.cfg
        self.logits = tuple(logits)
        self.n = len(logits)
        self.samples = samples
        self.identity = identity
        self.candidates = tuple(candidates)
        self.period = self.c['clock_ns']
        self.start = math.ceil(max(ready, module.free) / self.period)
        self.t = self.start
        self.output_cycles = math.ceil(output_ns / self.period)
        self.actions = Counter()
        # Compact observability is independent of optional per-frame traces.
        # These counters describe the existing FSM; they do not reserve time.
        self.stage_cycles = Counter()
        self.stage_calls = Counter()
        self.events = []
        self.outputs = []
        self.output_times = []
        self.frames = []
        self.source_free = max(self.start, math.ceil(module.source_ready_ns/self.period))
        self.peak_fair = 0
        self.ref = max(range(self.n), key=self.logits.__getitem__)
        self.levels = (self.n - 1).bit_length()
        self.stage('score_max', math.ceil(self.n / self.c['score_lanes']) +
                   (min(self.n, self.c['score_lanes']) - 1).bit_length(),
                   'score_ops', max(0, self.n - 1))
        self.stage('drive_encode', 2 * math.ceil(self.n / self.c['score_lanes']),
                   'score_ops', 2 * self.n)
        # Validity mask covers capacity; only valid candidate drives are written.
        source_lanes = self.n if module.kind == 'winner_hold' else self.n-1
        self.program(source_lanes*self.c['drive_bits'] + module.biased_capacity, 'initial_program')

    def stage(self, name, cycles, action=None, count=0, **detail):
        if type(cycles) is not int or cycles < 0:
            raise ValueError('nonnegative integer stage cycles')
        start = self.t
        self.t += cycles
        self.stage_cycles[name] += cycles
        self.stage_calls[name] += 1
        if action:
            self.actions[action] += count
        if self.c['record_events']:
            self.events.append(dict(name=name, start_cycle=start, end_cycle=self.t,
                                    resource='sampler_fsm', **detail))

    def program(self, bits, name):
        if self.c['external_source_programming']:
            # The actual source frontend owns Q/256 conversion and threshold
            # writes. Do not charge a second fictitious drive programming bus.
            self.actions['delegated_drive_bits'] += bits
            self.stage(name+'_delegated',0)
            return
        self.stage(name, self.c['config_setup_cycles'] +
                   math.ceil(bits / self.c['config_bits_per_cycle']), 'config_bits', bits)

    def encode(self, x):
        step = self.c['drive_step']
        if step is None:
            return x
        return -min(round(max(0., -x) / step), self.c['drive_max_code']) * step

    def draw(self, source, drives):
        if self.c['external_source_programming'] and not hasattr(source,'draw_at'):
            raise ValueError('external source programming requires a timed backend')
        if self.t < self.source_free:
            self.stage('source_interval_wait', self.source_free - self.t)
        started = self.t
        cycles = sum(self.c[k] for k in
                     ('source_command_cycles', 'source_settle_cycles', 'source_capture_cycles'))
        if hasattr(source, 'draw_at'):
            bits, done_ns = source.draw_at(started*self.period, drives)
            if not math.isfinite(done_ns) or done_ns < started*self.period:
                raise ValueError('invalid timed-source completion')
            cycles = math.ceil(done_ns/self.period)-started
            bits = list(bits)
            self.module.provenance.update(source_backend=source.kind,
                independent_ideal_response=False, quantization_changes_target=True,
                source_timing='explicit local PRNG protocol; mapped timing/PPA uncharacterized')
        else:
            bits = list(source.draw(drives))
            if isinstance(source, IdealBitSource):
                self.module.provenance.update(source_backend='UNDECIDED',
                    independent_ideal_response=True,
                    quantization_changes_target=self.c['drive_step'] is not None)
                self.module.provenance.pop('source_timing', None)
        if len(bits) != len(drives) or any(type(b) is not bool for b in bits):
            raise ValueError('source must return one boolean per requested lane')
        self.stage('parallel_source_read', cycles, 'biased_bit_draws', len(bits),
                   parallel_lanes=len(bits), service_waves=1)
        if hasattr(source, 'draw_at'):
            # Source wait/warmup/LUT time is NOT a PRNG update or active lane cycle.
            # Actual work is counted exactly once in the source's cumulative ledger.
            self.actions['timed_source_service_cycles'] += cycles
        else:
            self.actions['source_slot_cycles'] += len(bits) * cycles
        self.actions['buffer_bit_accesses'] += len(bits) * 2
        self.source_free = started + self.c['source_min_interval_cycles']
        self.module.source_ready_ns = self.source_free*self.period
        self.actions['proposal_frames'] += 1
        return bits

    def fair(self, source, width):
        if width == 0:
            return 0
        cycles = self.c['fair_capture_cycles']
        if hasattr(source, 'fair_at'):
            v, done_ns = source.fair_at(self.t*self.period, width)
            if not math.isfinite(done_ns) or done_ns < self.t*self.period:
                raise ValueError('invalid timed fair-source completion')
            cycles = math.ceil(done_ns/self.period)-self.t
        else:
            v = source.fair(width)
        if type(v) is not int or not 0 <= v < (1 << width):
            raise ValueError('invalid fair-bit vector')
        self.stage('parallel_fair_read', cycles,
                   'fair_bit_draws', width, parallel_lanes=width)
        self.peak_fair = max(self.peak_fair, width)
        return v

    def emit(self, index):
        self.stage('address_commit', self.c['commit_cycles'], 'control_ops', 1)
        available = self.t * self.period
        # A one-entry output register. Blocking sink is conservative, bounded,
        # and does not invent extra independent samples while backpressured.
        self.stage('output_transfer', self.output_cycles, 'output_indices', 1)
        self.outputs.append(index)
        self.output_times.append(dict(available_ns=available, consumed_ns=self.t * self.period))

    def close(self, success=True):
        m = self.module
        elapsed = (self.t - self.start) * self.period
        self.actions['macro_active_cycles'] = self.t-self.start
        detail, missing = {}, []
        for action in ENERGY_ACTIONS:
            count = self.actions[action]
            value = self.c['energy_pJ'].get(action)
            if value is None:
                if count:
                    missing.append(action)
            else:
                detail[action] = count * value * 1e-12
        known = sum(detail.values())
        receipt = dict(
            status='completed' if success else 'failed_cap', sampler=m.kind,
            start_ns=self.start * self.period, end_ns=self.t * self.period,
            configured_ns=self.start * self.period,  # corrected below from setup events/cycles
            elapsed_cycles=self.t - self.start, clock_ns=self.period,
            valid_candidates=self.n, capacity=m.capacity, masked_slots=m.capacity-self.n,
            samples=len(self.outputs), requested_samples=self.samples,
            local_indices=list(self.outputs), output_timestamps=self.output_times,
            first_sample_ns=self.output_times[0]['available_ns'] if self.outputs else None,
            config_bits=self.actions['config_bits'], config_bytes=math.ceil(self.actions['config_bits']/8),
            biased_parallel_lanes=self.n if m.kind == 'winner_hold' else self.n-1,
            provisioned_biased_lanes=m.biased_capacity,
            peak_fair_parallel_lanes=self.peak_fair, provisioned_fair_lanes=m.fair_capacity,
            source_backend=m.provenance.get('source_backend','UNDECIDED'), numerical_source=copy.deepcopy(m.provenance),
            actions=dict(self.actions), frames=self.frames, events=self.events,
            stage_cycles=dict(self.stage_cycles), stage_calls=dict(self.stage_calls),
            retained_internal_output_indices=1, energy_J=known,
            known_dynamic_energy_J=known, physical_dynamic_energy_J=None if missing else known,
            energy_breakdown_J=detail, uncharacterized_energy_actions=missing,
            # Compatibility subtotal only; callers MUST propagate completeness.
            cost_status='UNCHARACTERIZED' if missing else 'USER_PARAMETERIZED_NOT_MEASURED',
            service='full-width source, blocking digital FSM, one output register',
            timing_status='configured LT schedule; NOT characterized physical source/RTL timing',
        )
        receipt['configured_ns'] = self.configured_cycle * self.period
        m.free = receipt['end_ns']
        m.active_ns += elapsed
        m.energy_J += known
        m.calls += 1
        m.actions.update(self.actions)
        m.missing_energy.update(missing)
        m.requests.append(receipt)
        return receipt


class ParallelSampler:
    """Serial query sharing; candidate-bit sampling within each query is full width."""
    kind = None

    def __init__(self, cfg=None, capacity=512):
        if type(capacity) is not int or capacity < 1:
            raise ValueError('positive integer capacity')
        unknown = set(cfg or {}) - set(DEFAULT)
        if unknown:
            raise ValueError('unknown sampler configuration: ' + repr(sorted(unknown)))
        self.cfg = copy.deepcopy(DEFAULT)
        self.cfg.update(copy.deepcopy(cfg or {}))
        c = self.cfg
        for k, v in c.items():
            if k in ('energy_pJ', 'area', 'drive_step', 'idle_W', 'record_events', 'offset_update_mode','external_source_programming'):
                continue
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError(k)
            if k not in ('clock_ns', 'winner_shift') and type(v) is not int:
                raise ValueError(k + ' must be integer')
        for k in ('clock_ns', 'drive_bits', 'score_lanes', 'config_bits_per_cycle',
                  'source_capture_cycles', 'source_min_interval_cycles', 'tree_levels_per_cycle',
                  'decision_cycles', 'commit_cycles', 'fair_capture_cycles', 'rank_retry_cap',
                  'max_proposals_per_sample'):
            if c[k] <= 0:
                raise ValueError(k)
        if type(c['record_events']) is not bool:
            raise ValueError('record_events')
        if type(c['external_source_programming']) is not bool:
            raise ValueError('external_source_programming')
        if c['offset_update_mode'] not in ('per_candidate', 'shared_scalar'):
            raise ValueError('offset update mode')
        if c['drive_step'] is not None:
            if not math.isfinite(c['drive_step']) or c['drive_step'] <= 0 or c['drive_max_code'] < 1:
                raise ValueError('drive quantization')
            if c['drive_max_code'] >= 2 ** c['drive_bits']:
                raise ValueError('drive code does not fit payload')
        for name, allowed in (('energy_pJ', ENERGY_ACTIONS), ('area', AREA_KEYS)):
            if set(c[name]) - set(allowed):
                raise ValueError(name + ' contains unknown cost keys')
            for value in c[name].values():
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                    raise ValueError(name)
        if c['idle_W'] is not None and (not math.isfinite(c['idle_W']) or c['idle_W'] < 0):
            raise ValueError('idle_W')
        self.capacity = capacity
        self.biased_capacity = capacity if self.kind == 'winner_hold' else max(0, capacity-1)
        self.fair_capacity = (capacity-1).bit_length() if self.kind == 'winner_hold' else c['max_shift']
        self.free = self.active_ns = self.energy_J = self.source_ready_ns = 0.
        self.calls = 0
        self.actions = Counter()
        self.missing_energy = set()
        self.requests = []
        self.provenance = dict(kind='explicit_sampler_behavior', source_backend='UNDECIDED',
                               independent_ideal_response=True, drive_step=c['drive_step'],
                               hardware_distribution_validated=False,
                               quantization_changes_target=c['drive_step'] is not None)

    @property
    def buffer_bits(self):
        n = self.capacity
        # Concrete conservative registered bitmap + padded reduction tree +
        # one address. Drive state belongs to the source-interface backend.
        padded = 1 << ((n-1).bit_length())
        levels = (n-1).bit_length()
        tree = sum((padded >> level) * (level+1) for level in range(1, levels+1))
        if self.kind != 'winner_hold':
            tree = (padded-1) * (2 + levels)
        return n + tree + 2*max(1, levels) + 1

    def area_receipt(self):
        factors = dict(biased_lane_mm2=self.biased_capacity, fair_lane_mm2=self.fair_capacity,
                       digital_base_mm2=1, buffer_bit_mm2=self.buffer_bits)
        known = sum(n*self.cfg['area'][k] for k,n in factors.items()
                    if self.cfg['area'].get(k) is not None)
        missing = [k for k,n in factors.items() if n and self.cfg['area'].get(k) is None]
        return dict(known_area_mm2=known, physical_area_mm2=None if missing else known,
                    uncharacterized_area_terms=missing, provisioned_buffer_bits=self.buffer_bits,
                    source_drive_storage_in_backend=True)

    @property
    def area_mm2(self):
        return self.area_receipt()['known_area_mm2']

    def begin(self, ready, logits, samples, identity, candidates, output_ns):
        if not math.isfinite(ready) or ready < 0 or not math.isfinite(output_ns) or output_ns < 0:
            raise ValueError('invalid time')
        if type(samples) is not int or samples < 1:
            raise ValueError('sample count')
        if not 1 <= len(logits) <= self.capacity or not all(math.isfinite(x) for x in logits):
            raise ValueError('invalid logits/capacity')
        if len(candidates) != len(logits) or len(set(candidates)) != len(candidates):
            raise ValueError('candidate map')
        if any(type(i) is not int or i < 0 for i in candidates):
            raise ValueError('candidate id')
        s = Session(self, ready, logits, samples, identity, candidates, output_ns)
        s.configured_cycle = s.t
        return s

    def finish(self, end):
        if not math.isfinite(end) or end < self.free:
            raise ValueError('finish before last transaction')
        idle_ns = max(0., end-self.active_ns)
        idle = 0. if self.cfg['idle_W'] is None else idle_ns*1e-9*self.cfg['idle_W']
        missing = sorted(self.missing_energy)
        if self.cfg['idle_W'] is None and idle_ns:
            missing.append('idle_W')
        return dict(calls=self.calls, active_ns=self.active_ns, active_and_config_J=self.energy_J,
                    kind=self.kind,
                    idle_J=idle, capacity=self.capacity, area_mm2=self.area_mm2,
                    **self.area_receipt(), actions=dict(self.actions),
                    numerical_source=self.provenance, internal_rng_separately_charged=False,
                    known_energy_J=self.energy_J+idle,
                    physical_energy_J=None if missing else self.energy_J+idle,
                    uncharacterized_energy_terms=missing,
                    cost_status='UNCHARACTERIZED' if missing else 'USER_PARAMETERIZED_NOT_MEASURED')


def input_sha(logits, candidates):
    raw = json.dumps(dict(logits=list(logits), candidate_ids=list(candidates)),
                     sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()
