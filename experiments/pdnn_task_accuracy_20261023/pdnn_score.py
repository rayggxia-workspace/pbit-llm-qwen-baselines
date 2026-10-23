"""Issue145: floating-weight, full-path P-DNN cached multiple-choice scoring.

The official task/tokenizer layer is deliberately separate. The caller supplies
unchanged Harness requests and calls its official process_results afterwards.
No labels, training, W8 quantization or sampled Attention are used here.

Scoring flow adapted from Issue59 at integration 6966739a5223680888bf0315f7bb4f73423a1ae6:
experiments/qwen_task_accuracy_20261019/cached_score.py
Git blob 7d5046a84c5a55088b06ac148443cc0eb33c889b.
The unchanged full-path operator used by the strict loader is:
experiments/pdnn_ffn/full_path_pdnn_ffn.py
Git blob 35f147161eb5e2b65407417f5f84411cad0e3631.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import time

import torch
from torch.nn import functional as F


SOURCE_PROVENANCE = {
    'integration': '6966739a5223680888bf0315f7bb4f73423a1ae6',
    'cached_score_git_blob': '7d5046a84c5a55088b06ac148443cc0eb33c889b',
    'full_path_git_blob': '35f147161eb5e2b65407417f5f84411cad0e3631',
}


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def model_device(model):
    """Require one actual device; never probe CUDA availability on a CPU path."""
    values = list(model.parameters()) + list(model.buffers())
    if not values:
        raise ValueError('model must have parameters or buffers')
    devices = {value.device for value in values}
    if len(devices) != 1 or next(iter(devices)).type not in ('cpu', 'cuda'):
        raise ValueError('unsharded CPU or allocated single-CUDA-device model required')
    return next(iter(devices))


def rng_snapshot(device):
    device = torch.device(device)
    result = {'cpu': torch.get_rng_state().clone(), 'cuda': None, 'device': str(device)}
    if device.type == 'cuda':
        result['cuda'] = torch.cuda.get_rng_state(device).clone()
    elif device.type != 'cpu':
        raise ValueError('unsupported model device')
    return result


def rng_restore(snapshot):
    torch.set_rng_state(snapshot['cpu'])
    if snapshot['cuda'] is not None:
        torch.cuda.set_rng_state(snapshot['cuda'], device=torch.device(snapshot['device']))


def rng_seed(seed, device):
    # torch.manual_seed also touches CUDA generators. CPU jobs must not do so.
    torch.random.default_generator.manual_seed(seed)
    device = torch.device(device)
    if device.type == 'cuda':
        with torch.cuda.device(device):
            torch.cuda.manual_seed(seed)


def _variant(variant):
    expected = {'layers', 'samples', 'seed', 'batch', 'context'}
    if set(variant) != expected:
        raise ValueError('variant fields must be exactly layers,samples,seed,batch,context')
    result = copy.deepcopy(variant)
    layers = result['layers']
    if not isinstance(layers, (list, tuple)) or any(type(i) is not int or not 0 <= i < 24 for i in layers):
        raise ValueError('layers must be unique decoder indices in 0..23')
    if len(set(layers)) != len(layers) or len(layers) not in (0, 2, 4):
        raise ValueError('Issue145 uses BF16 or exactly two/four explicitly selected FFNs')
    result['layers'] = sorted(layers)
    for key, minimum, maximum in (('samples', 1, None), ('seed', 0, None),
                                   ('batch', 1, 16), ('context', 3, None)):
        value = result[key]
        if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
            raise ValueError('invalid integer variant field: ' + key)
    return result


def _validated_documents(documents, max_length):
    result, seen = [], set()
    for index, raw in enumerate(documents):
        if not isinstance(raw, dict) or not isinstance(raw.get('id'), str) or not raw['id'] or raw['id'] in seen:
            raise ValueError('each document requires a unique nonempty string id')
        seen.add(raw['id'])
        context, choices = raw.get('context_ids'), raw.get('choices_ids')
        if not isinstance(context, (list, tuple)) or len(context) < 3:
            raise ValueError('contexts require >=3 tokens')
        if not isinstance(choices, (list, tuple)) or len(choices) < 2:
            raise ValueError('at least two nonempty choices required')
        for values in [context, *choices]:
            if not isinstance(values, (list, tuple)) or not values or any(type(v) is not int or v < 0 for v in values):
                raise ValueError('token IDs must be nonnegative integers')
        if len(context) + max(map(len, choices)) - 1 > max_length:
            raise ValueError('context plus scored choice exceeds explicit context bound')
        result.append(dict(id=raw['id'], task=str(raw.get('task', '')), index=index,
                           context_ids=list(context), choices_ids=[list(a) for a in choices]))
    if not result:
        raise ValueError('at least one document required')
    return result


def document_batches(documents, batch):
    groups = {}
    for row in documents:
        groups.setdefault((len(row['context_ids']), len(row['choices_ids'])), []).append(row)
    for signature in sorted(groups):
        group = groups[signature]
        for start in range(0, len(group), batch):
            yield group[start:start + batch]


def batch_seed(rows, seed):
    payload = json.dumps([seed, [(r['task'], r['id']) for r in rows]],
                         ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], 'little') % (2**31 - 1)


def _tensor_identity(value):
    return (id(value), value.data_ptr(), tuple(value.shape), str(value.dtype),
            str(value.device), value.requires_grad, value._version)


class ModelGuard:
    """Check the actual installed modules, immutable tensors and sampling mode."""
    def __init__(self, model, variant):
        from experiments.pdnn_ffn.full_path_pdnn_ffn import FullPathPBitFFN
        self.model, self.variant = model, variant
        self.device = model_device(model)
        layers = list(model.model.layers)
        if len(layers) != 24 or model.training or any(m.training for m in model.modules()):
            raise ValueError('all 24 decoder layers and submodules must be in eval mode')
        selected = set(variant['layers'])
        for index, layer in enumerate(layers):
            if index in selected:
                if type(layer.mlp) is not FullPathPBitFFN:
                    raise ValueError('selected layer must be the original serial FullPathPBitFFN')
                _check_config(asdict(layer.mlp.config), model.config.hidden_size)
                if layer.mlp.sample_count != variant['samples']:
                    raise ValueError('installed sample_count differs from declared variant')
            elif type(layer.mlp).__name__ != 'Qwen2MLP':
                raise ValueError('unselected layers must retain original Qwen2MLP')
        for name, value in model.named_parameters():
            if value.requires_grad or value.dtype != torch.bfloat16:
                raise ValueError('frozen BF16 floating weights required: ' + name)
        self.modules = tuple(id(layer.mlp) for layer in layers)
        self.tensors = self._tensors()
        self.configs = self._configs()

    def _tensors(self):
        return {kind + ':' + name: _tensor_identity(value)
                for kind, items in (('parameter', self.model.named_parameters()),
                                    ('buffer', self.model.named_buffers())) for name, value in items}

    def _configs(self):
        return {index: (asdict(self.model.model.layers[index].mlp.config),
                        self.model.model.layers[index].mlp.sample_count)
                for index in self.variant['layers']}

    def verify(self):
        if self.modules != tuple(id(layer.mlp) for layer in self.model.model.layers):
            raise RuntimeError('FFN module identity changed during evaluation')
        if self.tensors != self._tensors() or self.device != model_device(self.model):
            raise RuntimeError('model parameter/buffer/device changed during evaluation')
        if self.configs != self._configs() or any(m.training for m in self.model.modules()):
            raise RuntimeError('sampling configuration or eval state changed during evaluation')


def _check_config(config, width):
    if (config.get('architecture', 'serial') != 'serial'
            or config.get('input_encoding', 'sigmoid') != 'sigmoid'
            or config.get('coding') not in ('bipolar', 'binary')
            or config.get('input_bits', 1) != 1
            or config.get('input_size') != width or config.get('output_size') != width
            or len(config.get('hidden_sizes', [])) != 1
            or type(config['hidden_sizes'][0]) is not int or config['hidden_sizes'][0] <= 0):
        raise ValueError('only one-bit-input serial two-matrix bipolar/binary FullPathPBitFFN is supported')
    for key in ('input_temperature', 'hidden_temperature', 'minimum_temperature'):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('finite positive temperature required: ' + key)


def install_students(model, checkpoints, samples, personal_root, device):
    """Verify explicit checkpoint bytes BEFORE loading; no implicit discovery.

    Every item requires layer,path,bytes,sha256. Optional student_type and
    student_config additionally pin CPU-inspected metadata. This function reads
    only files under the caller's already verified personal_root. It performs no
    ownership inference, writes, training or quantization. Payload loading uses
    weights_only=True. Returned records bind original bytes and effective config.
    """
    from experiments.pdnn_ffn.full_path_pdnn_ffn import FullPathPBitFFN, FullPathPBitFFNConfig
    if type(samples) is not int or samples <= 0 or len(checkpoints) not in (2, 4):
        raise ValueError('positive sample count and exactly two/four checkpoints required')
    actual = model_device(model)
    if actual != torch.device(device):
        raise ValueError('requested device differs from actual base model device')
    root = Path(personal_root).resolve(strict=True)
    if not root.is_dir() or len(model.model.layers) != 24 or any(m.training for m in model.modules()):
        raise ValueError('verified personal directory and 24-layer eval model required')
    if any(type(layer.mlp).__name__ != 'Qwen2MLP' for layer in model.model.layers):
        raise ValueError('install into a fresh original model exactly once')
    if any(value.dtype != torch.bfloat16 for value in model.parameters()):
        raise ValueError('base model weights must already be BF16')
    prepared, records, seen = [], [], set()
    for entry in checkpoints:
        if not {'layer', 'path', 'bytes', 'sha256'} <= set(entry):
            raise ValueError('explicit layer/path/bytes/sha256 required')
        index = entry['layer']
        if type(index) is not int or not 0 <= index < 24 or index in seen:
            raise ValueError('invalid or repeated checkpoint layer')
        seen.add(index)
        path = Path(entry['path']).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('checkpoint must be a regular file inside verified personal root')
        if type(entry['bytes']) is not int or entry['bytes'] <= 0 or path.stat().st_size != entry['bytes']:
            raise ValueError('checkpoint byte size changed')
        digest = file_sha256(path)
        if digest != entry['sha256']:
            raise ValueError('checkpoint SHA-256 changed')
        payload = torch.load(path, map_location='cpu', weights_only=True)
        if path.stat().st_size != entry['bytes'] or file_sha256(path) != digest:
            raise ValueError('checkpoint changed while loading')
        if not isinstance(payload, dict) or payload.get('training_args', {}).get('layer') != index:
            raise ValueError('checkpoint payload layer differs from manifest')
        for key in ('phase', 'step'):
            if key in entry and payload.get(key) != entry[key]:
                raise ValueError('manifest ' + key + ' differs from payload')
        source_config = dict(payload['student_config'])
        # September checkpoints omit fields that the public loader defaults.
        config_args = dict(source_config)
        config_args['hidden_sizes'] = tuple(config_args['hidden_sizes'])
        config = asdict(FullPathPBitFFNConfig(**config_args))
        _check_config(config, model.config.hidden_size)
        expected_type = ('full_path_bipolar_pdnn_v1' if config['coding'] == 'bipolar'
                         else 'full_path_binary_pdnn_v2')
        if payload.get('student_type') != expected_type:
            raise ValueError('checkpoint student_type differs from serial config')
        if entry.get('student_type', expected_type) != expected_type:
            raise ValueError('manifest student_type differs from payload')
        if 'student_config' in entry:
            if json.dumps(source_config, sort_keys=True) != json.dumps(entry['student_config'], sort_keys=True):
                raise ValueError('manifest student_config differs from payload')
        state = payload['student_state_dict']
        if not isinstance(state, dict) or any(not isinstance(v, torch.Tensor) or not v.is_floating_point()
                or not torch.isfinite(v).all().item() for v in state.values()):
            raise ValueError('checkpoint requires finite floating-point state tensors')
        config['hidden_sizes'] = tuple(config['hidden_sizes'])
        student = FullPathPBitFFN(FullPathPBitFFNConfig(**config))
        student.load_state_dict(state, strict=True)
        student.to(device=actual, dtype=torch.bfloat16).eval().requires_grad_(False)
        student.set_sample_count(samples)
        prepared.append((index, student))
        records.append(dict(layer=index, path=str(path), bytes=entry['bytes'], sha256=digest,
                            student_type=expected_type, source_student_config=source_config,
                            student_config=asdict(student.config), phase=payload.get('phase'),
                            step=payload.get('step'), training_args_layer=payload['training_args']['layer'],
                            samples=samples, device=str(actual), dtype='torch.bfloat16',
                            parameters=sum(p.numel() for p in student.parameters())))
    # Complete all validations before replacing any module.
    for index, student in prepared:
        model.model.layers[index].mlp = student
    model.requires_grad_(False)
    ModelGuard(model, dict(layers=sorted(seen), samples=samples))
    return sorted(records, key=lambda r: r['layer'])


class ExecutionAudit:
    def __init__(self, model):
        self.active, self.handles = None, []
        self.decode_calls = self.prefill_calls = self.query_rows = 0
        self.counts = {kind: {phase: [0] * 24 for phase in ('prefill', 'decode')}
                       for kind in ('decoder', 'ffn')}
        self.tokens = {phase: [0] * 24 for phase in ('prefill', 'decode')}
        self.seen = {}
        for index, layer in enumerate(model.model.layers):
            for kind, module in (('decoder', layer), ('ffn', layer.mlp)):
                def hook(owner, args, kwargs, index=index, kind=kind):
                    hidden = kwargs.get('hidden_states', kwargs.get('x', args[0] if args else None))
                    if self.active is None or hidden is None or hidden.ndim != 3:
                        raise RuntimeError('decoder/FFN executed outside declared scoring phase')
                    if index in self.seen[kind] or (self.active == 'decode') != (hidden.shape[1] == 1):
                        raise RuntimeError('repeated layer or wrong prefill/decode shape')
                    self.seen[kind].append(index)
                    self.counts[kind][self.active][index] += 1
                    if kind == 'ffn':
                        self.tokens[self.active][index] += hidden.shape[0] * hidden.shape[1]
                self.handles.append(module.register_forward_pre_hook(hook, with_kwargs=True))

    def begin(self, phase):
        if self.active is not None or phase not in ('prefill', 'decode'):
            raise RuntimeError('invalid nested scoring phase')
        self.active, self.seen = phase, {'decoder': [], 'ffn': []}

    def end(self, batch):
        if any(value != list(range(24)) for value in self.seen.values()):
            raise RuntimeError('every forward must execute all 24 decoder FFNs in order')
        if self.active == 'decode':
            self.decode_calls += 1
            self.query_rows += batch
        else:
            self.prefill_calls += 1
        self.active = None

    def summary(self, layers):
        return dict(actual_decode_calls=self.decode_calls, actual_prefill_calls=self.prefill_calls,
            actual_decode_query_rows=self.query_rows,
            decoder_decode_calls_per_layer=self.counts['decoder']['decode'].copy(),
            decoder_prefill_calls_per_layer=self.counts['decoder']['prefill'].copy(),
            ffn_decode_calls_per_layer=self.counts['ffn']['decode'].copy(),
            ffn_prefill_calls_per_layer=self.counts['ffn']['prefill'].copy(),
            ffn_decode_tokens_per_layer=self.tokens['decode'].copy(),
            ffn_prefill_tokens_per_layer=self.tokens['prefill'].copy(),
            replaced_layers=layers,
            replaced_decode_calls={str(i): self.counts['ffn']['decode'][i] for i in layers},
            replaced_prefill_calls={str(i): self.counts['ffn']['prefill'][i] for i in layers},
            every_scored_target_used_24_decoder_ffn_layers=True)

    def close(self):
        for handle in self.handles:
            handle.remove()


def evaluate_tasks(model, documents, variant, progress=None):
    """Score official tokenized requests with frozen installed P-DNN students.

    Preserves caller RNG even on failure. The input model is consumed in eval
    mode, with all weights frozen; no default CUDA device or generator is used
    when its actual tensors are on CPU. Only the actual allocated CUDA model
    device's generator is captured. Different topology/sample/batch conditions
    do not establish common P-DNN draws merely by using the same case seed.
    """
    variant = _variant(variant)
    rows = _validated_documents(documents, variant['context'])
    device = model_device(model)
    guard = ModelGuard(model, variant)
    vocab = model.config.vocab_size
    if any(v >= vocab for r in rows for sequence in [r['context_ids'], *r['choices_ids']] for v in sequence):
        raise ValueError('input token outside model vocabulary')
    caller_rng = rng_snapshot(device)
    audit = None
    started = time.perf_counter()
    result_rows, batch_records = [None] * len(rows), []
    stats = dict(shared_first_query_rows=0, branch_query_rows=0, dummy_query_rows=0,
                 scored_choice_tokens=0, batches=0, first_token_logit_reuses=0, completed_documents=0)

    def forward(tokens, cache, phase):
        audit.begin(phase)
        output = model.model(input_ids=tokens, past_key_values=cache, use_cache=True)
        audit.end(tokens.shape[0])
        return output

    try:
        audit = ExecutionAudit(model)
        with torch.inference_mode():
            for number, batch_rows in enumerate(document_batches(rows, variant['batch'])):
                size, length = len(batch_rows), len(batch_rows[0]['context_ids'])
                seed = batch_seed(batch_rows, variant['seed'])
                rng_seed(seed, device)
                context = torch.tensor([r['context_ids'] for r in batch_rows], device=device, dtype=torch.long)
                prefill = forward(context[:, :-1], None, 'prefill')
                first = forward(context[:, -1:], prefill.past_key_values, 'decode')
                del prefill
                logits = model.lm_head(first.last_hidden_state[:, -1]).float()
                shared_lp, shared_best = F.log_softmax(logits, -1), logits.argmax(-1)
                base_cache, base_rng = copy.deepcopy(first.past_key_values), rng_snapshot(device)
                del first, logits
                orders = [sorted(range(len(r['choices_ids'])), key=lambda j, r=r: tuple(r['choices_ids'][j]))
                          for r in batch_rows]
                choices_out = [[None] * len(r['choices_ids']) for r in batch_rows]
                stats['shared_first_query_rows'] += size
                for branch in range(len(batch_rows[0]['choices_ids'])):
                    answers = [r['choices_ids'][order[branch]] for r, order in zip(batch_rows, orders)]
                    rng_restore(base_rng)
                    cache = copy.deepcopy(base_cache)
                    target = torch.tensor([a[0] for a in answers], device=device)
                    score = shared_lp.gather(-1, target[:, None]).squeeze(-1).double()
                    greedy = shared_best == target
                    for position in range(1, max(map(len, answers))):
                        active = torch.tensor([position < len(a) for a in answers], device=device)
                        tokens = torch.tensor([[a[position-1] if position-1 < len(a) else 0]
                                               for a in answers], device=device)
                        output = forward(tokens, cache, 'decode')
                        cache = output.past_key_values
                        logits = model.lm_head(output.last_hidden_state[:, -1]).float()
                        target = torch.tensor([a[position] if position < len(a) else 0 for a in answers], device=device)
                        values = F.log_softmax(logits, -1).gather(-1, target[:, None]).squeeze(-1)
                        score += torch.where(active, values.double(), 0.)
                        greedy &= (~active) | (logits.argmax(-1) == target)
                        real = sum(position < len(a) for a in answers)
                        stats['branch_query_rows'] += real
                        stats['dummy_query_rows'] += size - real
                        del output, logits, tokens, values
                    for index, (answer, value, exact) in enumerate(zip(answers, score.tolist(), greedy.tolist())):
                        if not math.isfinite(value) or value > 1e-5:
                            raise RuntimeError('invalid choice loglikelihood')
                        choices_out[index][orders[index][branch]] = dict(logprob=value, is_greedy=bool(exact), tokens=len(answer))
                        stats['scored_choice_tokens'] += len(answer)
                    del cache, score, greedy, target
                completed = []
                for row, choices in zip(batch_rows, choices_out):
                    item = dict(id=row['id'], task=row['task'], context_tokens=length, choices=choices)
                    result_rows[row['index']] = item
                    completed.append(item)
                    stats['first_token_logit_reuses'] += len(choices) - 1
                stats['batches'] += 1
                stats['completed_documents'] += size
                batch_records.append(dict(batch=number, document_ids=[r['id'] for r in batch_rows],
                    context_tokens=length, seed=seed, rows=size,
                    choice_tokens=sum(len(a) for r in batch_rows for a in r['choices_ids'])))
                if device.type == 'cuda':
                    torch.cuda.synchronize(device)
                if progress:
                    progress(dict(documents=completed, batch=number,
                        elapsed_seconds=time.perf_counter() - started,
                        execution_audit=audit.summary(variant['layers'])))
                del context, base_cache, base_rng, shared_lp, shared_best
        expected = sum(len(a) for r in rows for a in r['choices_ids'])
        if stats['scored_choice_tokens'] != expected or any(r is None for r in result_rows):
            raise RuntimeError('not all choice tokens scored exactly once')
        if audit.query_rows != stats['shared_first_query_rows'] + stats['branch_query_rows'] + stats['dummy_query_rows']:
            raise RuntimeError('actual query row accounting mismatch')
        execution = dict(stats, **audit.summary(variant['layers']))
        execution.update(original_tokenized_requests=expected,
                         shared_first_query_counted_once_for_actual_execution=True)
    finally:
        try:
            if audit is not None:
                audit.close()
            guard.verify()
        finally:
            rng_restore(caller_rng)
    return dict(test='cached_mc_full_path_pdnn', variant=variant, documents=result_rows,
        execution_audit=execution, batches=batch_records, training=False,
        elapsed_seconds=time.perf_counter() - started, device=str(device), dtype='torch.bfloat16',
        source_provenance=SOURCE_PROVENANCE.copy(),
        protocol=dict(score='teacher-forced FP32 token log-softmax summed in FP64',
            first_target='last prompt token uses q_len=1; logits shared across choices',
            branch='deep-copy KV and restore global CPU plus actual CUDA-device RNG',
            choice_order='label-free lexicographic token IDs, mapped to original order',
            batching='exact prompt length and number of choices; no padding; batch <=16',
            attention='unchanged original SDPA in prefill and decode',
            ffn='only explicit layers replaced, both prefill and decode; floating BF16 weights',
            samples='complete stochastic paths averaged after continuous readout',
            rng='per-batch SHA256(task/doc IDs/case seed); caller RNG restored even on failure'),
        limitations=['batch composition and sample count affect global random-draw consumption',
            'same case seed across two/four layers does not prove shared draws',
            'dummy completed-choice rows retain batch shape but are never scored',
            'software stochastic simulation is not physical p-bit hardware',
            'official task definitions, labels and process_results remain caller responsibilities'])
