"""Single-zone K64/M128 actor preserving the current28nm result/state pipeline."""
from collections import Counter, deque
from architecture_tlm.unified_v6.shared_memory import Signal, align_time


def program(self, core, layer, mode, out, k):
    assert self.cim_states[core] == 'free' and not self.cim_compute_busy[core]
    self.cim_states[core] = 'loading'
    spans = self._weight_spans(layer, mode, out, k)
    assert sum(n for _, n in spans) == 8192
    yield from self.h.fetch('CIM_core'+str(core), spans[0][0], 8192,
        self.cim_weight[core], 0, 'GU_weights' if mode == 'GU' else 'down_weights', spans=spans)
    self.cim_states[core] = 'ready'


def prefetch_gu(self, layer):
    tiles, _, _ = self._tiles('GU')
    def one(core):
        out, k = tiles[core]
        yield from program(self, core, layer, 'GU', out, k)
        self.common_prefetched.add((layer, core, out, k))
    yield from self._parallel([one(i) for i in range(min(self.common_cores, len(tiles)))])


def common_stage(self, layer, mode):
    service = self.p28_cim_binding['FFN_core']['modes'][mode]
    tiles, outs, blocks = self._tiles(mode); tasks = deque(enumerate(tiles)); n = len(tiles)
    h = self.h; ready = {}; retire = deque(); expected = [0]*outs; occupied = set()
    credits = [0]*self.common_cores
    state_slots = min(self.output_batch, outs) if mode == 'GU' else outs
    owners = [None]*state_slots; input_key = [None]*self.common_cores
    completed = [0]; changed = [Signal()]; stats = Counter(); ports = self.state_port_free
    started = h.now; coverage = set(); previous_commit = [-1]*outs
    def state_slot(out): return out % state_slots
    def notify():
        prior = changed[0]; changed[0] = Signal(); prior.set()
    def loader(core):
        while tasks:
            ix, (out, k) = tasks.popleft(); key = (layer, core, out, k)
            if mode == 'GU' and key in self.common_prefetched:
                self.common_prefetched.remove(key); stats['prefetch_hits'] += 1
            else:
                yield from program(self, core, layer, mode, out, k)
            if mode == 'GU':
                yield from h.transfer(self.vector, 65536+(out*blocks+k)*2, 2, False, 'GU_weight_scale_metadata')
            else:
                base = 65536+2*(self.model['ffn']//64)*(self.model['hidden']//64)
                for plane in range(2):
                    yield from h.transfer(self.vector, base+(2*out+plane)*blocks+k, 1, False, 'Wd_weight_scale_metadata')
            free = Signal(); ready[core] = (ix, out, k, free)
            stats['peak_resident_ready_tiles'] = max(stats['peak_resident_ready_tiles'], len(ready)); notify()
            yield free
    def worker(core):
        while completed[0] < n:
            eligible = [(row[0], slot, row) for slot, row in ready.items()
                if slot == core and row[2] == expected[row[1]] and row[1] not in occupied
                and owners[state_slot(row[1])] in (None, row[1])]
            if credits[core] >= 2 or not eligible:
                why = 'drain' if stats['dispatched_frames'] == n else 'result_credit' if credits[core] >= 2 else 'state_dependency' if ready else 'weight_ready'
                t = h.now; yield changed[0]; stats['wait_'+why+'_core_ns'] += h.now-t; continue
            _, slot, (ix, out, k, free) = eligible[0]; del ready[slot]; occupied.add(out)
            assert self.cim_states[core] == 'ready' and not self.cim_compute_busy[core]
            self.cim_states[core] = 'computing'; self.cim_compute_busy[core] = True
            cell = state_slot(out)
            if owners[cell] is None:
                assert k == 0; owners[cell] = out
                stats['peak_owned_state_groups'] = max(stats['peak_owned_state_groups'], sum(v is not None for v in owners))
            stats['dispatched_frames'] += 1; credits[core] += 1
            stats['peak_core_reserved_results'] = max(stats['peak_core_reserved_results'], credits[core]); notify()
            if input_key[core] != k:
                offset, size = (k*80, 80) if mode == 'GU' else (8192+k*128, 128)
                t = h.now; yield from h.transfer(self.vector, offset, size, False, 'GU_x_codes' if mode == 'GU' else 'NL_gu_codes')
                if mode == 'Wd':
                    yield from h.transfer(self.vector, 65536+self.cross_gu_scale+k, 1, False, 'NL_gu_scale')
                stats['input_load_core_ns'] += h.now-t; stats['input_cache_loads'] += 1; input_key[core] = k
            samples = service['samples']
            yield from self.delay(service['frame_cycles']*10, 'common_'+mode+'_core')
            stats['sample_core_ns'] += service['frame_ns']; stats['sample_frames'] += 1
            self.kernel_active['GU_frames' if mode == 'GU' else 'Wd_M128_frames'] += 1
            self.actions['GU_logical_R8_ports' if mode == 'GU' else 'NL_logical_R8_ports'] += 64*samples*(1 if mode == 'GU' else 3)
            self.actions['common_R8_words'] += samples*(1 if mode == 'GU' else 3)
            self.actions['SC_equivalent_MAC'] += 8192
            assert ix not in coverage; coverage.add(ix)
            self.cim_compute_busy[core] = False; self.cim_states[core] = 'free'
            retire.append((core, out, k)); stats['peak_captured_results'] = max(stats['peak_captured_results'], len(retire))
            free.set(); notify()
    def state_worker(port):
        while completed[0] < n:
            if not retire: yield changed[0]; continue
            core, out, k = retire.popleft(); offset = state_slot(out)*1024
            assert owners[state_slot(out)] == out and previous_commit[out] == k-1
            if k+1 == blocks:
                yield lambda: not self.p28_staging_busy
                self.p28_staging_busy = True
            if k:
                yield from h.transfer(self.common_state, offset, 1024, False, 'common_'+mode+'_state_read')
            begin = max(align_time(h.now, 4), ports[port]); ports[port] = begin+16
            if begin > h.now: yield from h.delay(begin-h.now)
            yield from self.delay(40, 'common_state32_port')
            self.actions['common_state32_vectors'] += 4; self.actions['crossK_updates'] += 128
            if k+1 < blocks:
                yield from h.transfer(self.common_state, offset, 1024, True, 'common_'+mode+'_state_write')
            else:
                yield from self.p28_finish_output(self, mode)
                if mode == 'GU':
                    yield from h.transfer(self.vector, 8192+out*128, 128, True, 'GU_quantized_output')
                    yield from h.transfer(self.vector, 65536+self.cross_gu_scale+out, 1, True, 'GU_scale_output')
                else:
                    yield from h.transfer(self.vector, out*256, 256, True, 'FFN_BF16_output')
                self.p28_staging_busy = False
            previous_commit[out] = k; expected[out] = k+1; occupied.remove(out)
            if k+1 == blocks: owners[state_slot(out)] = None
            credits[core] -= 1; completed[0] += 1; notify()
    yield from self._parallel([loader(i) for i in range(min(self.common_cores, n))]
        + [worker(i) for i in range(self.common_cores)] + [state_worker(i) for i in range(self.state_ports)])
    assert len(coverage) == completed[0] == n and not ready and not retire and not occupied and not any(credits)
    assert all(k == blocks for k in expected) and not self.common_prefetched
    assert not any(self.cim_compute_busy) and all(v == 'free' for v in self.cim_states)
    elapsed = h.now-started
    self.common_stats.append(dict(layer=layer, mode=mode, state_slots=state_slots,
        state_capacity_bytes=self.common_state.size, output_batch=self.output_batch, frames=n,
        output_groups=outs, Kblocks=blocks, physical_common_cores=self.common_cores, elapsed_ns=elapsed,
        core_sampling_utilization=stats['sample_core_ns']/(self.common_cores*elapsed),
        frame_cycles=service['frame_cycles'], samples_per_frame=service['samples'],
        frame_service_ns=service['frame_ns'], profile_sha256=self.p28_binding_sha, **dict(stats)))
