"""Full-candidate parallel winner-hold sampler with explicit digital arbitration."""
import math
from parallel_sampler_v5 import ParallelSampler, IdealBitSource, SamplingCapError, input_sha


class WinnerHoldSampler(ParallelSampler):
    kind = 'winner_hold'

    def request(self, ready, logits, samples, rng, identity, candidate_ids,
                output_ns_per_index=0., source=None):
        s = self.begin(ready, logits, samples, identity, candidate_ids, output_ns_per_index)
        source = source or IdealBitSource(rng)
        s.module.provenance['source_driver_kind'] = source.kind
        drives = [s.encode(z-logits[s.ref]-s.c['winner_shift']) for z in logits]
        winner = s.ref
        rounds = samples+s.c['burn_updates']
        for step in range(rounds):
            bits = s.draw(source, drives)
            active = [i for i,b in enumerate(bits) if b]
            s.stage('active_count_tree', math.ceil(s.levels/s.c['tree_levels_per_cycle']),
                    'winner_count_nodes', max(0, s.n-1))
            previous = winner
            s.stage('winner_bit_test', s.c['decision_cycles'], 'control_ops', 1)
            if active and not bits[winner]:
                width = (len(active)-1).bit_length()
                rank = 0
                for _ in range(s.c['rank_retry_cap']):
                    rank = s.fair(source, width)
                    if rank < len(active):
                        break
                    s.actions['rank_retries'] += 1
                else:
                    raise SamplingCapError('uniform-rank cap; no biased fallback', s.close(False))
                s.stage('uniform_rank_tree', math.ceil(s.levels/s.c['tree_levels_per_cycle']),
                        'rank_node_visits', s.levels)
                winner = active[rank]
            s.actions['winner_switches' if winner != previous else 'winner_holds'] += 1
            s.actions['algorithm_updates'] += 1
            if s.c['record_events']:
                s.frames.append(dict(round=step, active_count=len(active), previous=previous,
                                     winner=winner, retained=step >= s.c['burn_updates']))
            if step >= s.c['burn_updates']:
                s.emit(winner)
            else:
                s.stage('burn_commit', s.c['commit_cycles'], 'control_ops', 1)
        receipt = s.close()
        receipt.update(input_sha256=input_sha(logits,candidate_ids),
                       initialization='argmax', burn_updates=s.c['burn_updates'],
                       target='odds(sigmoid(encoded(z-max-shift))); softmax only with ideal unquantized drive',
                       no_extra_pv_sampler=True)
        return list(s.outputs), receipt
