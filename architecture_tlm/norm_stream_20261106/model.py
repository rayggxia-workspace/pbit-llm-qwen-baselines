"""Two finite norm slots; unchanged BF16 bytes and unchanged arithmetic.

This adapter targets the pinned Issue236 runtime. It does not change frozen
actors, extend their supported Qwen shapes, or supply invented model values.
"""
from contextlib import contextmanager
from types import MethodType


PROFILES = ('resident_2p5', 'stream_2p5', 'stream_2m')
SLOT_BYTES = 16384


@contextmanager
def construction(profile):
    from architecture_tlm.sram_capacity_20261103.depth_banks import DepthSRAM
    from architecture_tlm.common2p5_20261103 import model as common
    from architecture_tlm.digital_baselines_20261104 import factory
    original_region, original_factory = DepthSRAM.region, factory.common_model
    key = '2m_norm_stream'
    sentinel = object()
    previous = common.PROFILES.get(key, sentinel)
    common.PROFILES[key] = (4096,) * 512

    def region(mem, name, size, banks):
        if profile != 'resident_2p5' and name == 'resident_norm_weights':
            name, size, banks = 'norm_double_buffer', 2 * SLOT_BYTES, range(256)
        if profile == 'stream_2m' and name in ('activations_and_codes', 'common_FFN_wide_state'):
            banks = range(256)
        return original_region(mem, name, size, banks)

    def create(*args, **kwargs):
        if profile == 'stream_2m':
            kwargs['profile'] = key
        return original_factory(*args, **kwargs)

    DepthSRAM.region, factory.common_model = region, create
    try:
        yield
    finally:
        DepthSRAM.region, factory.common_model = original_region, original_factory
        if previous is sentinel:
            common.PROFILES.pop(key)
        else:
            common.PROFILES[key] = previous


class NormStore:
    def __init__(self, model, profile):
        from architecture_tlm.unified_v6.shared_memory import Signal
        self.Signal = Signal
        self.m, self.h, self.profile = model, model.h, profile
        self.streaming = profile != 'resident_2p5'
        self.d, self.layers = model.model['hidden'], model.model['layers']
        self.stride = 4 * self.d + 512  # two BF16 RMS gamma and Q/K-headnorm
        if self.stride > SLOT_BYTES or self.stride % 64 or 2*self.d % 64:
            raise ValueError('norm slot shape/alignment outside characterized contract')
        self.logical_bytes = self.layers * self.stride + 2 * self.d
        # Append, rather than shifting any existing weight/KV address.
        self.external = model.a.alloc('normalization_weights', self.logical_bytes)
        self.slots = [dict(tag=None, ready=Signal(), released=Signal(), uses=set()) for _ in range(2)]
        for slot in self.slots:
            slot['released'].set()
        self.events, self.loads = [], {}
        self.gamma_reads = self.headnorm_reads = 0

    def spec(self, tag):
        if not 0 <= tag <= self.layers:
            raise ValueError('invalid norm tag')
        return tag * self.stride, 2 * self.d if tag == self.layers else self.stride

    def load(self, tag):
        if not self.streaming:
            return
        slot = self.slots[tag % 2]
        if slot['tag'] == tag:
            yield slot['ready']
            return
        yield slot['released']
        if slot['tag'] == tag:
            yield slot['ready']
            return
        slot.update(tag=tag, ready=self.Signal(), released=self.Signal(), uses=set())
        offset, size = self.spec(tag)
        self.events.append(dict(event='load_start', tag=tag, slot=tag%2, ns=self.h.now, bytes=size))
        self.loads[tag] = self.loads.get(tag, 0) + 1
        yield from self.h.fetch('norm_prefetch', self.external+offset, size,
            self.m.norm_weights, (tag%2)*SLOT_BYTES, 'norm_weight_stream')
        slot['ready'].set()
        self.events.append(dict(event='ready', tag=tag, slot=tag%2, ns=self.h.now))

    def address(self, tag, kind):
        offset = {'attention':0, 'ffn':2*self.d, 'qk':4*self.d, 'final':0}[kind]
        size = 512 if kind == 'qk' else 2*self.d
        if self.streaming:
            slot = self.slots[tag%2]
            if slot['tag'] != tag or not slot['ready'].ready:
                raise RuntimeError('norm weight read before tagged slot ready')
            slot['uses'].add(kind)
            return (tag%2)*SLOT_BYTES+offset, size
        return tag*self.stride+offset, size

    def norm(self, layer, kind):
        tag = self.layers if kind == 'final' else layer
        yield from self.load(tag)
        offset, size = self.address(tag, kind)
        self.gamma_reads += size
        yield from self.h.transfer(self.m.vector, 0, size, False, 'norm_activation')
        yield from self.h.transfer(self.m.norm_weights, offset, size, False, 'norm_gamma')
        yield from self.m.delay(((self.d+63)//64)*10+30, 'RMSNorm_macro')
        yield from self.h.transfer(self.m.vector, 0, size, True, 'norm_output')

    def headnorm(self, layer):
        yield from self.load(layer)
        offset, size = self.address(layer, 'qk')
        self.headnorm_reads += size
        # The old combined RoPE/headnorm macro had no explicit gamma read.
        # Charge the same read in BOTH sides of the paired experiment.
        yield from self.h.transfer(self.m.norm_weights, offset, size, False, 'headnorm_gamma_explicit')

    def release(self, tag):
        if not self.streaming:
            return
        slot = self.slots[tag%2]
        required = {'final'} if tag == self.layers else {'attention', 'qk', 'ffn'}
        if slot['tag'] != tag or not required <= slot['uses'] or not slot['ready'].ready:
            raise RuntimeError('release before final norm-weight consumer')
        self.events.append(dict(event='release', tag=tag, slot=tag%2, ns=self.h.now))
        slot['released'].set()

    def report(self):
        return dict(profile=self.profile, streaming=self.streaming, slot_count=2 if self.streaming else 0,
            slot_bytes=SLOT_BYTES if self.streaming else 0, logical_weight_bytes=self.logical_bytes,
            resident_bytes=self.m.norm_weights.size, streamed_bytes=sum(self.spec(t)[1]*n for t,n in self.loads.items()),
            load_counts=dict(self.loads), RMS_gamma_read_bytes=self.gamma_reads,
            QK_headnorm_gamma_read_bytes=self.headnorm_reads, events=self.events,
            numeric_change='none: identical BF16 parameter bytes, order and arithmetic; no quantization',
            timing='finite shared DMA/SRAM and tagged ready/release; prefetch overlaps existing QKV phase',
            reference_delta='both paired paths explicitly charge old combined-macro QK-headnorm gamma read')


def install(model, profile):
    controller = NormStore(model, profile)
    parent_phase, parent_rope, parent_run = model.phase, model.rope, model.run
    model.norm_store = controller

    def norm(self, layer, kind):
        yield from controller.norm(layer, kind)

    def rope(self):
        yield from controller.headnorm(self.norm_active_layer)
        yield from parent_rope()

    def phase(self, stage, generators, layer):
        jobs = list(generators)
        if layer >= 0:
            self.norm_active_layer = layer
        if stage == 'embedding' and controller.streaming:
            jobs.append(controller.load(0))
        if stage == 'QKV' and controller.streaming:
            tag = layer+1
            if tag < controller.layers or self.include_lm:
                jobs.append(controller.load(tag))
        result = parent_phase(stage, jobs, layer)
        if stage == 'ffn_norm':
            controller.release(layer)
        if stage == 'final_norm':
            controller.release(controller.layers)
        return result

    def run(self):
        result = parent_run()
        result['norm_storage_contract'] = controller.report()
        return result

    model.norm, model.rope = MethodType(norm, model), MethodType(rope, model)
    model.phase, model.run = MethodType(phase, model), MethodType(run, model)
    return model


def make_model(backend, profile='stream_2m', **kwargs):
    if profile not in PROFILES:
        raise ValueError(profile)
    from architecture_tlm.digital_fair_20261105.joint_handoff.model import make_model as original
    with construction(profile):
        h, model = original(backend, **kwargs)
    install(model, profile)
    return h, model
