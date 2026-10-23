"""Per-group/per-output integration with the Issue116 Resource/Operation API.

This is a composable conditional scheduling adapter, not a replacement kernel.
All numeric results are raw FP32 words; every restore includes all four bins.
Credits reserve a result slot at acceptance and hold it through downstream
cross-k addition. This is intentionally conservative relative to a raw FIFO
which can return credit at dequeue. It is not a cycle-identical RTL wrapper.
No frequency, energy or silicon area is inferred from these cycle parameters.
"""
from dataclasses import dataclass
from .arithmetic import encode, normalize_counts, restore_bins, add_words


def positive(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name + ' must be a positive integer')


@dataclass(frozen=True)
class Profile:
    period_ps: int = 10000
    encode_latency: int = 2
    encode_ii: int = 1
    encode_depth: int = 4
    restore_latency: int = 2
    restore_ii: int = 1
    restore_lanes: int = 1
    restore_depth: int = 4
    add_latency: int = 1
    add_ii: int = 1
    add_capacity: int = 2
    encoded_groups: int = 1

    def __post_init__(self):
        for name, value in vars(self).items():
            positive(value, name)
        if self.encoded_groups != 1:
            raise ValueError('this first adapter serializes group lifetime; encoded_groups must be 1')

    def specs(self, api, prefix='er'):
        C, Resource, Buffer = api.Clock, api.Resource, api.Buffer
        clock = C(prefix+'.clock', self.period_ps)
        provenance = 'conditional adapter; functional RTL edges do not establish STA'
        resources = [Resource(prefix+'.encode', clock, self.encode_latency,
                              ii_cycles=self.encode_ii, capacity=self.encode_depth,
                              provenance=provenance),
                     Resource(prefix+'.add', clock, self.add_latency,
                              ii_cycles=self.add_ii, capacity=self.add_capacity,
                              provenance=provenance),
                     Resource(prefix+'.release', clock, 1, capacity=2, provenance=provenance)]
        buffers = [Buffer(prefix+'.encoded_free', self.encoded_groups,
                          self.encoded_groups, unit='complete encoded 64-value group')]
        for lane in range(self.restore_lanes):
            name = f'{prefix}.restore{lane}'
            resources.append(Resource(name, clock, self.restore_latency,
                                      ii_cycles=self.restore_ii, capacity=self.restore_depth,
                                      provenance=provenance))
            buffers += [Buffer(name+'.free', self.restore_depth, self.restore_depth,
                               unit='reserved complete output slot, includes in-flight and waiting add'),
                        Buffer(name+'.ready', self.restore_depth, unit='FP32 complete output')]
        return resources, buffers


class Adapter:
    """Append to a caller-owned Kernel; the caller provides counter producers.

    Counter providers run at restore completion after explicit producer deps.
    A producer must preserve its counted state until every row's restore ends.
    Input groups are finite; encode credit is returned only after all row adds.
    Prefixes permit multiple independent clients in one caller-owned kernel.
    """
    def __init__(self, kernel, api, profile=Profile(), prefix='er'):
        self.kernel, self.api, self.profile, self.prefix = kernel, api, profile, prefix
        self.encoded, self.restored, self.partial, self.receipts = {}, {}, {}, []
        self.last_lane_add = {}
        self.last_group_release = None
        self.pending_group = None
        self.groups = set()

    def add_encode(self, group, words, *, frac=23, deps=()):
        ident = f'{self.prefix}.{group}.encode'
        if not isinstance(group, str) or not group or group in self.groups:
            raise ValueError('nonempty unique group identifier required')
        if self.pending_group is not None:
            raise ValueError('attach the pending group restore before encoding another group')
        # Validate and freeze now; hardware invalid-word handling is separate.
        words = tuple(words)
        expected = encode(words, frac=frac)
        self.groups.add(group)
        self.pending_group = group
        if self.last_group_release is not None:
            deps = tuple(dict.fromkeys((*deps,self.last_group_release)))
        def complete(k, op):
            self.encoded[group] = expected
        self.kernel.add(self.api.Operation(ident, self.prefix+'.encode', deps=tuple(deps),
            inputs={self.prefix+'.encoded_free':1},
            actions={'complete_encode_group64':1, 'encoded_values':64},
            metadata={'numeric_format':'BF16' if frac == 7 else 'FP32',
                      'unit':'one B4 group, no 447-op multiplier'}, on_complete=complete))
        return ident

    def add_restore_tile(self, group, *, rows, counter_provider, representation,
                         count_width, samples, weight_scale_word, deps=(),
                         previous_adds=(), sink_start_ps=0):
        """Schedule rows separate full restores and separate cross-k FP32 adds.

        previous_adds preserves the caller's cross-k ordering for each row.
        All lanes restore four bins with the original FUSED=0 rounding order.
        Direct attachment of product-sign counters to the original RTL is NOT
        implied: these callbacks normalize to the signed-bin software boundary.
        """
        if type(rows) is not int or not 1 <= rows <= 64:
            raise ValueError('tile must have 1..64 output rows')
        if previous_adds and len(previous_adds) != rows:
            raise ValueError('one previous add dependency per output required')
        if type(sink_start_ps) is not int or sink_start_ps < 0:
            raise ValueError('nonnegative sink start required')
        if representation not in ('input_sign_twos_complement', 'product_sign_magnitude'):
            raise ValueError('explicit known counter representation required')
        if self.pending_group != group:
            raise ValueError('restore must attach exactly once to the pending encoded group')
        adds = []
        for row in range(rows):
            lane = row % self.profile.restore_lanes
            resource = f'{self.prefix}.restore{lane}'
            restore_id = f'{self.prefix}.{group}.row{row:03d}.restore'
            add_id = f'{self.prefix}.{group}.row{row:03d}.add'
            def restore(k, op, row=row, ident=restore_id):
                enc = self.encoded[group]
                bins = normalize_counts(counter_provider(row), representation=representation,
                                        count_width=count_width, samples=samples)
                word = restore_bins(bins, top_exp=enc['top_exp'],
                                    weight_scale_word=weight_scale_word, samples=samples)
                self.restored[ident] = word
                self.receipts.append(dict(operation=ident, row=row, signed_bins=list(bins),
                                          fp32_word=word, completed_ps=k.now_ps))
            self.kernel.add(self.api.Operation(restore_id, resource,
                deps=tuple(dict.fromkeys((f'{self.prefix}.{group}.encode', *deps))),
                inputs={resource+'.free':1}, outputs={resource+'.ready':1},
                actions={'complete_restore_output_b4':1},
                metadata={'counter_representation':representation,
                          'conversion':'software signed-bin boundary', 'fused':False},
                on_complete=restore))
            def accumulate(k, op, row=row, ident=restore_id):
                self.partial[row] = add_words(self.partial.get(row, 0), self.restored.pop(ident))
            dependencies = (restore_id,) + ((previous_adds[row],) if previous_adds else ())
            # FIFO tokens have identity. Preserve consumption order even when
            # the caller stalls an earlier row on a cross-k dependency. This
            # conservative model waits for the previous add's completion.
            if lane in self.last_lane_add:
                dependencies += (self.last_lane_add[lane],)
            dependencies = tuple(dict.fromkeys(dependencies))
            self.kernel.add(self.api.Operation(add_id, self.prefix+'.add', deps=dependencies,
                inputs={resource+'.ready':1}, outputs={resource+'.free':1},
                actions={'cross_k_fp32_add':1}, earliest_ps=sink_start_ps, on_complete=accumulate))
            self.last_lane_add[lane] = add_id
            adds.append(add_id)
        release_id = f'{self.prefix}.{group}.release'
        def release(k, op):
            self.encoded.pop(group)
        self.kernel.add(self.api.Operation(release_id, self.prefix+'.release', deps=tuple(adds),
            outputs={self.prefix+'.encoded_free':1}, on_complete=release))
        self.last_group_release = release_id
        self.pending_group = None
        return tuple(adds), release_id
