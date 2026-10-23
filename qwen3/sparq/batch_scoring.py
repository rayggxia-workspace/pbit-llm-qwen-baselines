"""Optional exact-length document batching for the original-FFN MC control.

No prompt padding or truncation. Qwen3 DynamicCache rows are independently
copied for each option, including repeated parent-document indices. This is a
different BF16 batch-shape protocol from serial evaluation; compare dense and
SparQ with the SAME batching plan and validate the serial numerical difference.
"""
from collections import OrderedDict
import copy
import hashlib
import math
from pathlib import Path
import time

import torch
from torch.nn import functional as F

from .scoring import _Session, _positive, _select_cache, _source_identity


def document_groups(documents, document_batch=8, max_choice_rows=32):
    """Stable first-seen-length buckets, then original order inside each bucket."""
    _positive(document_batch, 'document_batch')
    _positive(max_choice_rows, 'max_choice_rows')
    if document_batch > 8 or max_choice_rows > 32:
        raise ValueError('validated limits are at most 8 documents and 32 choice rows')
    buckets = OrderedDict()
    for index, row in enumerate(documents):
        count = len(row['choices_ids'])
        if count > max_choice_rows:
            raise ValueError('one document exceeds max_choice_rows; no choice may be omitted')
        buckets.setdefault(len(row['context_ids']), []).append(index)
    for indices in buckets.values():
        pending, choices = [], 0
        for index in indices:
            count = len(documents[index]['choices_ids'])
            if pending and (len(pending) == document_batch or choices + count > max_choice_rows):
                yield pending
                pending, choices = [], 0
            pending.append(index)
            choices += count
        if pending:
            yield pending


def evaluate_tasks_batched(model, documents, *, mode='dense', config=None,
                           document_batch=8, max_choice_rows=32, ffn='none', seed=0,
                           doc_limit=None, max_length=2048, tasks=None, progress=None):
    """Score every option; original input order is restored in results/progress.

    document_batch and max_choice_rows are maxima, not padding targets. The
    original FFN is mandatory because independent per-document stochastic RNG
    streams have not been defined for this batch-shape change. No model/device
    allocation occurs here except inference on the caller's existing model.
    """
    if ffn != 'none':
        raise ValueError('document batching currently requires original FFN (ffn=none)')
    _positive(max_length, 'max_length')
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
                raise ValueError('unsupported tokens/length; no padding or silent truncation')
    groups = list(document_groups(selected, document_batch, max_choice_rows))
    records = [None] * len(selected)
    started = time.perf_counter()
    choice_targets = shared_first = next_progress = peak_choice_rows = 0
    session = _Session(model, mode, config, ffn, seed)
    try:
        with torch.inference_mode():
            for group in groups:
                context = torch.tensor([selected[index]['context_ids'] for index in group],
                                       dtype=torch.long, device=session.device)
                cache = None
                if context.shape[1] > 1:
                    cache = session.forward(context[:, :-1], phase='prefill').past_key_values
                first = session.forward(context[:, -1:], cache)
                logprob = F.log_softmax(model.lm_head(first.last_hidden_state[:, -1]).float(), -1)
                # The base is immutable from this point. Only a deep-copied
                # branch is indexed with repeated parent rows and then updated.
                base_cache = first.past_key_values
                branches = []
                values = []
                for parent, index in enumerate(group):
                    answers = selected[index]['choices_ids']
                    values.append([None] * len(answers))
                    shared_first += len(answers) - 1
                    for option in sorted(range(len(answers)), key=lambda i: tuple(answers[i])):
                        answer = answers[option]
                        branches.append((parent, option, answer))
                        choice_targets += len(answer)
                parents = torch.tensor([row[0] for row in branches], device=session.device)
                targets = torch.tensor([row[2][0] for row in branches], device=session.device)
                initial_terms = logprob[parents, targets].tolist()
                initial_greedy = (logprob.argmax(-1)[parents] == targets).tolist()
                for (parent, option, answer), term, greedy in zip(branches, initial_terms, initial_greedy):
                    values[parent][option] = dict(terms=[term], is_greedy=greedy, tokens=len(answer))
                active = [index for index, branch in enumerate(branches) if len(branch[2]) > 1]
                peak_choice_rows = max(peak_choice_rows, len(active))
                if active:
                    parent_rows = torch.tensor([branches[i][0] for i in active],
                                               dtype=torch.long, device=session.device)
                    cache = _select_cache(copy.deepcopy(base_cache), parent_rows)
                step, output, current = 1, None, None
                while active:
                    inp = torch.tensor([[branches[index][2][step - 1]] for index in active],
                                       dtype=torch.long, device=session.device)
                    output = session.forward(inp, cache)
                    cache = output.past_key_values
                    current = F.log_softmax(model.lm_head(output.last_hidden_state[:, -1]).float(), -1)
                    target_ids = torch.tensor([branches[index][2][step] for index in active],
                                              dtype=torch.long, device=session.device)
                    terms = current.gather(-1, target_ids[:, None]).squeeze(-1).tolist()
                    correct = (current.argmax(-1) == target_ids).tolist()
                    remaining = []
                    for position, (index, term, greedy) in enumerate(zip(active, terms, correct)):
                        parent, option, answer = branches[index]
                        value = values[parent][option]
                        value['terms'].append(term)
                        value['is_greedy'] &= greedy
                        if len(answer) > step + 1:
                            remaining.append(position)
                    if remaining and len(remaining) != len(active):
                        cache = _select_cache(cache, torch.tensor(remaining, dtype=torch.long,
                                                                  device=session.device))
                    active = [active[index] for index in remaining]
                    step += 1
                for index, answers in zip(group, values):
                    for value in answers:
                        value['logprob'] = math.fsum(value.pop('terms'))
                        if not math.isfinite(value['logprob']):
                            raise RuntimeError('nonfinite choice likelihood')
                    row = selected[index]
                    result = {key: row[key] for key in ('id', 'task', 'doc_id') if key in row}
                    result['choices'] = answers
                    if tasks is not None:
                        task = tasks[row['task']]
                        result['metrics'] = task.process_results(task.eval_docs[row['doc_id']],
                            [(value['logprob'], value['is_greedy']) for value in answers])
                    records[index] = result
                # Publish only the completed contiguous input prefix, even when
                # later same-length documents were computed ahead of that prefix.
                while next_progress < len(records) and records[next_progress] is not None:
                    if progress:
                        progress(dict(kind='task_document', completed=next_progress + 1,
                                      total=len(selected), record=records[next_progress]))
                    next_progress += 1
                # Free complete groups' cache state before the next prefill.
                del base_cache, first, cache, context, logprob, output, current
        audit = session.summary()
        expected = choice_targets - shared_first
        if audit['tokens_per_layer']['decode']['attention'] != [expected] * audit['installed_layers']:
            raise RuntimeError('batched choices are not covered by all-layer decode execution')
        if next_progress != len(records) or any(row is None for row in records):
            raise RuntimeError('document order reconstruction is incomplete')
    finally:
        session.close()
    sources = _source_identity()
    sources['qwen3/sparq/batch_scoring.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return dict(test='qwen3_sparq_official_mc_document_batches', mode=mode, ffn=ffn, seed=seed,
        documents=records, evaluated_documents=len(records), requested_documents=len(documents),
        complete=doc_limit is None, smoke_limit=doc_limit, execution_audit=audit,
        choice_target_scores=choice_targets, shared_first_target_reuses=shared_first,
        attention_config=audit.get('replacement', {}).get('config'), source_files_sha256=sources,
        max_length=max_length, ffn_config=None, document_batch=document_batch,
        max_choice_rows=max_choice_rows, document_groups=len(groups),
        group_document_counts=[len(group) for group in groups],
        group_choice_counts=[sum(len(selected[i]['choices_ids']) for i in group) for group in groups],
        actual_peak_continuation_rows=peak_choice_rows,
        cache_policy='deep copy immutable multi-document prompt cache; select repeated parent rows; remove completed options; no padding',
        batching='stable first-seen exact context length buckets; original order inside bucket; original result/progress order',
        protocol='0-shot official prompts/process_results; raw likelihood; no chat template or prompt truncation',
        numerical_boundary='BF16 batch shapes differ from serial; report serial score/prediction differences before adoption; match dense/SparQ batch plan',
        elapsed_seconds=time.perf_counter() - started, physical_PPA=None)
