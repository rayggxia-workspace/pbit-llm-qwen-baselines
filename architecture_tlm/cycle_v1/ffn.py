"""A bounded, data-carrying FFN tile chain for the cycle_v1 scheduler.

This is a conditional architecture model, not characterized RTL. The arithmetic
uses the original signed-rail/bit-plane counters by default, with a separately
named signed-bin alternative (not evidence of a physical area improvement),
FP32 restoration/cross-tile addition, continuous SiLU, and separate x/z streams.
Python Random supplies local behavioral words; it is not a physical RNG model.
"""
from dataclasses import dataclass
import math
import random
import struct

from .contracts import Buffer, Clock, Operation, Resource
from .kernel import Kernel
from .memory import MemoryPort, MemoryRequest


def fp32(value):
    return struct.unpack('<f', struct.pack('<f', float(value)))[0]


def bf16(value):
    bits = struct.unpack('<I', struct.pack('<f', fp32(value)))[0]
    if bits & 0x7f800000 == 0x7f800000:
        return fp32(value)
    bits = (bits + 0x7fff + ((bits >> 16) & 1)) & 0xffff0000
    return struct.unpack('<f', struct.pack('<I', bits))[0]


def sigmoid(value):
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


@dataclass(frozen=True)
class FFNConfig:
    samples: int = 32
    strata: int = 32
    bins: int = 4
    tile: int = 64
    seed: int = 0
    count_bits: int | None = None
    counter_layout: str = 'bitplane'
    engines: int = 8
    weight_slots: int = 8
    weight_slot_bytes: int = 4096
    weight_scale_capacity_bytes: int = 32
    counter_capacity_bytes: int = 49152
    encoded_capacity_bytes: int = 256
    partial_capacity_bytes: int = 65536
    output_bf16: bool = True
    encode_latency: int = 7
    restore_latency: int = 4
    nonlinear_latency: int = 8
    sc_latency: int = 1
    rng_latency: int = 1
    vector_lanes: int = 16
    cdc_cycles: int = 3

    @property
    def counter_width(self):
        required=(self.samples*self.tile).bit_length() if self.counter_layout=='bitplane' else (self.samples*self.tile*128).bit_length()+1
        return self.count_bits if self.count_bits is not None else required

    def validate(self):
        if self.tile != 64 or self.bins not in (2, 4):
            raise ValueError('reference requires 64-lane groups and B2/B4')
        if self.counter_layout not in ('bitplane','signed_bin'):
            raise ValueError('counter_layout must be bitplane or signed_bin')
        if (type(self.samples) is not int or type(self.strata) is not int or
                self.samples < 1 or self.strata < 1 or
                256 % self.strata or self.samples % self.strata):
            raise ValueError('strata must divide 256 and positive sample count')
        if type(self.seed) is not int or (self.count_bits is not None and type(self.count_bits) is not int):
            raise ValueError('integer seed and counter width required')
        required=(self.samples*self.tile).bit_length() if self.counter_layout=='bitplane' else (self.samples*self.tile*128).bit_length()+1
        if self.counter_width < required:
            raise ValueError('counter cannot hold configured full-frame endpoint')
        for name in ('engines','weight_slots', 'weight_slot_bytes','weight_scale_capacity_bytes', 'counter_capacity_bytes',
                     'encoded_capacity_bytes', 'partial_capacity_bytes',
                     'encode_latency', 'restore_latency', 'nonlinear_latency',
                     'sc_latency', 'rng_latency', 'vector_lanes'):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(name + ' must be positive integer')
        if type(self.cdc_cycles) is not int or self.cdc_cycles<1:
            raise ValueError('positive destination-edge CDC visibility count required')


def encode_group(values, bins=4):
    """PoT encode one real/tail group, rounding on the FP32 A8 grid."""
    values = [fp32(x) for x in values]
    if not values or len(values) > 64 or any(not math.isfinite(x) for x in values):
        raise ValueError('one finite group of 1..64 values required')
    maximum = max(abs(x) for x in values)
    mantissa, exponent = math.frexp(maximum)
    exponent = 0 if maximum == 0 else exponent - (mantissa == .5)
    top = fp32(math.ldexp(1.0, exponent))
    out = []
    for x in values:
        scale, bin_id = top, 0
        for index in range(1, bins):
            candidate = max(fp32(top * 4.0 ** -index), 2.0 ** -126)
            if abs(x) <= candidate:
                scale, bin_id = candidate, index
        q = min(255, max(0, round(fp32(abs(x) * fp32(256.0 / scale)))))
        out.append(dict(q=q, sign=(x > 0) - (x < 0), scale=scale,
                        bin=bin_id, full_one=(abs(x) >= scale and x != 0)))
    return out


def threshold_words(config, phase, group, fixture=None):
    """Replay per-group words or generate independent equal-range strata.

    Replay JSON shape is thresholds:{x:[[T words]...],z:[[T words]...]}.
    This preserves shared64 and cross-bin correlation; no lane-wise Binomial.
    """
    replay = (fixture or {}).get('thresholds', {}).get(phase)
    if replay is not None:
        words = list(replay[group])
    else:
        rng = random.Random(config.seed * 1000003 + group * 97 +
                            (700001 if phase == 'x' else 700002))
        width = 256 // config.strata
        words = [k * width + rng.randrange(width)
                 for k in range(config.strata)
                 for _ in range(config.samples // config.strata)]
    if len(words) != config.samples or any(type(x) is not int or not 0 <= x < 256 for x in words):
        raise ValueError('invalid threshold replay')
    occupancy = [0] * config.strata
    for word in words:
        occupancy[word // (256 // config.strata)] += 1
    if occupancy != [config.samples // config.strata] * config.strata:
        raise ValueError('replay is not the configured stratified sequence')
    return words


def matrix_spec(value, tile=64):
    """Accept raw rows or {codes:rows, scales:[row_tile][column_tile]}.

    Prequantized scales must come from the full historical tile when exporting
    cropped rows. Raw fixtures quantize their own explicit (possibly tail) tile.
    """
    prequantized = isinstance(value, dict)
    rows = value['codes'] if prequantized else value
    if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
        raise ValueError('nonempty rectangular matrix required')
    nr, nc = len(rows), len(rows[0])
    codes = [[0] * nc for _ in range(nr)]
    scales = [[0.0] * math.ceil(nc / tile) for _ in range(math.ceil(nr / tile))]
    if prequantized:
        if (len(value['scales']) != len(scales) or
                any(len(row) != len(scales[0]) for row in value['scales'])):
            raise ValueError('tile scale shape mismatch')
        for i, row in enumerate(rows):
            if any(type(x) is not int or not -128 <= x <= 127 for x in row):
                raise ValueError('W8 codes must be integers in -128..127')
            codes[i] = list(row)
        for i, row in enumerate(value['scales']):
            for j, x in enumerate(row):
                if not math.isfinite(x) or x <= 0:
                    raise ValueError('weight scale must be positive finite')
                scales[i][j] = fp32(x)
    else:
        rows = [[fp32(x) for x in row] for row in rows]
        if any(not math.isfinite(x) for row in rows for x in row):
            raise ValueError('finite weights required')
        for r in range(0, nr, tile):
            for c in range(0, nc, tile):
                scale = fp32(max(1e-20, max(abs(x) for row in rows[r:r+tile]
                                            for x in row[c:c+tile])) / 127.0)
                scales[r//tile][c//tile] = scale
                for i in range(r, min(nr, r+tile)):
                    for j in range(c, min(nc, c+tile)):
                        codes[i][j] = min(127, max(-127, round(fp32(rows[i][j] / scale))))
    return dict(codes=codes, scales=scales, rows=nr, cols=nc)


def default_resources(config=None):
    c = config or FFNConfig()
    clock = Clock('core', 10000)
    return [Resource('control', clock, 1, capacity=16),
            Resource('encode', clock, c.encode_latency, capacity=2),
            Resource('restore', clock, c.restore_latency, capacity=2),
            Resource('nonlinear', clock, c.nonlinear_latency, capacity=2),
            Resource('vector', clock, 2, capacity=2),
            Resource('rng', clock, c.rng_latency, capacity=2)]+[
            Resource('sc:'+str(i),clock,c.sc_latency,capacity=1) for i in range(c.engines)]


def default_buffers(config=None, prefix='ffn'):
    c = config or FFNConfig()
    return [Buffer(prefix+'.weights', c.weight_slots*c.weight_slot_bytes,
                   initial=c.weight_slots*c.weight_slot_bytes),
            Buffer(prefix+'.scales',c.weight_scale_capacity_bytes,initial=c.weight_scale_capacity_bytes),
            Buffer(prefix+'.counters', c.counter_capacity_bytes, initial=c.counter_capacity_bytes),
            Buffer(prefix+'.encoded', c.encoded_capacity_bytes, initial=c.encoded_capacity_bytes),
            Buffer(prefix+'.partials', c.partial_capacity_bytes, initial=c.partial_capacity_bytes)]


def make_kernel(config=None, memory_latency=4):
    c = config or FFNConfig()
    return Kernel(default_resources(c), default_buffers(c), memory_ports=[
        MemoryPort('dram', Clock('dram', 12500), latency_cycles=memory_latency, window=4,strict_reads=True),
        MemoryPort('sram', Clock('sram', 12500), latency_cycles=2, window=4,strict_reads=True)])


def build_ffn(kernel, fixture, config=None, prefix='ffn'):
    """Append a complete cropped/small FFN chain; return mutable result state.

    Matrix input dimensions are never truncated. All input tiles reduce before
    the nonlinear barrier. Projection output rows may explicitly be cropped by
    the fixture. Numerical values are frozen inputs; memory requests carry their
    exact addresses/bytes and completion, not a post-hoc traffic subtraction.
    """
    c = config or FFNConfig()
    c.validate()
    x = [fp32(v) for v in fixture['x']]
    matrices = {name: matrix_spec(fixture[name]) for name in ('wg', 'wu', 'wd')}
    wg, wu, wd = [matrices[n] for n in ('wg', 'wu', 'wd')]
    if not x or wg['cols'] != len(x) or wu['cols'] != len(x) or wg['rows'] != wu['rows'] or wd['cols'] != wg['rows']:
        raise ValueError('FFN matrix dimensions do not compose')
    residual = [fp32(v) for v in fixture.get('residual', [0.0]*wd['rows'])]
    if len(residual) != wd['rows'] or any(not math.isfinite(v) for v in x+residual):
        raise ValueError('finite residual must match down output dimension')
    # Conservative simultaneous g/u/z/down/residual allocation; no implicit
    # aliasing of z with a released g/u region is assumed.
    partial_bytes = (3*wg['rows'] + 2*wd['rows']) * 4
    if partial_bytes > c.partial_capacity_bytes:
        raise ValueError('partial-sum storage exceeds configured capacity')
    state = dict(gate=[0.0]*wg['rows'], up=[0.0]*wu['rows'], z=[],
                 projected=[0.0]*wd['rows'], output=None, counters={},
                 encoded={}, thresholds={}, operation_ids=[], tile_receipts=[],
                 local_state_bytes=dict(gate=wg['rows']*4,up=wu['rows']*4,z=wg['rows']*4,
                     down=wd['rows']*4,residual=wd['rows']*4),
                 provenance=dict(scope='one explicitly shaped FFN chain',
                    numeric='exact integer sample accumulation; FP32 tile restore/reduction; BF16 optional output',
                    random_source='frozen_replay' if fixture.get('thresholds') else 'Python Random local behavioral PRNG',
                    RNG_is_physical=False, timing='configured, uncharacterized',
                    weight_layout='offline tile-major packed signed W8; FP32 scale read/stored separately',
                    counter_layout=c.counter_layout,
                    counter_mapping='B bins x 2 sign rails x 8 magnitude planes x output rows' if c.counter_layout=='bitplane' else 'B signed integer sums per output row; alternate mapping with no inherited PPA',
                    tensor_storage='FP32 input/z/partial/residual; fixed W8 plus FP32 scale; BF16 output when configured',
                    storage_boundary='finite local weights/counters/encoded/partial state; backing SRAM/DRAM address space has no total-capacity allocator',
                    trace_storage='retained threshold histories and receipts are simulator evidence, not hardware buffers',
                    cdc=f'producer completion to destination acceptance: {c.cdc_cycles} destination edges; 3 models two synchronizers plus old-state consumer',
                    fixture=fixture.get('provenance', {})))
    ids = state['operation_ids']
    free_weights, free_counts,free_scales = prefix+'.weights', prefix+'.counters',prefix+'.scales'
    free_encoded, free_partials = prefix+'.encoded', prefix+'.partials'
    slots = [None]*c.weight_slots
    matrix_base = {'wg':0x10000000, 'wu':0x20000000, 'wd':0x30000000}
    partial_base = {'wg':0x50000000, 'wu':0x51000000, 'wd':0x52000000}
    values = {'wg':state['gate'], 'wu':state['up'], 'wd':state['projected']}
    last_partial = {}
    tile_serial = [0]
    pack = lambda values: struct.pack('<'+'f'*len(values), *values)
    unpack = lambda data: list(struct.unpack('<'+'f'*(len(data)//4), data))
    kernel.load_memory('sram', 0x40000000, pack(x))
    kernel.load_memory('sram', 0x42000000, pack(residual))
    weight_payload = {}
    for matrix_name,matrix in matrices.items():
        for r in range(0,matrix['rows'],64):
            for start in range(0,matrix['cols'],64):
                gi=start//64
                block_codes=[code for row in matrix['codes'][r:r+64] for code in row[start:start+64]]
                payload=struct.pack('<'+'b'*len(block_codes),*block_codes)
                scale_payload=pack([matrix['scales'][r//64][gi]])
                address=matrix_base[matrix_name]+(r//64*math.ceil(matrix['cols']/64)+gi)*4160
                weight_payload[matrix_name,r,gi]=(payload,scale_payload)
                kernel.load_memory('dram',address,payload)
                kernel.load_memory('dram',address+4096,scale_payload)

    def add(suffix, resource, **kwargs):
        ident = prefix+'.'+suffix
        kwargs.setdefault('cdc_cycles',c.cdc_cycles)
        kernel.add(Operation(ident, resource, **kwargs))
        ids.append(ident)
        return ident

    reserve = add('reserve_partials', 'control', inputs={free_partials:partial_bytes})

    def phase(name, vector, projections, dependency):
        phase_complete_id=prefix+'.'+name+'.complete'
        def build_group(gi, previous_group):
            start=gi*64
            block = vector[start:start+64]
            encoded_bytes = len(block)*3+4
            if encoded_bytes > c.encoded_capacity_bytes:
                raise ValueError('encoded group exceeds configured capacity')
            key = name, gi
            read = add(f'{name}.g{gi}.input_read', 'sram', deps=(previous_group,),
                       memory=MemoryRequest((0x40000000 if name=='x' else 0x41000000)+start*4, len(block)*4),
                       inputs={free_encoded:encoded_bytes})
            def encoded_cb(k, op, key=key, read=read, block=block):
                actual=unpack(k.memory_reads[read])
                if actual != block:
                    raise AssertionError('activation data changed between producer and encoder')
                state['encoded'][key] = encode_group(actual, c.bins)
                state['thresholds'][key] = threshold_words(c, name, key[1], fixture)
            encoded = add(f'{name}.g{gi}.encode', 'encode', deps=(read,),
                          actions={'activation_encode_values':len(block)}, on_complete=encoded_cb)
            group_done = []
            group_tiles=[(mn,rr) for mn in projections for rr in range(0,matrices[mn]['rows'],64)]
            local_tile_index=0
            for matrix_name in projections:
                matrix = matrices[matrix_name]
                for r in range(0, matrix['rows'], 64):
                    nr, nc = min(64,matrix['rows']-r), len(block)
                    ti = tile_serial[0]
                    tile_serial[0] += 1
                    slot = ti % c.weight_slots
                    label = f'{matrix_name}.r{r//64}.k{gi}'
                    wave=local_tile_index//c.weight_slots
                    first_in_wave=local_tile_index%c.weight_slots==0
                    wave_tiles=group_tiles[wave*c.weight_slots:(wave+1)*c.weight_slots]
                    wave_labels=[f'{mn}.r{rr//64}.k{gi}' for mn,rr in wave_tiles]
                    local_tile_index+=1
                    tile_key = matrix_name, r//64, gi
                    counter_factor=16 if c.counter_layout=='bitplane' else 1
                    count_bytes = math.ceil(nr*c.bins*counter_factor*c.counter_width/8)
                    weight_bytes = nr*nc
                    if count_bytes > c.counter_capacity_bytes or weight_bytes > c.weight_slot_bytes:
                        raise ValueError('tile exceeds finite local weight/counter capacity')
                    dep = [encoded]
                    if slots[slot]: dep.append(slots[slot])
                    address = matrix_base[matrix_name] + (r//64*math.ceil(matrix['cols']/64)+gi)*4160
                    local = 0x60000000+slot*c.weight_slot_bytes
                    payload,scale_payload=weight_payload[matrix_name,r,gi]
                    scale_local=0x61000000+slot*4
                    def loaded_cb(k,op,payload=payload):
                        if k.memory_reads[op.id] != payload:
                            raise AssertionError('DMA weight bytes disagree with frozen input')
                    load = add(label+'.weight_read', 'dram', deps=tuple(dep),
                        memory=MemoryRequest(address, weight_bytes), inputs={free_weights:weight_bytes},
                        actions={'weight_read_bytes':weight_bytes},
                        on_complete=loaded_cb,
                        metadata={'matrix':matrix_name,'row':r,'column':start,'rows':nr,'columns':nc})
                    def scale_loaded(k,op,expected=scale_payload):
                        if k.memory_reads[op.id]!=expected:
                            raise AssertionError('DMA weight scale bytes disagree with input')
                    scale_load=add(label+'.scale_read','dram',deps=tuple(dep),
                        memory=MemoryRequest(address+4096,4),inputs={free_scales:4},on_complete=scale_loaded,
                        actions={'weight_scale_read_bytes':4})
                    scale_fill=add(label+'.scale_fill','sram',deps=(scale_load,),
                        memory=MemoryRequest(scale_local,4,write=True,data=scale_payload),actions={'sram_write_bytes':4})
                    scale_read=add(label+'.scale_local_read','sram',deps=(scale_fill,),
                        memory=MemoryRequest(scale_local,4),actions={'sram_read_bytes':4})
                    fill = add(label+'.weight_fill', 'sram', deps=(load,),
                        memory=MemoryRequest(local,weight_bytes,write=True,data=payload), actions={'sram_write_bytes':weight_bytes})
                    readw = add(label+'.weight_local_read', 'sram', deps=(fill,),
                        memory=MemoryRequest(local,weight_bytes), actions={'sram_read_bytes':weight_bytes})
                    def init_count(k, op, tile_key=tile_key, nr=nr, nc=nc, readw=readw,payload=payload,
                                   scale_read=scale_read,scale_payload=scale_payload):
                        actual=k.memory_reads[readw]
                        if actual != payload:
                            raise AssertionError('array-side weight bytes disagree with DMA payload')
                        if k.memory_reads[scale_read]!=scale_payload:
                            raise AssertionError('local scale bytes disagree with DMA payload')
                        state['counters'][tile_key] = ([[[[0]*8 for _ in range(2)] for _ in range(c.bins)] for _ in range(nr)]
                                                     if c.counter_layout=='bitplane' else [[0]*c.bins for _ in range(nr)])
                        state.setdefault('resident_weights',{})[tile_key]=(
                            [list(struct.unpack('<'+'b'*nc,actual[row*nc:(row+1)*nc])) for row in range(nr)],
                            unpack(k.memory_reads[scale_read])[0])
                    previous = add(label+'.count_init','control',deps=(readw,scale_read),
                        inputs={free_counts:count_bytes},on_complete=init_count,
                        actions={'counter_initialize_bits':nr*c.bins*counter_factor*c.counter_width})
                    for step in range(c.samples):
                        rng_suffix=f'{name}.g{gi}.wave{wave}.rng{step}'
                        rng=prefix+'.'+rng_suffix
                        if first_in_wave:
                            rng_deps=tuple(prefix+'.'+wl+('.count_init' if step==0 else f'.sample{step-1}') for wl in wave_labels)
                            add(rng_suffix,'rng',deps=rng_deps,
                                actions={'random_word8':1,'shared64_broadcast_tiles':len(wave_tiles)},
                                metadata={'phase':name,'group':gi,'step':step,'wave':wave,'replay_same_group':wave>0})
                        def sample_cb(k, op, key=key, tile_key=tile_key, matrix=matrix,
                                      r=r, start=start, nr=nr, step=step):
                            enc = state['encoded'][key]
                            word = state['thresholds'][key][step]
                            acc = state['counters'][tile_key]
                            codes,_ = state['resident_weights'][tile_key]
                            for row in range(nr):
                                for col, item in enumerate(enc):
                                    if item['full_one'] or word < item['q']:
                                        code=codes[row][col]
                                        if c.counter_layout=='bitplane':
                                            rail=0 if item['sign']*code>=0 else 1
                                            for bit in range(8):
                                                acc[row][item['bin']][rail][bit]+=(abs(code)>>bit)&1
                                        else: acc[row][item['bin']]+=item['sign']*code
                                if c.counter_layout=='bitplane':
                                    if any(not 0<=v<1<<c.counter_width for b in acc[row] for rail in b for v in rail):
                                        raise OverflowError('unsigned bit-plane counter overflow')
                                elif any(not -(1<<(c.counter_width-1)) <= v < 1<<(c.counter_width-1) for v in acc[row]):
                                    raise OverflowError('signed bin counter overflow')
                        previous = add(label+f'.sample{step}', 'sc:'+str(slot%c.engines), deps=(rng,), on_complete=sample_cb,
                            actions={'sc_sample_frames':1,'weight_input_trials':nr*nc,
                                     'counter_clocked_slots':nr*c.bins*counter_factor},
                            metadata={'tile':label,'step':step,'samples':c.samples,'engine':slot%c.engines})
                    deps=[previous]
                    partial_key=matrix_name,r
                    readp=None
                    if partial_key in last_partial:
                        readp=add(label+'.partial_read','sram',deps=(last_partial[partial_key],),
                            memory=MemoryRequest(partial_base[matrix_name]+r*4,nr*4),actions={'partial_read_bytes':nr*4})
                        deps.append(readp)
                    writep=prefix+'.'+label+'.partial_write'
                    def restore_cb(k, op, key=key, tile_key=tile_key, matrix=matrix,
                                   matrix_name=matrix_name, r=r, gi=gi, nr=nr, label=label,readp=readp):
                        enc=state['encoded'][key]
                        scale_by_bin={item['bin']:item['scale'] for item in enc}
                        raw_counts=state['counters'].pop(tile_key)
                        if c.counter_layout=='bitplane':
                            counts=[[sum((planes[0][bit]-planes[1][bit])*(1<<bit) for bit in range(8))
                                     for planes in row] for row in raw_counts]
                            counter_peak=max(v for row in raw_counts for b in row for rail in b for v in rail)
                        else:
                            counts=raw_counts
                            counter_peak=max(abs(v) for row in counts for v in row)
                        _,weight_scale=state['resident_weights'].pop(tile_key)
                        old=unpack(k.memory_reads[readp]) if readp else [0.0]*nr
                        for row in range(nr):
                            total=0.0
                            for b in range(c.bins):
                                # Each bin restores before cross-bin/tile FP32 addition.
                                term=fp32(fp32(counts[row][b]*scale_by_bin.get(b,0.0))*weight_scale/c.samples)
                                total=fp32(total+term)
                            values[matrix_name][r+row]=fp32(old[row]+total)
                        add(label+'.partial_write','sram',deps=(op.id,),
                            memory=MemoryRequest(partial_base[matrix_name]+r*4,nr*4,write=True,
                                                 data=pack(values[matrix_name][r:r+nr])),
                            actions={'partial_write_bytes':nr*4})
                        state['tile_receipts'].append(dict(tile=label,counter_peak=counter_peak,
                                                          integer_equivalent_peak=max(abs(v) for row in counts for v in row),
                                                          counter_layout=c.counter_layout,
                                                          restored_rows=nr,complete_ps=k.now_ps))
                    restored=add(label+'.restore','restore',deps=tuple(deps),on_complete=restore_cb,
                        outputs={free_counts:count_bytes},actions={'complete_tile_restore':1,'cross_tile_fp32_add':nr})
                    release=add(label+'.weight_release','control',deps=(restored,),outputs={free_weights:weight_bytes,free_scales:4})
                    slots[slot]=release
                    last_partial[partial_key]=writep
                    group_done.extend([writep,release])
            def group_done_cb(k,op):
                state['encoded'].pop(key)
                if start+64<len(vector):
                    build_group(gi+1,op.id)
                else:
                    add(name+'.complete','control',deps=(op.id,))
            add(f'{name}.g{gi}.release','control',deps=tuple(group_done),outputs={free_encoded:encoded_bytes},
                on_complete=group_done_cb)
        build_group(0,dependency)
        return phase_complete_id

    x_done=phase('x',x,('wg','wu'),reserve)
    def nonlinear_cb(k, op):
        state['z']=[fp32(fp32(g*fp32(sigmoid(g)))*u) for g,u in zip(state['gate'],state['up'])]
        z_write=add('z.write','sram',deps=(op.id,),
                    memory=MemoryRequest(0x41000000,len(state['z'])*4,write=True,data=pack(state['z'])))
        z_done=phase('z',state['z'],('wd',),z_write)
        residual_read=add('residual.read','sram',deps=(z_done,),
            memory=MemoryRequest(0x42000000,len(residual)*4),actions={'residual_read_bytes':len(residual)*4})
        def output_cb(k2, op2):
            actual_residual=unpack(k2.memory_reads[residual_read])
            if actual_residual!=residual:
                raise AssertionError('residual input bytes changed')
            converted=[bf16(v) if c.output_bf16 else v for v in state['projected']]
            state['output']=[bf16(fp32(v+r)) if c.output_bf16 else fp32(v+r) for v,r in zip(converted,actual_residual)]
            payload=pack(state['output'])
            if c.output_bf16:
                payload=b''.join(payload[i+2:i+4] for i in range(0,len(payload),4))
            state['output_address']=0x53000000
            state['output_bytes']=len(payload)
            def stored(k3,op3): state['complete_ps']=k3.now_ps
            add('output.write','sram',deps=(op2.id,),
                memory=MemoryRequest(state['output_address'],len(payload),write=True,data=payload),
                outputs={free_partials:partial_bytes},on_complete=stored,actions={'output_write_bytes':len(payload)})
        add('residual','vector',deps=(residual_read,),on_complete=output_cb,
            actions={'residual_add':len(residual),'down_fp32_to_bf16':len(residual) if c.output_bf16 else 0,
                     'residual_fp32_to_bf16':len(residual) if c.output_bf16 else 0})
    add('swiglu','nonlinear',deps=(x_done,),latency_cycles=c.nonlinear_latency+math.ceil(wg['rows']/c.vector_lanes)-1,
        on_complete=nonlinear_cb,actions={'silu_values':wg['rows'],'gated_multiply':wg['rows']},
        metadata={'all_input_tiles_reduced':True})
    return state


def reference_ffn(fixture, config=None):
    """Independent count-compressed FP32 oracle, no event scheduler/counters."""
    c=config or FFNConfig()
    c.validate()
    mats={name:matrix_spec(fixture[name]) for name in ('wg','wu','wd')}
    def sampled(values,phase):
        result=[]
        for group,start in enumerate(range(0,len(values),64)):
            encoded=encode_group(values[start:start+64],c.bins)
            words=threshold_words(c,phase,group,fixture)
            result.extend(fp32(item['sign']*item['scale']*sum(item['full_one'] or w<item['q'] for w in words)/c.samples)
                          for item in encoded)
        return result
    def project(values,matrix):
        result=[]
        for r,row in enumerate(matrix['codes']):
            result.append(fp32(math.fsum(float(v)*code*matrix['scales'][r//64][j//64]
                                         for j,(v,code) in enumerate(zip(values,row)))))
        return result
    sx=sampled(fixture['x'],'x')
    gate,up=project(sx,mats['wg']),project(sx,mats['wu'])
    z=[fp32(fp32(g*fp32(sigmoid(g)))*u) for g,u in zip(gate,up)]
    projected=project(sampled(z,'z'),mats['wd'])
    residual=fixture.get('residual',[0.0]*len(projected))
    out=[bf16(fp32(bf16(v)+r)) if c.output_bf16 else fp32(v+r) for v,r in zip(projected,residual)]
    return dict(gate=gate,up=up,z=z,projected=projected,output=out)


def reference_ffn_tiled(fixture,config=None):
    """Bit-equal count-compressed oracle at the declared rounding boundaries.

    The execution path updates signed bin sums once per temporal sample. This
    oracle first counts each lane's complete stream and contracts counts with
    integer weights, independently checking the time/space interchange before
    applying the same explicitly specified FP32 restoration and tile order.
    """
    c=config or FFNConfig()
    c.validate()
    matrices={name:matrix_spec(fixture[name]) for name in ('wg','wu','wd')}
    def project_phase(vector,names,phase):
        groups=[]
        for group,start in enumerate(range(0,len(vector),64)):
            encoded=encode_group(vector[start:start+64],c.bins)
            words=threshold_words(c,phase,group,fixture)
            groups.append((encoded,[sum(item['full_one'] or word<item['q'] for word in words)
                                    for item in encoded]))
        outputs={}
        for name in names:
            matrix=matrices[name]
            result=[]
            for row,codes in enumerate(matrix['codes']):
                total=0.0
                for group,(encoded,counts) in enumerate(groups):
                    partial=0.0
                    for b in range(c.bins):
                        members=[i for i,item in enumerate(encoded) if item['bin']==b]
                        integer=sum(counts[i]*encoded[i]['sign']*codes[group*64+i] for i in members)
                        scale=encoded[members[0]]['scale'] if members else 0.0
                        restored=fp32(fp32(integer*scale)*matrix['scales'][row//64][group]/c.samples)
                        partial=fp32(partial+restored)
                    total=fp32(total+partial)
                result.append(total)
            outputs[name]=result
        return outputs
    gu=project_phase(fixture['x'],('wg','wu'),'x')
    gate,up=gu['wg'],gu['wu']
    z=[fp32(fp32(g*fp32(sigmoid(g)))*u) for g,u in zip(gate,up)]
    projected=project_phase(z,('wd',),'z')['wd']
    residual=[fp32(v) for v in fixture.get('residual',[0.0]*len(projected))]
    output=[bf16(fp32(bf16(v)+r)) if c.output_bf16 else fp32(v+r) for v,r in zip(projected,residual)]
    return dict(gate=gate,up=up,z=z,projected=projected,output=output)
