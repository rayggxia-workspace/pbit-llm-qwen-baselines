"""Conservative retained-state compute clock gating for the v6 scheduler.

This changes timing only when enabled. It is not power gating: registers and
weights retain state, SRAM/HBM/RNG/seed/program buses remain outside the gate.
An operation's reservation includes its drain; only after completion and a
fixed idle timeout may its local compute clock stop. A new request discovers
the stopped clock at the ordinary resource-ready time, then pays one wake
cycle. It never wakes in anticipation of a future request or memory response.

The policy is a conditional macro, not an implemented ICG/STA proof. Integrated
clock-gate/controller/clock-tree power and wake energy require characterization.
"""
import math

from architecture_tlm.unified_v6.core import Scheduler


COMPUTE_EXACT = frozenset({
    'mac', 'vector', 'locality_accumulator',
    'ffn_SC_bucket_shift_reduce', 'ffn_SC_coefficient16_restore',
    'ffn_SC_cross_tile_add64', 'ffn_SC_fixed4_P8_encode',
    'ffn_SC_fixed4_GU_P8_encode', 'ffn_SC_true_g_signed8',
    'ffn_SC_sigmoid_ROM9', 'ffn_SC_sign_and_exponent_sum',
    'ffn_SC_wide_RNE_BF16',
})


def is_compute_resource(name):
    # Do not match sc_weight_bank, locality_stream, context/seed, or sampler.
    return name in COMPUTE_EXACT or (
        name.startswith('sc:') and name[3:].isdigit())


class ClockGatedScheduler(Scheduler):
    def __init__(self, keep=2000, *, core_period_ns=2., enabled=True,
                 idle_threshold_cycles=8, wake_cycles=1,
                 installed_resources=()):
        super().__init__(keep)
        if not math.isfinite(core_period_ns) or core_period_ns <= 0:
            raise ValueError('positive finite core period required')
        for value in (idle_threshold_cycles, wake_cycles):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError('positive integer gate timeout/wake cycles required')
        self.gate_period = float(core_period_ns)
        self.gating_enabled = bool(enabled)
        self.idle_threshold_cycles = idle_threshold_cycles
        self.wake_cycles = wake_cycles
        self._gate = {}
        for name in installed_resources:
            if not is_compute_resource(name):
                raise ValueError('not a supported compute clock domain: '+name)
            self._state(name)

    def _state(self, name):
        return self._gate.setdefault(name, dict(last_end_ns=0., busy_ns=0.,
            idle_clock_on_ns=0., wakeup_ns=0., off_ns=0., wakeups=0,
            reservations=0))

    def _ceil(self, value):
        return math.ceil(value/self.gate_period-1e-10)*self.gate_period

    def _deadline(self, last_end):
        # Operation completion can be fractional ns; disable only on a core edge.
        return self._ceil(last_end)+self.idle_threshold_cycles*self.gate_period

    def reserve(self, stage, ready, duration, resources, period=0., **detail):
        resources = tuple(sorted(set(resources)))
        selected = tuple(r for r in resources if is_compute_resource(r))
        for r in selected:
            self._state(r)
        # Preserve the exact original Scheduler behavior, trace and counters.
        if not self.gating_enabled or not selected or duration == 0:
            return super().reserve(stage, ready, duration, resources, period, **detail)
        if ready < 0 or duration < 0 or not math.isfinite(ready+duration):
            raise ValueError('invalid time')
        if period and not math.isclose(period, self.gate_period, rel_tol=1e-10):
            raise ValueError('compute gate and operation clocks must agree')
        request = self._ceil(max([ready]+[self.free[r] for r in resources]))
        stopped = {r for r in selected
                   if request >= self._deadline(self._gate[r]['last_end_ns'])-1e-9}
        wake = self.wake_cycles*self.gate_period if stopped else 0.
        # All requested SC domains wake in parallel; no factor of domain count.
        service_ready = request+wake
        before_count = self.count
        done = super().reserve(stage, service_ready, duration, resources,
                               period or self.gate_period, **detail)
        start = done-duration
        self.wait[stage] += service_ready-ready
        if before_count < len(self.events):
            event = self.events[before_count]
            event['ready_ns'] = ready
            event['clock_gate_wakeup_cycles'] = self.wake_cycles if stopped else 0
            event['clock_gate_woken_resources'] = tuple(sorted(stopped))
        for r in selected:
            state = self._gate[r]
            last = state['last_end_ns']
            if r in stopped:
                deadline = self._deadline(last)
                state['idle_clock_on_ns'] += deadline-last
                state['off_ns'] += max(0., request-deadline)
                state['wakeup_ns'] += start-request
                state['wakeups'] += 1
            else:
                # A request arriving before timeout keeps its clock enabled
                # while another simultaneously requested domain wakes.
                state['idle_clock_on_ns'] += start-last
            state['busy_ns'] += duration
            state['last_end_ns'] = done
            state['reservations'] += 1
        return done

    def clock_gating_report(self, end_ns=None):
        end = self.end() if end_ns is None else float(end_ns)
        if not math.isfinite(end) or end < self.end()-1e-8:
            raise ValueError('report horizon must cover every reservation')
        horizon = self._ceil(end)
        domains = {}
        for r, original in sorted(self._gate.items()):
            state = dict(original)
            if self.gating_enabled:
                tail = max(0., horizon-state['last_end_ns'])
                idle_on = min(tail, self._deadline(state['last_end_ns'])-state['last_end_ns'])
                state['idle_clock_on_ns'] += idle_on
                state['off_ns'] += tail-idle_on
            else:
                state.update(busy_ns=self.busy[r], idle_clock_on_ns=horizon-self.busy[r],
                             wakeup_ns=0., off_ns=0., wakeups=0)
            state['clock_on_ns'] = (state['busy_ns']+state['idle_clock_on_ns']+
                                    state['wakeup_ns'])
            state['lifetime_ns'] = horizon
            for key in ('busy_ns','clock_on_ns','off_ns','wakeup_ns'):
                state[key.replace('_ns','_cycles')] = state[key]/self.gate_period
            if abs(state['clock_on_ns']+state['off_ns']-horizon)>max(1e-7,horizon*1e-12):
                raise AssertionError('clock lifetime conservation failed: '+r)
            domains[r] = state
        return dict(enabled=self.gating_enabled, core_period_ns=self.gate_period,
            idle_threshold_cycles=self.idle_threshold_cycles, wake_cycles=self.wake_cycles,
            lifetime_ns=horizon, resources=domains,
            initial_state='clock enabled at time zero; state always retained',
            off_edge_policy='request at timeout edge pays wake; no predictive wakeup',
            excluded='SRAM/HBM/RNG/seed/context/program buses/sampler',
            coverage='installed_resources plus observed selected compute resources; pass installed names to include unused units',
            limitations=['conditional ICG/controller timing macro; no clock tree, gate-cell or wake-energy calibration',
                         'no leakage reduction is implied; this is retained-state clock gating',
                         'reservation must include complete drain before resource idle',
                         'compute held pending after request remains clocked until service'])
