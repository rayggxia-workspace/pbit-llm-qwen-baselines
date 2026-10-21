"""Unpadded cached MC loglikelihood with actual decode-only Attention.

The caller supplies official Harness-tokenized documents, not labels.  All
choices of a document must have one common context.  The final context token
is always decoded separately and its logits are shared by every choice.  Every
later answer target traverses all 32 layers with q_len=1.  Branches restore KV,
FFN generators, selector/sampler generators and screening summaries together;
diagnostic counters remain cumulative.  No upstream numerical kernel changes.
"""
import copy
import hashlib
import json
import math
import time
from collections import defaultdict
from types import MethodType

import torch
from torch.nn import functional as F

from experiments.llama2_task_accuracy_20261020.adapter import (
    ExecutionAudit, ModelGuard, _case, _install_ffn)
from experiments.llama2_task_accuracy_20261020.adapter import (
    JointAttentionController)


def _validated_documents(documents, max_length):
    if type(max_length) is not int or max_length < 3:
        raise ValueError('max_length must be an integer >=3')
    result, seen = [], set()
    for index, raw in enumerate(documents):
        if not isinstance(raw, dict) or not isinstance(raw.get('id'), str) or not raw['id']:
            raise ValueError('each document requires a nonempty stable string id')
        if raw['id'] in seen:
            raise ValueError('document ids must be unique')
        seen.add(raw['id'])
        context, choices = raw.get('context_ids'), raw.get('choices_ids')
        if not isinstance(context, (tuple, list)) or len(context) < 3:
            raise ValueError('contexts require >=3 tokens; short contexts need a separate protocol')
        if not isinstance(choices, (tuple, list)) or len(choices) < 2:
            raise ValueError('each document requires at least two nonempty tokenized choices')
        for values in [context, *choices]:
            if not isinstance(values, (tuple, list)) or not values or any(
                    type(value) is not int or value < 0 for value in values):
                raise ValueError('context and each choice must be nonempty nonnegative integer token ids')
        if len(context) + max(map(len, choices)) - 1 > max_length:
            raise ValueError('context+choice input exceeds max_length; truncate explicitly in the request manifest')
        result.append(dict(id=raw['id'], task=str(raw.get('task', '')), index=index,
                           context_ids=list(context), choices_ids=[list(x) for x in choices]))
    if not result:
        raise ValueError('at least one document required')
    return result


def document_batches(documents, batch):
    """Stable length grouping without padding or label/score-dependent choices."""
    if type(batch) is not int or not 1 <= batch <= 16:
        raise ValueError('batch must be an integer in 1..16')
    grouped = defaultdict(list)
    for row in documents:
        grouped[(len(row['context_ids']), len(row['choices_ids']))].append(row)
    for signature in sorted(grouped):
        group = grouped[signature]
        for start in range(0, len(group), batch):
            yield group[start:start + batch]


def batch_seed(rows, seed):
    """Exclude S, choices, labels and runtime order from the common-prefix seed."""
    if type(seed) is not int or seed < 0:
        raise ValueError('seed must be a nonnegative integer')
    payload = json.dumps([seed, [(r['task'], r['id']) for r in rows]],
                         ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], 'little') % (2**31 - 1)


def _seed_streams(layers, controller, seed):
    for index, layer in enumerate(layers):
        for role, offset in (('rng_input', 700001), ('rng_product', 700002)):
            generator = getattr(layer.mlp, role, None)
            if generator is not None:
                generator.manual_seed(offset + seed * 1000 + index * 7)
    if controller is not None:
        controller.seed = seed
        controller._rng.clear()
        for state in controller._state.values():
            state['summary'] = None


def _snapshot_branch(cache, layers, controller):
    return dict(cache=copy.deepcopy(cache),
        ffn_rng={(i, role): getattr(layer.mlp, role).get_state().clone()
                 for i, layer in enumerate(layers) for role in ('rng_input', 'rng_product')
                 if getattr(layer.mlp, role, None) is not None},
        attention_rng=({key: generator.get_state().clone()
                        for key, generator in controller._rng.items()} if controller else {}),
        summaries=({key: copy.deepcopy(value['summary'])
                    for key, value in controller._state.items()} if controller else {}))


def _restore_branch(snapshot, layers, controller):
    for (index, role), state in snapshot['ffn_rng'].items():
        getattr(layers[index].mlp, role).set_state(state)
    if controller is not None:
        for key in list(controller._rng):
            if key not in snapshot['attention_rng']:
                del controller._rng[key]
        for key, state in snapshot['attention_rng'].items():
            if key not in controller._rng:
                controller._rng[key] = torch.Generator(device=key[1])
            controller._rng[key].set_state(state)
        for key, value in snapshot['summaries'].items():
            controller._state[key]['summary'] = copy.deepcopy(value)
    # Restoring always clones the saved base.  In-place DynamicCache updates or
    # mutable legacy tuples must never alter the next choice's branch point.
    return copy.deepcopy(snapshot['cache'])


class ActiveSamplingProbe:
    """Count real non-dummy query rows without changing upstream arithmetic.

    Shared first-token queries count once, although their logits score several
    choices.  Upstream aggregate counters additionally include harmless dummy
    rows needed to keep batch shape/RNG consumption fixed during a branch.
    """
    def __init__(self, controller):
        self.controller, self.mask = controller, None
        self.totals = dict(query_token_rows=0., query_head_rows=0.,
                           possible_candidates=0., selected_candidates=0.,
                           GQA_possible_candidates=0., GQA_union_candidates=0.)
        self._values = None
        self._original = controller._record_core
        probe = self

        def record(owner, a, q, length, chosen, raw, counts, width, sampled, adjacent):
            probe._original(a, q, length, chosen, raw, counts, width, sampled, adjacent)
            if probe.mask is None or probe.mask.shape != (q.shape[0],):
                raise RuntimeError('active query mask missing or inconsistent')
            batch, heads = q.shape[:2]
            mask = probe.mask.to(device=q.device)
            valid = mask.to(torch.float64).sum()
            selections = counts.reshape(batch, heads)[mask].sum()
            union = chosen.reshape(batch, a.num_key_value_heads,
                                   a.num_key_value_groups, -1).any(2)[mask]
            sizes = (length - torch.arange(chosen.shape[-1], device=q.device) * 64).clamp(1, 64)
            values = torch.stack([valid, valid * heads, valid * heads * length,
                selections, valid * a.num_key_value_heads * length, (union * sizes).sum()])
            probe._values = values if probe._values is None else probe._values + values
        controller._record_core = MethodType(record, controller)

    def result(self):
        if self._values is not None:
            self.totals = dict(zip(self.totals, self._values.tolist()))
        result = dict(self.totals)
        result['selected_fraction'] = result['selected_candidates'] / max(result['possible_candidates'], 1.)
        result['GQA_union_fraction'] = result['GQA_union_candidates'] / max(result['GQA_possible_candidates'], 1.)
        return result

    def close(self):
        self.controller._record_core = self._original


def evaluate_tasks(model, documents, case, calibration=None, progress=None):
    """Consume one fresh model and return official-request choice logprobs.

    Input documents: ``{'id': str, 'task': str, 'context_ids': list[int],
    'choices_ids': list[list[int]]}``.  Labels are neither needed nor inspected.
    Caller runs official ``task.process_results(doc, [(logprob,is_greedy),...])``.
    ``progress(dict)`` receives each completed batch plus cumulative elapsed and
    execution counts.  It must not call/alter this model or its generators.

    Models use original LlamaMLP objects on entry.  Installing Attention first,
    then FFN, preserves all Issue50 runtime preconditions and arithmetic.
    """
    case = _case(dict(batch=16, **case)) if 'batch' not in case else _case(case)
    rows = _validated_documents(documents, case['context'])
    list(document_batches([], case['batch']))  # Validate even before model mutation.
    layers = list(model.model.layers)
    if len(layers) != 32 or model.training or any(type(x.mlp).__name__ != 'LlamaMLP' for x in layers):
        raise ValueError('fresh 32-layer eval model with original LlamaMLP required')
    device = next(model.parameters()).device
    if device.type == 'cuda':
        torch.backends.cuda.matmul.allow_tf32 = False
    vocab = getattr(model.config, 'vocab_size', None)
    if vocab is not None and any(value >= vocab for row in rows for sequence in
            [row['context_ids'], *row['choices_ids']] for value in sequence):
        raise ValueError('input token id outside model vocabulary')
    controller = audit = guard = probe = None
    started = time.perf_counter()
    outputs = [None] * len(rows)
    stats = dict(shared_first_query_rows=0, branch_query_rows=0,
                 dummy_query_rows=0, scored_choice_tokens=0, batches=0,
                 first_token_logit_reuses=0, completed_documents=0)
    batch_records = []

    def sync():
        if device.type == 'cuda':
            torch.cuda.synchronize(device)

    def forward(tokens, cache, phase, active=None):
        if probe is not None:
            probe.mask = active
        audit.begin(phase)
        out = model.model(input_ids=tokens, past_key_values=cache, use_cache=True)
        audit.end(tokens.shape[0])
        return out

    def audit_summary():
        return dict(stats, actual_decode_calls=audit.decode_steps,
            actual_decode_query_rows=audit.query_targets,
            actual_prefill_calls=audit.prefill_steps,
            attention_decode_calls_per_layer=list(audit.decode_by_layer),
            ffn_decode_calls_per_layer=list(audit.ffn_decode_by_layer))

    try:
        if case['mode'].startswith('screen') and calibration is None:
            raise ValueError('screening requires the fixed train-derived calibration')
        if case['mode'] != 'sdpa':
            controller = JointAttentionController(**{key: case[key] for key in
                ('mode', 'samples', 'burn', 'spacing', 'seed', 'budget_blocks', 'selection', 'target_fraction')},
                calibration=calibration)
            controller.install(model)
            probe = ActiveSamplingProbe(controller)
        _install_ffn(model, case)
        guard, audit = ModelGuard(model, case['ffn']), ExecutionAudit(layers)
        with torch.inference_mode():
            for batch_number, batch_rows in enumerate(document_batches(rows, case['batch'])):
                number, length = len(batch_rows), len(batch_rows[0]['context_ids'])
                current_seed = batch_seed(batch_rows, case['seed'])
                _seed_streams(layers, controller, current_seed)
                contexts = torch.tensor([r['context_ids'] for r in batch_rows], device=device, dtype=torch.long)
                active_all = torch.ones(number, device=device, dtype=torch.bool)
                prefill = forward(contexts[:, :-1], None, 'prefill')
                cache = prefill.past_key_values
                del prefill
                # This q_len=1 call predicts EVERY choice's first target.  It is
                # never substituted by logits from the multi-token prefill.
                first = forward(contexts[:, -1:], cache, 'decode', active_all)
                shared_logits = model.lm_head(first.last_hidden_state[:, -1]).float()
                shared_logprobs = F.log_softmax(shared_logits, dim=-1)
                shared_argmax = shared_logits.argmax(-1)
                snapshot = _snapshot_branch(first.past_key_values, layers, controller)
                del first, shared_logits, cache
                stats['shared_first_query_rows'] += number
                max_choices = max(len(r['choices_ids']) for r in batch_rows)
                # Pair branches in a label-free canonical order.  CTMC event
                # coverage can append blocks according to the slowest row;
                # keeping branch composition canonical prevents arbitrary
                # within-document option permutations from changing that
                # cross-row RNG consumption. Return original request order.
                orders = [sorted(range(len(r['choices_ids'])),
                                 key=lambda i, r=r: tuple(r['choices_ids'][i]))
                          for r in batch_rows]
                per_row = [[None] * len(r['choices_ids']) for r in batch_rows]
                for choice in range(max_choices):
                    answers = [r['choices_ids'][order[choice]] if choice < len(order) else []
                               for r, order in zip(batch_rows, orders)]
                    lengths = torch.tensor([len(a) for a in answers], device=device)
                    target = torch.tensor([a[0] if a else 0 for a in answers], device=device)
                    ll = shared_logprobs.gather(-1, target[:, None]).squeeze(-1).double()
                    greedy = shared_argmax == target
                    branch = _restore_branch(snapshot, layers, controller)
                    for position in range(1, max(map(len, answers))):
                        active = lengths > position
                        tokens = torch.tensor([[a[position - 1] if position - 1 < len(a) else 0]
                                               for a in answers], device=device, dtype=torch.long)
                        output = forward(tokens, branch, 'decode', active)
                        branch = output.past_key_values
                        logits = model.lm_head(output.last_hidden_state[:, -1]).float()
                        target = torch.tensor([a[position] if position < len(a) else 0
                                               for a in answers], device=device)
                        values = F.log_softmax(logits, dim=-1).gather(-1, target[:, None]).squeeze(-1)
                        ll += torch.where(active, values.double(), 0.)
                        greedy &= (~active) | (logits.argmax(-1) == target)
                        active_count = sum(position < len(a) for a in answers)
                        stats['branch_query_rows'] += active_count
                        stats['dummy_query_rows'] += number - active_count
                        del output, logits, tokens, values
                    for i, (answer, value, exact) in enumerate(zip(answers, ll.tolist(), greedy.tolist())):
                        if answer:
                            if not math.isfinite(value) or value > 1e-5:
                                raise RuntimeError('invalid choice logprob')
                            per_row[i][orders[i][choice]] = dict(logprob=value, is_greedy=bool(exact), tokens=len(answer))
                            stats['scored_choice_tokens'] += len(answer)
                    del branch, ll, greedy, target
                batch_output = []
                for row, choices in zip(batch_rows, per_row):
                    if len(choices) != len(row['choices_ids']) or any(c is None for c in choices):
                        raise RuntimeError('choice/result count mismatch')
                    result = dict(id=row['id'], task=row['task'], context_tokens=length,
                                  choices=choices)
                    outputs[row['index']] = result
                    batch_output.append(result)
                    stats['first_token_logit_reuses'] += len(choices) - 1
                stats['batches'] += 1
                stats['completed_documents'] += number
                sync()
                batch_records.append(dict(batch=batch_number, document_ids=[r['id'] for r in batch_rows],
                    context_tokens=length, seed=current_seed, rows=number,
                    choice_tokens=sum(len(c) for r in batch_rows for c in r['choices_ids'])))
                if progress is not None:
                    progress(dict(documents=batch_output, batch=batch_number,
                        elapsed_seconds=time.perf_counter() - started, execution_audit=audit_summary()))
                del contexts, snapshot, shared_logprobs, shared_argmax
        if audit.query_targets != stats['shared_first_query_rows'] + stats['branch_query_rows'] + stats['dummy_query_rows']:
            raise RuntimeError('actual query row accounting mismatch')
        expected = sum(len(c) for r in rows for c in r['choices_ids'])
        if stats['scored_choice_tokens'] != expected or any(x is None for x in outputs):
            raise RuntimeError('not all requested choice tokens scored')
        sampling = controller.stats() if controller else None
        active_sampling = probe.result() if probe else None
        if sampling:
            for index in range(32):
                layer = sampling['layers'][str(index)]
                if layer['decode_calls'] != audit.decode_steps or layer['prefill_calls'] != audit.prefill_steps:
                    raise RuntimeError('controller call counts differ from independent audit')
            if sampling['totals']['query_token_rows'] != audit.query_targets * 32:
                raise RuntimeError('sampling query row audit mismatch')
            if active_sampling['query_token_rows'] != (stats['shared_first_query_rows'] + stats['branch_query_rows']) * 32:
                raise RuntimeError('non-dummy sampling query row audit mismatch')
            sampling['scope'] = ('all 32 single-token MC scoring decode layers, shared first query once; '
                'includes unscored dummy batch rows; multi-token prefix attention is original SDPA; FFN follows case')
            sampling['seed'] = case['seed']
            sampling['seed_scope'] = 'case seed selects deterministic per-batch seeds recorded in batches'
        ffn_stats = ({str(i): layer.mlp.diagnostics() for i, layer in enumerate(layers)}
                     if case['ffn'] != 'none' else None)
        if case['ffn'] != 'none' and any(layer.mlp.calls != audit.decode_steps + audit.prefill_steps for layer in layers):
            raise RuntimeError('FFN sampler call counts differ from independent audit')
        summary = audit_summary()
        summary.update(attention_prefill_calls_per_layer=list(audit.prefill_by_layer),
            ffn_prefill_calls_per_layer=list(audit.ffn_prefill_by_layer),
            every_scored_target_used_32_decode_layers=True,
            shared_first_query_counted_once_for_actual_execution=True,
            original_tokenized_requests=expected)
    finally:
        if audit:
            audit.close()
        if probe:
            probe.close()
        if controller:
            controller.close()
        if guard:
            guard.verify()
    return dict(test='cached_mc_joint_stratified_ffn_attention', documents=outputs,
        case=copy.deepcopy(case), batches=batch_records, execution_audit=summary,
        sampling_stats=sampling, active_sampling_stats=active_sampling, ffn_stats=ffn_stats,
        elapsed_seconds=time.perf_counter() - started, training=False,
        protocol=dict(score='teacher-forced sum of FP32 per-token log-softmax in FP64',
            first_target='last context token is a scored q_len=1 query; its logits shared across choices',
            branch='deep-copy KV cache + restore FFN/selector/Ising RNG and per-layer screening summaries',
            choice_order='score label-free lexicographic token-id order per document; map results to original request order',
            prefill_attention='original multi-token SDPA', ffn='all prefill and decode tokens follow case',
            batching='exact context-length grouping; no padding or attention_mask; batch <=16',
            dummy='legal token 0 only for finished/missing choice rows; excluded from scientific scores and active sampling metrics',
            rng='per-batch SHA256(task/doc ids/global seed), excluding S and choice; complete branch state restore',
            integration='official fixed-version Harness tokenization and task.process_results are caller responsibilities',
            accuracy='no label inspection, choice score ensemble or majority voting inside scorer'),
        limitations=['different batch composition is a different random-stream protocol',
            'short task prompts can retain all K blocks; active sampling metrics disclose actual pruning',
            'finite ideal hard-onehot CTMC is not physical Ising hardware execution',
            'natural hardware runs need not share branch noise; this paired protocol controls evaluation variance',
            'context>=3 and explicitly bounded total inputs required; no implicit request truncation'])
