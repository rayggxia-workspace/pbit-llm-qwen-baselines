"""Cached target scoring with the unchanged historical S12/P8 Attention path."""
from contextlib import AbstractContextManager
import hashlib
import json
import math
from pathlib import Path
import time


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    path.write_bytes(raw)
    path.with_suffix('.sha256').write_bytes((hashlib.sha256(raw).hexdigest() + '\n').encode())


class Engine(AbstractContextManager):
    def __init__(self, model, context, case, seed, domain, record_inputs=False):
        self.model, self.context, self.case = model, context, case
        self.seed, self.domain = seed, domain
        self.record_inputs = record_inputs
        self.calls, self.scored, self.prefill = 0, [0] * 36, [0] * 36
        self.inputs = []

    def __enter__(self):
        from attention_mode import JointController
        from experiments.attention_gap_accuracy_20261102.methods import Patch
        from experiments.sparq_ising_20261028.core import Config
        self.gap = Patch('ising64_gap_s12_p8' if self.case else 'bf16')
        self.gap.__enter__()
        cfg = Config(r=32, k=128, local=32, samples=64, burn=0, mode='winner') if self.case else None
        self.ctl = JointController(self.model, cfg, '%s:%s' % (self.seed, self.domain))
        self.context.seed = self.seed
        return self

    def __exit__(self, *exc):
        try:
            self.ctl.close()
        finally:
            self.gap.__exit__(*exc)
        return False

    def forward(self, ids, cache, prefix):
        self.ctl.prefix = prefix
        self.context.begin(0, self.calls, domain=self.domain)
        self.calls += 1
        result = self.model(ids, past_key_values=cache, use_cache=True, logits_to_keep=1)
        assert len(self.context.coverage) == 36
        for layer, info in self.context.coverage.items():
            assert info['calls'] == 1 and info['tokens'] == ids.numel()
            (self.prefill if prefix else self.scored)[layer] += ids.numel()
        if self.case:
            for layer in self.model.model.layers:
                ar = layer.mlp.last_arithmetic
                assert (ar['T_x'], ar['T_AND']) == (64, 128)
        if self.record_inputs:
            self.inputs.append({'call': self.calls - 1, 'prefix': prefix, 'shape': list(ids.shape),
                                'input_ids_sha256': hashlib.sha256(ids.cpu().numpy().tobytes()).hexdigest()})
        return result

    def report(self, expected_targets):
        assert self.scored == [expected_targets] * 36
        assert all(v['decode_queries'] == expected_targets for v in self.ctl.state.values())
        if self.case:
            assert all(v['sampled_head_rows'] == expected_targets * 32 for v in self.ctl.state.values())
        attention = self.ctl.report()
        attention['FFN_sampling'] = self.case if self.case else 'BF16 parent'
        return {'calls': self.calls, 'scored_tokens_per_layer': self.scored,
                'prefill_tokens_per_layer': self.prefill, 'attention': attention,
                'quantization': self.gap.report(), 'input_ledger': self.inputs,
                'input_ledger_sha256': hashlib.sha256((json.dumps(self.inputs, separators=(',', ':')) + '\n').encode()).hexdigest()}


def score_ppl(model, context, case, tokens, seed, output, parts, batch=8,
              suffix=False, capture=False):
    import numpy as np
    import torch
    from torch.nn import functional as F
    from transformers import DynamicCache
    from experiments.sparq_ising_20261028.vendor.plans import suffix_plan, full_window_plan, plan_batches
    full = suffix_plan(len(tokens), 2048, 128, 8) if suffix else full_window_plan(len(tokens), 2048, 1024)
    records, audits = [], []
    started = time.monotonic()
    digest = hashlib.sha256()
    with torch.no_grad():
        for part in parts:
            plan = full if suffix else full[part:part + 8]
            if not plan:
                raise ValueError('empty PPL part')
            targets = sum(r['scored_tokens'] for r in plan)
            # The historical FFN stream label remains a label, not a T setting.
            with Engine(model, context, case, seed, 'joint-trained-ffn16:' + str(part)) as engine:
                for rows in plan_batches(plan, batch):
                    prefix, steps = rows[0]['prefill_tokens'], rows[0]['scored_tokens']
                    caches = []
                    if prefix:
                        for row in rows:
                            ids = torch.as_tensor(np.asarray(tokens[row['begin']:row['begin'] + prefix], dtype=np.int64), device='cuda')[None]
                            result = engine.forward(ids, None, True)
                            caches.append(result.past_key_values)
                            del result, ids
                        legacy = tuple((torch.cat([c.key_cache[i] for c in caches]),
                                        torch.cat([c.value_cache[i] for c in caches])) for i in range(36))
                        cache = DynamicCache.from_legacy_cache(legacy)
                        del legacy, caches
                    else:
                        cache = None
                    losses = torch.zeros(len(rows), device='cuda', dtype=torch.float64)
                    for step in range(steps):
                        pos = prefix + step
                        ids = torch.tensor([[int(tokens[r['begin'] + pos])] for r in rows], device='cuda')
                        target = torch.tensor([int(tokens[r['begin'] + pos + 1]) for r in rows], device='cuda')
                        result = engine.forward(ids, cache, False)
                        cache = result.past_key_values
                        logits = result.logits[:, -1].float()
                        assert bool(torch.isfinite(logits).all())
                        losses += F.cross_entropy(logits, target, reduction='none').double()
                        if capture:
                            digest.update(logits.cpu().contiguous().numpy().tobytes())
                    for row, loss in zip(rows, losses.tolist()):
                        first = row['begin'] + prefix + 1
                        last = first + steps
                        raw = np.asarray(tokens[first:last], dtype='<u4').tobytes()
                        records.append(dict(row, nll_sum=loss, target_begin=first, target_end=last,
                                            target_token_sha256=hashlib.sha256(raw).hexdigest()))
                    save(Path(output) / 'PROGRESS.json', {'status': 'running', 'records': records,
                         'scored_targets': sum(r['scored_tokens'] for r in records), 'seconds': time.monotonic() - started})
                    del cache, result, logits, ids, target, losses
                audits.append(engine.report(targets))
            if suffix:
                break
    total = sum(r['scored_tokens'] for r in records)
    nll = sum(r['nll_sum'] for r in records)
    return {'targets': total, 'nll': nll, 'ppl': math.exp(nll / total), 'records': records,
            'audits': audits, 'seconds': time.monotonic() - started,
            'logits_sha256': digest.hexdigest() if capture else None,
            'prefix_attention': 'accurate SDPA', 'scored_attention': 'sampled S64' if case else 'BF16 parent'}


def task_lm(model, tokenizer, context, case, seed, task_name, shard_start, output):
    import torch
    from lm_eval.models.huggingface import HFLM

    class CachedLM(HFLM):
        def __init__(self):
            super().__init__(pretrained=model, tokenizer=tokenizer, backend='causal', batch_size=1,
                             max_length=2048, add_bos_token=False, logits_cache=False, truncation=False)
            self.requests_audit, self.targets, self.reports = [], 0, []
            self.started = time.monotonic()

        def _loglikelihood_tokens(self, requests, disable_tqdm=False, override_bs=None):
            from torch.nn import functional as F
            values = []
            with torch.no_grad():
                for _, c, a in requests:
                    assert c and a and len(c) + len(a) <= 2049
                    key = hashlib.sha256((json.dumps([c, a], separators=(',', ':')) + '\n').encode()).hexdigest()
                    domain = 'and128-task:%s:%d:%d' % (task_name, shard_start, len(self.requests_audit))
                    with Engine(model, context, case, seed, domain, record_inputs=True) as engine:
                        cache = None
                        if len(c) > 1:
                            ids = torch.tensor([c[:-1]], device='cuda')
                            result = engine.forward(ids, cache, True)
                            cache = result.past_key_values
                        nll, exact = 0.0, True
                        inputs = [c[-1]] + a[:-1]
                        for input_id, target_id in zip(inputs, a):
                            ids = torch.tensor([[input_id]], device='cuda')
                            result = engine.forward(ids, cache, False)
                            cache = result.past_key_values
                            logp = F.log_softmax(result.logits[:, -1].float(), dim=-1)
                            assert bool(torch.isfinite(logp).all())
                            nll += float(logp[0, target_id])
                            exact = exact and int(logp.argmax(-1)) == target_id
                        self.reports.append(engine.report(len(a)))
                    self.targets += len(a)
                    self.requests_audit.append({'tokens_sha256': key, 'context_tokens': len(c), 'answer_tokens': len(a)})
                    values.append((nll, exact))
                    del cache, result, ids
                    if len(self.requests_audit) % 16 == 0:
                        save(Path(output) / 'PROGRESS.json', {'status': 'running', 'requests': len(self.requests_audit),
                             'targets': self.targets, 'seconds': time.monotonic() - self.started})
            return values

    return CachedLM()
