"""Feasible bounded tile schedule. Link/macros, NOT DRAMSys/STA measurements."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class Config:
    tile: int = 64
    slots: int = 2
    clock_ns: float = 10.
    memory_bytes_per_cycle: int = 32
    memory_latency: int = 20
    mac_per_cycle: int = 64
    mac_latency: int = 14
    vector_per_cycle: int = 16
    vector_latency: int = 7
    local_bytes_per_cycle: int = 32
    local_latency: int = 2
    local_capacity: int = 262144


class Schedule:
    def __init__(self, cfg):
        self.cfg, self.free, self.events = cfg, {}, []

    def op(self, name, resource, ready, work, rate, latency):
        if work == 0:
            return ready
        start = max(ready, self.free.get(resource, 0))
        issue = math.ceil(work/rate)
        done = start+issue+latency
        # Pipelined resource may accept the next independent tile during drain.
        self.free[resource] = start+issue
        self.events.append(dict(name=name, resource=resource, start=start, end=done,
                                issue_end=start+issue, work=work))
        return done

    def memory(self, name, ready, bytes_):
        c = self.cfg
        return self.op(name, 'memory_link', ready, bytes_, c.memory_bytes_per_cycle, c.memory_latency)

    def vector(self, name, ready, ops):
        c = self.cfg
        return self.op(name, 'vector', ready, ops, c.vector_per_cycle, c.vector_latency)

    def mac(self, name, ready, ops):
        c = self.cfg
        return self.op(name, 'mac', ready, ops, c.mac_per_cycle, c.mac_latency)

    def local(self, name, ready, bytes_):
        c = self.cfg
        return self.op(name, 'local_sram', ready, bytes_, c.local_bytes_per_cycle, c.local_latency)


def run(row, d, cfg=Config()):
    c, mode = cfg, row['mode']
    if d not in (64,128):
        raise ValueError('this burst/feedback contract supports d64/d128')
    if min(c.tile, c.slots, c.mac_per_cycle, c.vector_per_cycle, c.memory_bytes_per_cycle, c.local_bytes_per_cycle) < 1:
        raise ValueError('positive resources')
    s = Schedule(c)
    ids = row['candidates']
    t = 0
    screen = row.get('screen')
    extra_bytes = 0
    if screen:
        # Warm summaries: appended K already arrives via common KV write path.
        t = s.vector('summary_append', t, screen['append_summary_adds'])
        t = s.local('summary_append_write', t, screen['append_summary_write_bytes'])
        t = s.local('summary_read', t, screen['summary_read_bytes'])
        t = s.mac('summary_QK', t, screen['summary_dot_MAC'])
        t = s.vector('screen_standardize_sigmoid_Bernoulli', t, 6*screen['blocks'])
        t = s.vector('quota_sort_upper_macro', t, screen['repair_sort_comparisons_upper'])
        t = s.local('candidate_map_write', t, 4*len(ids))
        extra_bytes = screen['summary_read_bytes']+screen['append_summary_write_bytes']+4*len(ids)
    slot_free = [t]*c.slots
    online_ready, scores_ready = t, t
    tiles = [ids[i:i+c.tile] for i in range(0, len(ids), c.tile)]
    for it, tile in enumerate(tiles):
        slot = it % c.slots
        loaded = s.memory('K_read', slot_free[slot], len(tile)*d*2)
        scored = s.mac('QK', loaded, len(tile)*d)
        if mode in ('D0', 'P1'):
            # Legal online dependence on previous max, denominator and output.
            weights = s.vector('online_max_exp_sum_rescale', max(scored, online_ready), 5*len(tile)+d+2)
            v_ready = s.memory('V_read', loaded, len(tile)*d*2)
            online_ready = s.mac('PV', max(weights, v_ready), len(tile)*d)
            slot_free[slot] = online_ready
        else:
            stored = s.local('score_write', scored, len(tile)*4)
            scores_ready = max(scores_ready, stored)
            slot_free[slot] = stored
    state_bytes = c.slots*c.tile*d*4 + d*16  # two BF16 K/V tiles + FP64 reference state allowance
    if mode in ('D0', 'P1'):
        done = s.vector('final_reciprocal_scale', online_ready, d+1)
        # No length-L probability or score array charged to online dense path.
    else:
        t = scores_ready
        n = len(ids)
        state_bytes += n*12  # FP32 score/mass + uint32 count
        if mode in ('P0', 'P2'):
            t = s.local('score_scan', t, n*4)
            t = s.vector('stable_softmax', t, 5*n)
            t = s.local('probability_write', t, n*4)
            t = s.local('CDF_scan', t, n*4)
            t = s.vector('systematic_counts', t, n+row['samples'])
        else:
            t = s.local('sampler_score_scan', t, n*4)
            # Exact legacy PR88 receipt: includes source, reduction, retries,
            # initialization, offset update and one-entry output protocol.
            duration = math.ceil(row['sampler']['elapsed_cycles']*row['sampler']['clock_ns']/c.clock_ns)
            s.events.append(dict(name='sampler_PR88', resource='sampler', start=t, end=t+duration,
                                 issue_end=t+duration, work=row['sampler']['actions'].get('proposal_frames', 0)))
            t += duration
            state_bytes += math.ceil(row['sampler']['area_contract']['provisioned_buffer_bits']/8)
        # One update per emitted address. This conservative stage is explicit;
        # it can be overlapped only with a separately validated sink adapter.
        t = s.local('histogram_RMW', t, 8*row['samples'])
        t = s.local('histogram_map_scan', t, n*8)
        slot_free = [t]*c.slots
        acc_ready = t
        for it, (address, count) in enumerate(row['counts'].items()):
            slot = it % c.slots
            # Row-aligned d64/d128 uses exact 64B bursts; tests reject other d.
            loaded = s.memory('V_gather', slot_free[slot], d*2)
            # Repeated samples revisit the same d accumulators. Independent
            # II1 add latency is NOT same-context II1. Restrict issued lanes
            # so every accumulator has at least vector_latency clocks to return.
            feedback_lanes=min(c.vector_per_cycle,max(1,d//max(1,c.vector_latency)))
            acc_ready = s.op('V_repeated_add','vector',max(acc_ready,loaded),
                             count*d,feedback_lanes,c.vector_latency)
            slot_free[slot] = acc_ready
        done = s.vector('sample_average', acc_ready, d)
    if screen:
        state_bytes += screen['summary_read_bytes']+4*len(ids)
    if state_bytes > c.local_capacity:
        raise ValueError('explicit local SRAM capacity exceeded')
    return dict(cycles=done, ns=done*c.clock_ns, config=asdict(c), events=s.events,
                allocated_local_bytes=state_bytes, screen_local_extra_bytes=extra_bytes,
                timing_kind='conditional feasible Link/tile macros; no DRAMSys or bank-specific STA',
                memory_link_bytes=sum(e['work'] for e in s.events if e['resource']=='memory_link'),
                energy_J=None, area_mm2=None,
                missing_costs=['MAC/vector implementation', 'random service', 'control/clock/idle',
                               'summary conversion', 'SRAM peripherals/interconnect', 'external memory'],
                summary_cache='warm maintained; cold full-K construction separately reported' if screen else None)
