"""Empty-reference corrected rejection; every failed proposal is charged."""
import math
from parallel_sampler_v5 import ParallelSampler, IdealBitSource, SamplingCapError, input_sha


class CorrectedRejectionSampler(ParallelSampler):
    kind = 'corrected_rejection'

    def __init__(self, cfg=None, capacity=512):
        super().__init__(cfg,capacity)
        if self.cfg['burn_updates'] or self.cfg['winner_shift']:
            raise ValueError('rejection uses adaptive m, no chain burn or winner_shift')

    def request(self, ready, logits, samples, rng, identity, candidate_ids,
                output_ns_per_index=0., source=None):
        s = self.begin(ready,logits,samples,identity,candidate_ids,output_ns_per_index)
        source = source or IdealBitSource(rng)
        s.module.provenance['source_driver_kind'] = source.kind
        nonref = [i for i in range(s.n) if i != s.ref]
        m = 0
        for phase in range(samples*s.c['max_proposals_per_sample']):
            drives = [s.encode(logits[i]-logits[s.ref]-m*math.log(2.)) for i in nonref]
            bits = s.draw(source,drives)
            active = [i for i,b in zip(nonref,bits) if b]
            reduction_levels=(max(1,len(nonref))-1).bit_length()
            s.stage('zero_single_multi_tree', math.ceil(reduction_levels/s.c['tree_levels_per_cycle']),
                    'rejection_flag_nodes', max(0,len(nonref)-1))
            s.stage('proposal_decision',s.c['decision_cycles'],'control_ops',1)
            old_m = m
            address = None
            if len(active) == 1:
                address = active[0]
                s.actions['accepted_single'] += 1
            elif not active:
                # Exactly 2^-m with m independent fair bits. m=0 accepts freely.
                if s.fair(source,m) == 0:
                    address = s.ref
                    s.actions['accepted_empty_reference'] += 1
                else:
                    m = max(0,m-1)
                    s.actions['rejected_empty'] += 1
            else:
                m = min(s.c['max_shift'],m+1)
                s.actions['rejected_multi'] += 1
            if m != old_m:
                s.stage('offset_feedback',s.c['offset_feedback_cycles'],'control_ops',1)
                lanes=len(nonref) if s.c['offset_update_mode']=='per_candidate' else 1
                s.stage('offset_reencode',2*math.ceil(lanes/s.c['score_lanes']),
                        'score_ops',2*lanes)
                bits_to_update = s.c['drive_bits']*(len(nonref) if s.c['offset_update_mode']=='per_candidate' else 1)
                s.program(bits_to_update,'offset_drive_update')
                s.actions['offset_changes'] += 1
            if s.c['record_events']:
                s.frames.append(dict(proposal=phase,active_count=len(active),shift=old_m,
                                     next_shift=m,accepted=address is not None,local_index=address))
            if address is not None:
                s.emit(address)
                if len(s.outputs) == samples:
                    receipt = s.close()
                    receipt.update(input_sha256=input_sha(logits,candidate_ids),
                                   initialization='m=0, max-score empty reference', final_shift=m,
                                   target='softmax only for independent ideal unquantized sigmoid + exact empty correction',
                                   no_extra_pv_sampler=True)
                    return list(s.outputs),receipt
        raise SamplingCapError('proposal cap; no IID fallback or partial trajectory',s.close(False))
