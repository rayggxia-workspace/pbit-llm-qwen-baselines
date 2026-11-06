"""One shared BF16 pool for all ordinary projections and all three FFN matrices.

Attention QK/PV retains the existing dedicated resources. SRAM/DMA capacity,
ports and external timing are inherited unchanged. No numerical inference.
"""
import copy
from architecture_tlm.digital_fair_20261105.model import FairDigitalDecode, Configuration, fma_cycles
from architecture_tlm.digital_baselines_20261104.model import BaselineDecode
from architecture_tlm.unified_v6.shared_decode import spans_tile
from architecture_tlm.unified_v6.shared_memory import Signal
from architecture_tlm.digital_fair_20261105.time_audit import check_exclusive_time


class BF16EqualAreaDecode(FairDigitalDecode):
    def configure_bf16(self, profile):
        self.profile = copy.deepcopy(profile)
        self.configure_fair(Configuration('BF16_equal_area', wd_lanes=profile['lanes'],
            wd_k_parallel=32, wd_k_tile=128, ffn_prefetch_slots=4, contexts=4))
        assert self.configuration.output_tile * 128 * 2 <= 65536
        self.digital_contract.update(physical_FMA_lanes=profile['lanes'],
            non_FFN_active_FMA_lanes=profile['lanes'], K_parallel_lanes_per_output=32,
            BF16_all_matrix_K_tile=128, BF16_all_matrix_output_tile=self.configuration.output_tile,
            ordinary_FMA_lanes=profile['lanes'], W8_GU_N64_dot_units=0,
            W8_down='absent', numerical_change='BF16 weights/operands, FP32 feedback and reduction; K32/c4 scheduling',
            resource_sharing='single FMA pool shared sequentially by QKV/O/g/u/down/lm_head; QK/PV separate',
            input_holding='one BF16 input vector, no duplicate full weight registers',
            fixed_area_profile=copy.deepcopy(profile))

    def matrix_tasks(self, layer, name, outputs, inputs, element=2):
        assert element == 2, 'this actor never decodes W8 or samples FFN'
        base = self.lm_base if name == 'lm_head' else self.weight_bases[layer, name]
        c = self.configuration
        tasks = []
        for out0 in range(0, outputs, c.output_tile):
            nout = min(c.output_tile, outputs - out0)
            for k in range(0, inputs, c.wd_k_tile):
                count = min(c.wd_k_tile, inputs - k)
                spans = spans_tile(base, out0, nout, k, inputs, count, 2, self.weight_layout)
                assert sum(n for _, n in spans) == nout * count * 2 <= 65536
                tasks.append((spans, nout * count, out0, nout, k + count == inputs))
        return tasks

    def digital_matrix(self, layer, name, outputs, inputs, element=2):
        begin = self.h.now
        tasks = self.matrix_tasks(layer, name, outputs, inputs, element)
        signals, loaders = {}, {}
        window = self._window(name)
        audit = dict(layer=layer, name=name, tasks=len(tasks), input_init_ns=0,
            weight_ready_wait_ns=0, operand_service_ns=0, arithmetic_tail_ns=0,
            reduction_output_ns=0, arithmetic_service_ns=0, weight_bytes=0,
            logical_MAC=0, reduction_ADD=0)

        def loader(ix, slot):
            if (layer, name, ix) in self.prefetched:
                self.prefetched.remove((layer, name, ix))
                self.actions['ordinary_prefetch_hits'] += 1
            else:
                yield from self._load_matrix(layer, name, tasks[ix][0], slot, ix)
            signals.setdefault(ix, Signal()).set()

        def driver():
            started = self.h.now
            source = 98304 if name == 'down' else 0
            yield from self.h.transfer(self.vector, source, inputs * 2, False, name + '_activation_to_local')
            audit['input_init_ns'] += self.h.now - started
            for ix, (spans, work, out0, nout, last_k) in enumerate(tasks):
                slot = ix % window
                if ix == 0:
                    for j in range(min(window, len(tasks))):
                        loaders[j] = loader(j, j)
                started = self.h.now
                yield signals.setdefault(ix, Signal())
                audit['weight_ready_wait_ns'] += self.h.now - started
                start = self.h.now
                region, offset = self._location(layer, name, slot)
                nbytes = sum(n for _, n in spans)
                yield from self.h.transfer(region, offset, nbytes, False, name + '_operand')
                cycles = fma_cycles(nout, work // nout, self.profile['lanes'], 32)
                self.actions['digital_BF16_MAC'] += work
                audit['operand_service_ns'] += self.h.now - start
                audit['arithmetic_service_ns'] += cycles * 10
                tail = max(0, start + cycles * 10 - self.h.now)
                if tail:
                    yield from self.h.delay(tail)
                audit['arithmetic_tail_ns'] += tail
                self.work_digest.update(('%s/%d/%d/%d/%d' % (name, layer, ix, work, nbytes)).encode())
                signals.pop(ix)
                lease = self.slot_leases.pop((region.name, offset))
                assert lease[:3] == (layer, name, ix)
                audit['weight_bytes'] += nbytes
                audit['logical_MAC'] += work
                output_start = self.h.now
                if last_k:
                    count = nout * 31
                    self.actions['digital_FP32_reduce_ADD'] += count
                    audit['reduction_ADD'] += count
                    yield from self.delay(self.reduction_cycles(nout, 32, self.reduction_adders) * 10,
                                          'digital_final_K_reduction')
                    if name == 'lm_head':
                        yield from self.delay(70, 'streaming_argmax_macro')
                        self.actions['argmax_compares'] += nout
                    else:
                        dest = {'g': 32768, 'u': 65536}.get(name, 0)
                        yield from self.delay(40, 'matrix_BF16_RNE')
                        yield from self.h.transfer(self.vector, dest + out0 * 2, nout * 2, True, name + '_output')
                audit['reduction_output_ns'] += self.h.now - output_start
                nxt = ix + window
                if nxt < len(tasks):
                    loaders[nxt] = loader(nxt, slot)
            self.unpriced['digital_activation_hold_bytes_peak'] = max(
                self.unpriced['digital_activation_hold_bytes_peak'], inputs * 2)

        yield from self._managed(driver(), loaders)
        audit['elapsed_ns'] = self.h.now - begin
        check_exclusive_time(audit)
        self.matrix_audit.append(audit)

    def run(self):
        result = BaselineDecode.run(self)
        assert not self.slot_leases
        result['executed_resources'].update(ordinary_MAC_lanes=self.profile['lanes'],
            physical_ordinary_FMA_lanes=self.profile['lanes'],
            FFN_Wd_active_FMA_lanes=self.profile['lanes'], FFN_GU_active_FMA_lanes=self.profile['lanes'],
            FFN_prefetch_slots=4, physical_SparQ_selector=False, W8_N64_dot_units=0)
        result['matrix_wait_audit'] = self.matrix_audit
        result['peak_live_weight_bytes'] = self.peak_live_weight_bytes
        result['BF16_equal_area_profile'] = copy.deepcopy(self.profile)
        result['attention_adapter_contract'] = copy.deepcopy(self.attention_adapter_contract)
        return result


def make_model(backend, profile, **kwargs):
    from architecture_tlm.digital_baselines_20261104.factory import make_model as original_model
    from architecture_tlm.digital_fair_20261105.joint_handoff.attention.adapter import install
    hub, model = original_model(backend, 'D_BF16_dense', **kwargs)
    model.__class__ = BF16EqualAreaDecode
    model.configure_bf16(profile)
    install(model, 'dense')
    return hub, model
