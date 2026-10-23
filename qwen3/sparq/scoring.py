"""Paired cached PPL and official multiple-choice likelihood scoring.

No checkpoint, dataset, or result is loaded/written on import. The caller owns
provenance and artifacts. A fresh model is required for an optional FFN case.
"""
import copy
import hashlib
import math
import struct
import time
from contextlib import nullcontext
from pathlib import Path

import torch
from torch.nn import functional as F

from ..stochastic.vendor.scoring import (full_window_plan, suffix_plan,
    plan_batches, plan_metadata, ids_sha256, summarize_records, target_positions)
from .adapter import SparQController


def _identity(tensor):
    return (id(tensor), tensor.data_ptr(), tuple(tensor.shape), str(tensor.dtype),
            str(tensor.device), tensor._version)


class ExecutionAudit:
    """Independent hooks verify attention and FFN order on every model call."""
    def __init__(self, layers):
        self.count = len(layers)
        self.phase, self.handles, self.calls = None, [], {'prefill': 0, 'decode': 0}
        self.tokens = {phase: {kind: [0] * self.count for kind in ('attention', 'ffn')}
                       for phase in self.calls}
        for index, layer in enumerate(layers):
            for kind, module in [('attention', layer.self_attn), ('ffn', layer.mlp)]:
                def hook(owner, args, kwargs, index=index, kind=kind):
                    hidden = kwargs.get('hidden_states', kwargs.get('x', args[0] if args else None))
                    if self.phase is None or hidden is None or hidden.ndim != 3:
                        raise RuntimeError('operator executed outside declared scoring phase')
                    if self.phase == 'decode' and hidden.shape[1] != 1:
                        raise RuntimeError('scored predictor bypassed single-token execution')
                    self.seen[kind].append(index)
                    self.tokens[self.phase][kind][index] += hidden.shape[0] * hidden.shape[1]
                self.handles.append(module.register_forward_pre_hook(hook, with_kwargs=True))

    def begin(self, phase):
        if self.phase is not None or phase not in self.calls:
            raise RuntimeError('unfinished/unknown execution phase')
        self.phase, self.seen = phase, {'attention': [], 'ffn': []}

    def end(self):
        if any(order != list(range(self.count)) for order in self.seen.values()):
            raise RuntimeError('not all configured layers executed exactly once in order')
        self.calls[self.phase] += 1
        self.phase = None

    def close(self):
        for handle in self.handles:
            handle.remove()

    def summary(self):
        return dict(installed_layers=self.count, calls=self.calls, tokens_per_layer=self.tokens,
                    every_scored_predictor_executed_all_layers=True)


class _Session:
    def __init__(self, model, mode, config, ffn, seed):
        if mode not in ('native', 'dense', 'sparq') or ffn not in ('none', 'b4_t32'):
            raise ValueError('unsupported attention/FFN mode')
        if type(seed) is not int or seed < 0:
            raise ValueError('seed must be nonnegative integer')
        self.model, self.controller, self.audit = model, None, None
        layers = list(model.model.layers)
        if (model.config.model_type != 'qwen3' or not layers
                or len(layers) != model.config.num_hidden_layers
                or model.config._attn_implementation != 'sdpa'
                or any(module.training for module in model.modules())
                or any(type(layer.mlp).__name__ != 'Qwen3MLP' for layer in layers)):
            raise ValueError('fresh eval Qwen3 with all original FFNs required')
        devices = {p.device for p in model.parameters()} | {b.device for b in model.buffers()}
        if len(devices) != 1:
            raise ValueError('one explicit model device required')
        self.device = next(iter(devices))
        self.ffn, self.mode = ffn, mode
        try:
            if mode != 'native':
                self.controller = SparQController(mode, config).install(model)
            if ffn != 'none':
                from ..stochastic.scorer import _install_ffn
                _install_ffn(model, dict(ffn=ffn, seed=seed))
            self.guard = self.snapshot()
            self.audit = ExecutionAudit(layers)
        except BaseException:
            if self.controller:
                self.controller.close()
            raise

    def snapshot(self):
        result = {name: _identity(p) for name, p in self.model.named_parameters()}
        for i, layer in enumerate(self.model.model.layers):
            result['mlp:' + str(i)] = id(layer.mlp)
            if self.ffn != 'none':
                for name in ('gu_codes', 'gu_decoded', 'gu_tile_lsb',
                             'down_codes', 'down_decoded', 'down_tile_lsb'):
                    result[f'{i}:{name}'] = _identity(getattr(layer.mlp, name))
        return result

    def forward(self, tokens, cache=None, phase='decode'):
        self.audit.begin(phase)
        scope = self.controller.prefill() if self.controller and phase == 'prefill' else nullcontext()
        with scope:
            output = self.model.model(input_ids=tokens, past_key_values=cache, use_cache=True)
        self.audit.end()
        return output

    def summary(self):
        result = self.audit.summary()
        if self.controller:
            stats = self.controller.stats()
            for state in stats['layers'].values():
                if (state['decode_calls'] != self.audit.calls['decode']
                        or state['prefill_calls'] != self.audit.calls['prefill']
                        or state['decode_query_tokens'] != self.audit.tokens['decode']['attention'][0]):
                    raise RuntimeError('replacement dispatch differs from independent all-layer audit')
            result['replacement'] = stats
        return result

    def close(self):
        if self.audit:
            self.audit.close()
        if self.controller:
            self.controller.close()
        if self.guard != self.snapshot():
            raise RuntimeError('model parameters/FFN objects/immutable W8 buffers changed during scoring')


def _hash_logits(digest, logits):
    value = logits.detach().float().cpu().contiguous()
    digest.update(struct.pack('<I', value.ndim))
    digest.update(struct.pack('<' + 'Q' * value.ndim, *value.shape))
    digest.update(value.numpy().astype('<f4', copy=False).tobytes())


def _positive(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name + ' must be positive integer')


def _source_identity():
    root = Path(__file__).resolve().parents[1]
    paths = ['sparq/adapter.py', 'sparq/scoring.py', 'sparq/core.py',
             'stochastic/vendor/scoring.py']
    return {('qwen3/' + name): hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in paths if (root / name).is_file()}


def evaluate_ppl(model, token_ids, *, mode='dense', config=None, context=2048,
                 stride=1024, protocol='full', suffix_decode=128,
                 suffix_examples=32, batch=4, ffn='none', seed=0,
                 max_windows=None, capture_logits_hash=False, progress=None):
    """All scored targets run q_len=1; batch only groups compatible windows.

    mode='native' is the unchanged cached SDPA gate. mode='dense' is the same
    native operator through the wrapper. max_windows explicitly marks a smoke.
    """
    _positive(batch, 'batch')
    if protocol not in ('full', 'suffix'):
        raise ValueError('protocol must be full or suffix')
    if token_ids.ndim == 2 and token_ids.shape[0] == 1:
        token_ids = token_ids[0]
    if token_ids.ndim != 1 or token_ids.dtype != torch.long:
        raise ValueError('one-dimensional int64 token IDs required')
    ids = token_ids.detach().cpu().contiguous()
    if ids.numel() < 2 or int(ids.min()) < 0 or int(ids.max()) >= model.config.vocab_size:
        raise ValueError('invalid corpus/vocabulary')
    full_plan = (full_window_plan(len(ids), context, stride) if protocol == 'full' else
                 suffix_plan(len(ids), context, suffix_decode, suffix_examples))
    plan = full_plan
    if max_windows is not None:
        _positive(max_windows, 'max_windows')
        plan = full_plan[:max_windows]
    metadata = plan_metadata(plan, len(ids), protocol)
    metadata['requested_segments'] = len(full_plan)
    metadata['smoke_limit'] = max_windows
    metadata['complete_requested_protocol'] = max_windows is None and len(plan) == len(full_plan)
    metadata['every_full_corpus_target_once'] &= metadata['complete_requested_protocol']
    started, records = time.perf_counter(), []
    digest = hashlib.sha256() if capture_logits_hash else None
    session = _Session(model, mode, config, ffn, seed)
    try:
        with torch.inference_mode():
            for rows in plan_batches(plan, batch):
                tokens = torch.stack([ids[row['begin']:row['end']] for row in rows]).to(session.device)
                prefix, steps = rows[0]['prefill_tokens'], rows[0]['scored_tokens']
                cache = None
                if prefix:
                    cache = session.forward(tokens[:, :prefix], phase='prefill').past_key_values
                losses = torch.zeros(len(rows), dtype=torch.float64, device=session.device)
                for step in range(steps):
                    pos = prefix + step
                    output = session.forward(tokens[:, pos:pos + 1], cache)
                    cache = output.past_key_values
                    logits = model.lm_head(output.last_hidden_state[:, -1]).float()
                    if digest is not None:
                        _hash_logits(digest, logits)
                    losses += F.cross_entropy(logits, tokens[:, pos + 1], reduction='none').double()
                for row, nll in zip(rows, losses.tolist()):
                    if not math.isfinite(nll):
                        raise RuntimeError('nonfinite NLL')
                    record = dict(row, nll_sum=nll,
                        target_positions_sha256_le_int64=ids_sha256(target_positions(row)))
                    records.append(record)
                    if progress:
                        progress(dict(kind='ppl_window', completed=len(records), total=len(plan), record=record))
                del cache, output, logits, losses, tokens
        audit = session.summary()
        if any(n != metadata['scored_tokens'] for n in audit['tokens_per_layer']['decode']['attention']):
            raise RuntimeError('executed predictors do not match exact target coverage')
    finally:
        session.close()
    return dict(test='qwen3_sparq_cached_ppl', mode=mode, ffn=ffn, seed=seed,
                **summarize_records(records), records=records, scoring_plan=metadata,
                token_ids_sha256_le_int64=ids_sha256(ids.tolist()), execution_audit=audit,
                scored_logits_sha256=digest.hexdigest() if digest else None,
                complete=metadata['complete_requested_protocol'],
                attention_config=audit.get('replacement', {}).get('config'),
                scoring_parameters=dict(context=context, stride=stride, protocol=protocol,
                    suffix_decode=suffix_decode, suffix_examples=suffix_examples, batch=batch),
                source_files_sha256=_source_identity(),
                ffn_config=None if ffn == 'none' else dict(policy='pot4', cycles=32, strata=32, mode='sampled'),
                scope='full_corpus' if metadata['every_full_corpus_target_once'] else 'suffix_or_smoke',
                elapsed_seconds=time.perf_counter() - started,
                precision='original model/cache dtype; FP32 logits/logsoftmax; FP64 NLL sum',
                prefill='native dense attention; FFN follows explicit ffn setting', physical_PPA=None)


def _rng_snapshot(session):
    # StratifiedFFN owns per-layer generators. Copy these, never infer GPU use
    # from global CUDA availability; CPU scoring must not initialize CUDA.
    result = []
    for layer in session.model.model.layers:
        for name, value in vars(layer.mlp).items():
            if isinstance(value, torch.Generator):
                result.append((value, value.get_state().clone()))
            elif isinstance(value, dict):
                result.extend((g, g.get_state().clone()) for g in value.values()
                              if isinstance(g, torch.Generator))
    return result


def _cache_map(cache, transform):
    """Legacy tensor cache support for independent fixtures; unknown types fail."""
    if isinstance(cache, torch.Tensor):
        return transform(cache)
    if isinstance(cache, tuple):
        return tuple(_cache_map(v, transform) for v in cache)
    if isinstance(cache, list):
        return [_cache_map(v, transform) for v in cache]
    if cache is None or isinstance(cache, (int, float, bool)):
        return cache
    raise TypeError('cache lacks supported independent-batch operations')


def _branch_cache(cache, copies):
    result = copy.deepcopy(cache)
    if copies != 1:
        if callable(getattr(result, 'batch_repeat_interleave', None)):
            result.batch_repeat_interleave(copies)
        else:
            result = _cache_map(result, lambda t: t.repeat_interleave(copies, dim=0))
    return result


def _select_cache(cache, indices):
    if callable(getattr(cache, 'batch_select_indices', None)):
        cache.batch_select_indices(indices)
        return cache
    return _cache_map(cache, lambda t: t.index_select(0, indices))


def evaluate_tasks(model, documents, *, mode='dense', config=None, ffn='none',
                   seed=0, doc_limit=None, max_length=2048, choice_batch=4,
                   tasks=None, progress=None):
    """No padding/truncation. Independent cache per option; official metrics optional.

    A shared last-prompt query scores every option's first token. Those reused
    logits passed through all layers once; choice_target_scores counts each use.
    """
    _positive(max_length, 'max_length')
    _positive(choice_batch, 'choice_batch')
    if ffn != 'none' and choice_batch != 1:
        raise ValueError('B4/T32 MC requires choice_batch=1 for its declared paired RNG protocol')
    documents = list(documents)
    if not documents:
        raise ValueError('empty document set')
    if doc_limit is not None:
        _positive(doc_limit, 'doc_limit')
    selected = documents if doc_limit is None else documents[:doc_limit]
    seen = set()
    for row in selected:
        if row['id'] in seen:
            raise ValueError('duplicate document ID')
        seen.add(row['id'])
        context, choices = row['context_ids'], row['choices_ids']
        if not context or len(choices) < 2:
            raise ValueError('nonempty prompt and at least two choices required')
        for answer in choices:
            if (not answer or len(context) + len(answer) - 1 > max_length
                    or any(type(t) is not int or not 0 <= t < model.config.vocab_size for t in context + answer)):
                raise ValueError('unsupported tokens/length; no silent truncation')
    session, records = _Session(model, mode, config, ffn, seed), []
    started, choice_targets, shared_first = time.perf_counter(), 0, 0
    try:
        with torch.inference_mode():
            for row in selected:
                context = torch.tensor(row['context_ids'], dtype=torch.long, device=session.device)[None]
                cache = None
                if context.shape[1] > 1:
                    cache = session.forward(context[:, :-1], phase='prefill').past_key_values
                first = session.forward(context[:, -1:], cache)
                lp = F.log_softmax(model.lm_head(first.last_hidden_state[:, -1]).float(), -1)
                base_cache, base_rng = copy.deepcopy(first.past_key_values), _rng_snapshot(session)
                values = [None] * len(row['choices_ids'])
                # Token-only order does not inspect labels; restores FFN branch
                # randomness so choice order cannot alter another option score.
                order = sorted(range(len(values)), key=lambda i: tuple(row['choices_ids'][i]))
                for index in order:
                    answer = row['choices_ids'][index]
                    values[index] = dict(terms=[float(lp[0, answer[0]])],
                        is_greedy=int(lp.argmax(-1)[0]) == answer[0], tokens=len(answer))
                    choice_targets += len(answer)
                for begin in range(0, len(order), choice_batch):
                    active = [index for index in order[begin:begin + choice_batch]
                              if len(row['choices_ids'][index]) > 1]
                    if not active:
                        continue
                    cache = _branch_cache(base_cache, len(active))
                    for generator, state in base_rng:
                        generator.set_state(state)
                    step = 1
                    while active:
                        inp = torch.tensor([[row['choices_ids'][i][step - 1]] for i in active],
                                           dtype=torch.long, device=session.device)
                        output = session.forward(inp, cache)
                        cache = output.past_key_values
                        current = F.log_softmax(model.lm_head(output.last_hidden_state[:, -1]).float(), -1)
                        targets = torch.tensor([row['choices_ids'][i][step] for i in active],
                                               dtype=torch.long, device=session.device)
                        terms = current.gather(-1, targets[:, None]).squeeze(-1).tolist()
                        greedy = (current.argmax(-1) == targets).tolist()
                        remaining = []
                        for position, (index, term, correct) in enumerate(zip(active, terms, greedy)):
                            values[index]['terms'].append(term)
                            values[index]['is_greedy'] &= correct
                            if len(row['choices_ids'][index]) > step + 1:
                                remaining.append(position)
                        if remaining and len(remaining) != len(active):
                            cache = _select_cache(cache, torch.tensor(remaining, dtype=torch.long,
                                                                      device=session.device))
                        active = [active[i] for i in remaining]
                        step += 1
                for value in values:
                    score = math.fsum(value.pop('terms'))
                    if not math.isfinite(score):
                        raise RuntimeError('nonfinite choice likelihood')
                    value['logprob'] = score
                shared_first += len(values) - 1
                result = {key: row[key] for key in ('id', 'task', 'doc_id') if key in row}
                result['choices'] = values
                if tasks is not None:
                    task = tasks[row['task']]
                    result['metrics'] = task.process_results(task.eval_docs[row['doc_id']],
                        [(v['logprob'], v['is_greedy']) for v in values])
                records.append(result)
                if progress:
                    progress(dict(kind='task_document', completed=len(records), total=len(selected), record=result))
        audit = session.summary()
        if audit['tokens_per_layer']['decode']['attention'] != [choice_targets - shared_first] * audit['installed_layers']:
            raise RuntimeError('choice scores are not covered by all-layer decode execution')
    finally:
        session.close()
    return dict(test='qwen3_sparq_official_mc_likelihood', mode=mode, ffn=ffn, seed=seed,
                documents=records, evaluated_documents=len(records), requested_documents=len(documents),
                complete=doc_limit is None, smoke_limit=doc_limit, execution_audit=audit,
                choice_target_scores=choice_targets, shared_first_target_reuses=shared_first,
                attention_config=audit.get('replacement', {}).get('config'),
                source_files_sha256=_source_identity(), max_length=max_length,
                ffn_config=None if ffn == 'none' else dict(policy='pot4', cycles=32, strata=32, mode='sampled'),
                choice_batch=choice_batch, cache_policy='deep copy prompt cache, repeat independent rows, remove completed rows; no dummy/padded tokens',
                protocol='0-shot likelihood; official task prompts and process_results; no chat template',
                elapsed_seconds=time.perf_counter() - started, physical_PPA=None)


def build_task_documents(task, name, tokenizer, max_length=2048):
    """Use lm-eval's official boundary handling; caller pins task/data sources."""
    from types import MethodType, SimpleNamespace
    from lm_eval.models.huggingface import HFLM
    encoder = SimpleNamespace(tokenizer=tokenizer, backend='causal', add_bos_token=False)
    encoder.tok_encode = MethodType(HFLM.tok_encode, encoder)
    rows = []
    for index, doc in task.doc_iterator():
        context = task.fewshot_context(doc, num_fewshot=0)
        contexts, choices = [], []
        for request in task.construct_requests(doc, context, metadata=(name, index, 1)):
            if request.request_type != 'loglikelihood':
                raise ValueError('only official likelihood requests are supported')
            c, a = HFLM._encode_pair(encoder, *request.args)
            if not c or not a or len(c) + len(a) - 1 > max_length:
                raise ValueError('empty/overlength official request; no silent truncation')
            contexts.append(c)
            choices.append(a)
        if not contexts or any(c != contexts[0] for c in contexts):
            raise ValueError('options must share identical tokenized context')
        rows.append(dict(id=f'{name}:{index}', task=name, doc_id=index,
                         context_ids=contexts[0], choices_ids=choices))
    return rows
