"""Opt-in memory schedules; original DecodeModel and saved results are untouched."""
import math
from system_decode import DecodeModel, WeightMacro, MIB


def match_physical_resources(result):
    """Both routes execute on the SAME superset mixed ASIC, including idle arrays."""
    c = result['config']; seconds = sum(result['time_ns'].values())*1e-9
    count = c['decode_tokens']; E = c['sc_engines']; r = c['rng']; w = c['weight_macro']
    if not result['variant'].startswith(('fixed_sc', 'dual_sc')):
        result['energy_J']['SC_idle'] = E*c['sc_cost']['idle_W_per_engine']*seconds
        result['energy_J']['weight_macro_hold'] = E*w['active_tile_hold_W']*seconds
        result['energy_J']['RNG_sources'] = r['sources']*r['source_power_W']*seconds
        result['energy_J']['RNG_fabric_FIFO'] = r['fifo_distribution_W']*seconds
    area = (w['cache_MiB']*w['area_mm2_per_MiB']
            + c['scratchpad']['capacity_MiB']*c['scratchpad']['area_mm2_per_MiB']
            + c['digital']['area_mm2']
            + E*(c['sc_cost']['logic_area_mm2_per_engine']+w['active_tile_area_mm2'])
            + r['sources']*r['area_mm2_per_source'])
    result['metrics']['parameterized_area_mm2'] = area
    result['metrics']['area_budget_feasible'] = area <= c['area_budget_mm2']
    result['metrics']['scenario_mJ_per_token'] = sum(result['energy_J'].values())*1000/count
    result['resource_matching'] = dict(
        physical_SC_engines=E, physical_digital_MACs_per_cycle=c['digital']['macs_per_cycle'],
        weight_SRAM_MiB=w['cache_MiB'], scratch_MiB=c['scratchpad']['capacity_MiB'],
        uniform_sources=r['sources'], area_mm2=area,
        idle_policy='same always-running sources and same unused-array standby; no new gating benefit')
    return result


class MatchedOriginalDecode(DecodeModel):
    def run(self):
        return match_physical_resources(super().run())


class PinnedWeightMacro(WeightMacro):
    """Static pin/bypass + bounded two-buffer staging within the same weight SRAM.

    DMA->SRAM write and SRAM read use the original ONE shared Link. Nothing
    bypasses memory or gets a new port; the scheduler merely issues DMA earlier.
    """
    def __init__(self, cfg, ext, energy, traffic, chunk, pin):
        super().__init__(cfg, ext, energy, traffic)
        self.staging_bytes = max(2*chunk, 2*8*4096)
        assert self.staging_bytes < cfg['cache_MiB']*MIB
        self.pin_budget = (int(cfg['cache_MiB']*MIB)-self.staging_bytes) if pin else 0
        self.pin_budget = self.pin_budget//self.line*self.line
        self.pin_tensor = 'lm_head'
        self.max_live_bytes = self.staging_bytes

    def request(self, tensor, offset, size, ready):
        first = offset//self.line; last = (offset+size-1)//self.line
        keys = [(tensor, block) for block in range(first, last+1)]
        misses = [key for key in keys if key not in self.cache]
        self.hits += len(keys)-len(misses); self.misses += len(misses)
        done = max([ready]+[self.cache[key] for key in keys if key in self.cache])
        runs = []
        for key in misses:
            if runs and key[1] == runs[-1][-1][1]+1:
                runs[-1].append(key)
            else:
                runs.append([key])
        for run in runs:
            n = len(run)*self.line
            address = self.ext.layout.address(tensor, run[0][1]*self.line, n)
            done = self.ext.access(done, n, 'weights', False, address=address)
            done = self.link.transfer(done, n)
            self.energy['weight_sram_access'] += n*self.cfg['write_pJ_per_byte']*1e-12
            self.traffic['weight_sram_write_bytes'] += n
            for key in run:
                if tensor == self.pin_tensor and key[1]*self.line < self.pin_budget:
                    self.cache[key] = done
        occupied = len(self.cache)*self.line+self.staging_bytes
        assert occupied <= self.cfg['cache_MiB']*MIB
        self.peak = max(self.peak, occupied)
        self.max_live_bytes = max(self.max_live_bytes, occupied)
        n = len(keys)*self.line
        done = self.link.transfer(done, n)
        self.energy['weight_sram_access'] += n*self.cfg['read_pJ_per_byte']*1e-12
        self.traffic['weight_sram_read_bytes'] += n
        return done


class MappedDecode(DecodeModel):
    def __init__(self, cfg, variant, evidence, shape, plan):
        super().__init__(cfg, variant, evidence, shape)
        self.plan = plan.copy()
        self.weights = PinnedWeightMacro(cfg['weight_macro'], self.ext, self.energy,
                                         self.traffic, plan['chunk_bytes'], plan['pin'])
        self.mapping_checks = dict(two_buffer_slots=2, extra_SRAM_bytes=0,
                                   max_staging_bytes=self.weights.staging_bytes)

    def digital_matrix(self, name, inp, out, ready, bytes_per_weight=2):
        c = self.cfg['digital']; total = inp*out*bytes_per_weight
        chunk = self.plan['chunk_bytes']; slots = [ready, ready]
        for i, offset in enumerate(range(0, total, chunk)):
            size = min(chunk, total-offset)
            # Before: next DMA waited for previous compute start. Here two SRAM
            # slots explicitly allow a second DMA while earlier SRAM/compute runs.
            arrived = self.weights.request(name, offset, size, slots[i % 2])
            start = max(arrived, self.digital_free)
            macs = size//bytes_per_weight
            self.digital_free = start+macs/c['macs_per_cycle']*self.period
            slots[i % 2] = self.digital_free
            self.actions['digital_MAC'] += macs
            price = c['mixed_fp_int8_mac_pJ'] if bytes_per_weight == 1 else c['mac_pJ']
            self.energy['digital_MAC'] += macs*price*1e-12
        scratch = (inp+out)*2
        self.energy['scratch_access'] += scratch*self.cfg['scratchpad']['read_pJ_per_byte']*1e-12
        self.traffic['scratch_matrix_interface_bytes'] += scratch
        return self.digital_free

    def attention(self, ready, L, layer):
        s = self.shape; q = s['num_attention_heads']; kv = s['num_key_value_heads']
        d = s['hidden_size']//q; c = self.cfg['digital']; sp = self.cfg['scratchpad']
        block = self.plan['attention_tokens']
        live = 2*(2*kv*d*2*block)+q*d*6+q*8
        assert live <= sp['capacity_MiB']*MIB, 'attention double buffer overflow'
        slots = [ready, ready]; compute = ready
        for i, offset in enumerate(range(0, L, block)):
            n = min(block, L-offset); size = 2*kv*d*2*n
            address = self.ext.layout.address(f'L{layer}/KV', offset*self.ext.layout.kv_token_bytes, size)
            loaded = self.ext.access(slots[i % 2], size, 'KV', False, address=address)
            start = max(loaded, self.digital_free)
            macs = 2*q*d*n; ops = 6*q*n; exp = q*n
            duration = (macs/c['macs_per_cycle']+ops/c['vector_ops_per_cycle']
                        +exp/c['nonlinear_ops_per_cycle'])*self.period
            compute = self.digital_free = start+duration
            slots[i % 2] = compute
            self.actions['attention_QK_PV_MAC'] += macs
            self.actions['digital_MAC'] += macs
            self.actions['softmax_logits'] += exp
            self.energy['digital_MAC'] += macs*c['mac_pJ']*1e-12
            self.energy['digital_vector'] += ops*c['vector_op_pJ']*1e-12
            self.energy['digital_nonlinear'] += exp*c['nonlinear_op_pJ']*1e-12
            self.energy['scratch_access'] += size*(sp['write_pJ_per_byte']+sp['read_pJ_per_byte'])*1e-12
            self.traffic['scratch_KV_tile_bytes'] += 2*size
        return compute

    def stochastic_matrix(self, name, inp, out, ready):
        # Identical operation/RNG counts, replay format, C-major loops and waves.
        assert self.variant == 'fixed_sc_exact', 'this adapter freezes fixed-weight SC'
        assert inp % 64 == out % 64 == 0
        T = self.cfg['samples']; E = self.engines; output_groups = out//64
        current = ready; per_tile_bytes = 4096
        bits = 64*T*self.cfg['rng']['input_bits_per_decision']; replay = bits/8
        sp = self.cfg['scratchpad']
        for k in range(inp//64):
            encoded = self.vectors(current, 64*self.cfg['sc_cost']['input_encode_vector_ops'])
            produced, _ = self.rng_service(encoded, bits)
            current = produced+replay/sp['bandwidth_GBs']
            self.energy['scratch_access'] += replay*sp['write_pJ_per_byte']*1e-12
            self.traffic['random_replay_write_bytes'] += int(replay)
            # Weight DMA is independent of RNG generation. Its bytes/cost remain.
            slots = [encoded, encoded] if self.plan['early_sc_weights'] else [current, current]
            for wave, j in enumerate(range(0, output_groups, E)):
                count = min(E, output_groups-j); tile = k*output_groups+j
                loaded = self.weights.tile_ready(name, tile*per_tile_bytes,
                                                 count*per_tile_bytes, slots[wave % 2], tiles=count)
                start = max(current, loaded)
                kernel = (T+1)*self.period; read = replay/sp['bandwidth_GBs']
                duration = max(kernel, read)
                current = start+duration; slots[wave % 2] = current
                self.sc_compute_ns += kernel; self.replay_ns += read
                self.sc_active_engine_ns += count*kernel
                self.sc_wait_engine_ns += count*(duration-kernel)
                self.actions['sc_tile_frames'] += count
                self.actions['sc_product_trials'] += count*4096*T
                self.energy['SC_logic_active'] += self.sc_kernel_power()*count*kernel*1e-9
                self.energy['SC_wait'] += count*max(0, duration-kernel)*self.cfg['sc_cost']['wait_W_per_engine']*1e-9
                self.energy['scratch_access'] += replay*sp['read_pJ_per_byte']*1e-12
                self.traffic['random_replay_read_bytes'] += int(replay)
            current = self.vectors(current, out*self.cfg['sc_cost']['finalize_vector_ops_per_partial'])
            partial = out*4
            self.traffic['scratch_partial_bytes'] += 2*partial
            self.energy['scratch_access'] += partial*(sp['read_pJ_per_byte']+sp['write_pJ_per_byte'])*1e-12
        return current

    def run(self):
        result = match_physical_resources(super().run())
        result['mapping_plan'] = self.plan
        result['mapping_checks'] = dict(**self.mapping_checks,
            pinned_bytes=len(self.weights.cache)*self.weights.line,
            pin_budget_bytes=self.weights.pin_budget,
            peak_weight_SRAM_bytes=self.weights.max_live_bytes,
            arithmetic_and_SC_loop_order_preserved=True)
        result['implementation'] = 'ZigZag/LOMA-derived DMA blocking + bounded two-buffer TLM schedule'
        return result
