"""Pure scoring plans. Importing this module never imports Torch/CUDA."""
import hashlib
import math
import struct


def _positive_int(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name + ' must be a positive integer')


def ids_sha256(values):
    """Hash signed little-endian int64 IDs/positions, independent of platform."""
    digest = hashlib.sha256()
    for value in values:
        digest.update(struct.pack('<q', int(value)))
    return digest.hexdigest()


def suffix_offsets(token_count, context=2048, decode=128, examples=32):
    for name, value in [('token_count', token_count), ('context', context),
                        ('decode', decode), ('examples', examples)]:
        _positive_int(value, name)
    if context < 3:
        raise ValueError('suffix context>=3 keeps prefill multi-token and exact SDPA')
    last = token_count - context - decode
    if last < 0:
        raise ValueError('corpus shorter than context+decode')
    # Exact half-even linspace rounding; pinned WT2/32 starts agree with the
    # historical torch.linspace(...).round().long() manifest.
    starts = [0] if examples == 1 else [round(last * i / (examples - 1)) for i in range(examples)]
    if len(set(starts)) != examples:
        raise ValueError('linspace starts are not unique')
    return starts


def suffix_plan(token_count, context=2048, decode=128, examples=32):
    starts = suffix_offsets(token_count, context, decode, examples)
    rows = [dict(segment_id=i, begin=start, end=start + context + decode,
                 first_target=start + context, last_target_exclusive=start + context + decode,
                 prefill_tokens=context - 1, scored_tokens=decode)
            for i, start in enumerate(starts)]
    positions = [position for row in rows for position in target_positions(row)]
    if len(set(positions)) != len(positions):
        raise ValueError('suffix target ranges overlap; choose fewer examples')
    return rows


def full_window_plan(token_count, context=2048, stride=1024):
    for name, value in [('token_count', token_count), ('context', context), ('stride', stride)]:
        _positive_int(value, name)
    if token_count < 2 or context < 3 or stride > context:
        raise ValueError('full protocol needs N>=2, context>=3 and stride<=context')
    rows, previous_end = [], 0
    for begin in range(0, token_count, stride):
        end = min(begin + context, token_count)
        first = max(previous_end, begin + 1)
        if first < end:
            rows.append(dict(segment_id=len(rows), begin=begin, end=end,
                             first_target=first, last_target_exclusive=end,
                             prefill_tokens=first - begin - 1, scored_tokens=end - first))
        previous_end = end
        if end == token_count:
            break
    # This also detects skipped or duplicated targets without a huge saved list.
    expected = 1
    for row in rows:
        if row['first_target'] != expected:
            raise AssertionError('full target coverage is discontinuous')
        expected = row['last_target_exclusive']
    if expected != token_count:
        raise AssertionError('full target coverage does not reach corpus end')
    return rows


def target_positions(row):
    return range(row['first_target'], row['last_target_exclusive'])


def plan_batches(plan, batch):
    """Consecutive compatible spans only: stable order, no padding/future data."""
    _positive_int(batch, 'batch')
    pending, signature = [], None
    for row in plan:
        current = (row['end'] - row['begin'], row['prefill_tokens'], row['scored_tokens'])
        if pending and (current != signature or len(pending) == batch):
            yield pending
            pending = []
        signature = current
        pending.append(row)
    if pending:
        yield pending


def plan_metadata(plan, token_count, protocol):
    scored = sum(row['scored_tokens'] for row in plan)
    positions = (position for row in plan for position in target_positions(row))
    return dict(protocol=protocol, source_tokens=token_count, scored_tokens=scored,
                target_positions_sha256_le_int64=ids_sha256(positions),
                every_full_corpus_target_once=(protocol == 'full' and scored == token_count - 1),
                segment_starts=[row['begin'] for row in plan], segments=plan,
                prefill='tokens strictly before the first scored input query; SDPA multi-token prefix',
                first_query='input at first_target-1 predicts first_target',
                full_warning='cached matched scorer; not bitwise equivalent to the vectorized BF16 anchor')


def summarize_records(records):
    scored = sum(row['scored_tokens'] for row in records)
    nll = math.fsum(row['nll_sum'] for row in records)
    if scored < 1 or not math.isfinite(nll) or nll < 0:
        raise ValueError('invalid/nonfinite scored NLL')
    return dict(scored_tokens=scored, nll_sum=nll, mean_nll=nll / scored,
                perplexity=math.exp(nll / scored))
