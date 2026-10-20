"""Cached teacher-forced joint FFN/attention reference for Issue 50.

The upstream adapter is installed while the fresh model still contains original
Qwen2MLP objects. FFNs are then replaced once, before either prefill or decode.
No upstream source is modified. Every scored query traverses all 24 layers with
q_len=1; only multi-token prefill attention retains the original SDPA path.
"""
import copy
import hashlib
import math
import struct
import time

from .upstream_attention import evaluate as upstream
from .upstream_attention.scoring import (full_window_plan, ids_sha256, plan_batches,
    plan_metadata, suffix_plan, summarize_records, target_positions)


FFN_CONFIGS = {
    'b2_t32': dict(policy='pot2', cycles=32, strata=32),
    'b4_t32': dict(policy='pot4', cycles=32, strata=32),
    'b4_t16': dict(policy='pot4', cycles=16, strata=16),
}
MODES = ('sdpa', 'digital_sdpa', 'screen_exact', 'screen_iid', 'screen_ising')
WEIGHT_BUFFERS = ('gu_codes', 'gu_decoded', 'gu_tile_lsb',
                  'down_codes', 'down_decoded', 'down_tile_lsb')


def _case(case):
    result = upstream._case(case)
    result.setdefault('ffn', 'none')
    result.setdefault('capture_scored_logits_sha256', False)
    if result['mode'] not in MODES or result['ffn'] not in ('none', *FFN_CONFIGS):
        raise ValueError('unknown joint attention/FFN mode')
    if type(result['capture_scored_logits_sha256']) is not bool:
        raise ValueError('capture_scored_logits_sha256 must be bool')
    return result


def _tensor_identity(value):
    return (id(value), value.data_ptr(), tuple(value.shape), str(value.dtype),
            str(value.device), value.requires_grad, value._version)


class ModelGuard:
    """Guard immutable parameters and quantized FFN buffers, excluding counters.

    Source model SHA-256 is a runner/staging responsibility. This guard detects
    replacement, storage changes and in-place writes during one scored case;
    diagnostics buffers and per-layer generators are intentionally mutable.
    """
    def __init__(self, model, ffn):
        self.model, self.ffn = model, ffn
        self.layers = list(model.model.layers)
        if len(self.layers) != 24 or model.training:
            raise ValueError('24-layer model in eval mode required')
        expected = 'Qwen2MLP' if ffn == 'none' else 'StratifiedFFN'
        if any(type(layer.mlp).__name__ != expected for layer in self.layers):
            raise ValueError('unexpected FFN object type in joint model')
        self.mlp_ids = [id(layer.mlp) for layer in self.layers]
        self.parameters = self.snapshot_parameters()
        self.weights = self.snapshot_weights()

    def snapshot_parameters(self):
        return {name: _tensor_identity(p) for name, p in self.model.named_parameters()}

    def snapshot_weights(self):
        if self.ffn == 'none':
            return {}
        return {(i, name): _tensor_identity(getattr(layer.mlp, name))
                for i, layer in enumerate(self.layers) for name in WEIGHT_BUFFERS}

    def verify(self):
        if self.mlp_ids != [id(layer.mlp) for layer in self.model.model.layers]:
            raise RuntimeError('FFN objects changed during joint evaluation')
        if self.parameters != self.snapshot_parameters():
            raise RuntimeError('parameter identity/storage/version changed during joint evaluation')
        if self.weights != self.snapshot_weights():
            raise RuntimeError('immutable FFN weight-buffer identity/storage/version changed')


class ExecutionAudit(upstream.ExecutionAudit):
    """Independent hooks for both 24-layer operator paths, in both phases."""
    def __init__(self, layers):
        super().__init__(layers)
        self.ffn_seen = []
        self.ffn_decode_by_layer = [0] * len(layers)
        self.ffn_prefill_by_layer = [0] * len(layers)
        self.ffn_decode_tokens_by_layer = [0] * len(layers)
        self.ffn_prefill_tokens_by_layer = [0] * len(layers)
        for index, layer in enumerate(layers):
            def hook(module, args, kwargs, index=index):
                hidden = kwargs.get('x', args[0] if args else None)
                if self.active is None or hidden is None or hidden.ndim != 3:
                    raise RuntimeError('FFN outside the declared scoring phase')
                if index in self.ffn_seen:
                    raise RuntimeError('FFN layer executed twice for one query')
                self.ffn_seen.append(index)
                if self.active == 'decode':
                    if hidden.shape[1] != 1:
                        raise RuntimeError('scored FFN query bypassed single-token decode')
                    self.ffn_decode_by_layer[index] += 1
                    self.ffn_decode_tokens_by_layer[index] += hidden.shape[0]
                else:
                    if hidden.shape[1] <= 1:
                        raise RuntimeError('prefill FFN must receive multi-token prefix')
                    self.ffn_prefill_by_layer[index] += 1
                    self.ffn_prefill_tokens_by_layer[index] += hidden.shape[0] * hidden.shape[1]
            self.handles.append(layer.mlp.register_forward_pre_hook(hook, with_kwargs=True))

    def begin(self, phase):
        super().begin(phase)
        self.ffn_seen = []

    def end(self, batch):
        if self.ffn_seen != list(range(len(self.decode_by_layer))):
            raise RuntimeError('every forward must execute all 24 FFNs in order')
        super().end(batch)


def _install_ffn(model, case):
    if case['ffn'] == 'none':
        return
    from experiments.qwen_multiscale_stratified_20261019.stratified_core import StratifiedFFN
    spec = FFN_CONFIGS[case['ffn']]
    for index, layer in enumerate(model.model.layers):
        layer.mlp = StratifiedFFN(layer.mlp, mode='sampled', seed=case['seed'],
                                  layer=index, **spec).eval()


def _update_logits_hash(digest, logits):
    # Always hash FP32 little-endian logits in scoring execution order, with
    # explicit shape boundaries. This diagnostic synchronizes and copies to CPU;
    # timed scientific cases disable it. It is not a PPL/equivalence tolerance.
    values = logits.detach().to(device='cpu').contiguous().numpy()
    digest.update(struct.pack('<I', values.ndim))
    digest.update(struct.pack('<' + 'Q' * values.ndim, *values.shape))
    digest.update(values.astype('<f4', copy=False).tobytes(order='C'))


def evaluate_case(model, token_ids, case, calibration):
    """Score a fresh model once; restore attention even on exceptions.

    The caller must provide a newly loaded eval model for each case. Replaced
    FFNs intentionally remain on that consumed model; original FFNs are not
    retained as a second GPU weight copy. Selector, CTMC and FFN RNG streams are
    independently seeded and never share generator state.
    """
    import torch
    from torch.nn import functional as F

    case = _case(case)
    if case['mode'].startswith('screen') and calibration is None:
        raise ValueError('screening requires fixed train-derived calibration')
    if token_ids.ndim == 2 and token_ids.shape[0] == 1:
        token_ids = token_ids[0]
    if token_ids.ndim != 1 or token_ids.dtype != torch.long:
        raise ValueError('token_ids must be one-dimensional int64 IDs')
    ids = token_ids.detach().cpu().contiguous()
    count = ids.numel()
    plan = (suffix_plan(count, case['context'], case['decode'], case['examples'])
            if case['protocol'] == 'suffix' else full_window_plan(count, case['context'], case['stride']))
    if any(row['prefill_tokens'] == 1 for row in plan):
        raise ValueError('plan has one-token prefill; choose compatible context/stride')
    metadata = plan_metadata(plan, count, case['protocol'])
    layers = list(model.model.layers)
    if len(layers) != 24 or model.training or any(type(x.mlp).__name__ != 'Qwen2MLP' for x in layers):
        raise ValueError('fresh 24-layer eval model with original Qwen2MLP required')
    device = next(model.parameters()).device
    if device.type == 'cuda':
        torch.backends.cuda.matmul.allow_tf32 = False
    controller, audit, guard = None, None, None
    records, prefill_seconds, decode_seconds = [], 0., 0.
    started = time.perf_counter()
    sampling, ffn_stats = None, None
    digest = hashlib.sha256() if case['capture_scored_logits_sha256'] else None

    def sync():
        if device.type == 'cuda':
            torch.cuda.synchronize(device)

    try:
        if case['mode'] != 'sdpa':
            from .upstream_attention.attention import JointAttentionController
            controller = JointAttentionController(**{key: case[key] for key in
                ('mode', 'samples', 'burn', 'spacing', 'seed', 'budget_blocks', 'selection', 'target_fraction')},
                calibration=calibration)
            # Upstream's own install preconditions check the original model.
            controller.install(model)
        _install_ffn(model, case)
        guard = ModelGuard(model, case['ffn'])
        audit = ExecutionAudit(layers)
        with torch.inference_mode():
            for batch_rows in plan_batches(plan, case['batch']):
                tokens = torch.stack([ids[row['begin']:row['end']] for row in batch_rows]).to(device)
                prefix = batch_rows[0]['prefill_tokens']
                steps = batch_rows[0]['scored_tokens']
                cache = None
                sync()
                before = time.perf_counter()
                if prefix:
                    audit.begin('prefill')
                    output = model.model(input_ids=tokens[:, :prefix], use_cache=True)
                    cache = output.past_key_values
                    audit.end(len(batch_rows))
                    del output
                sync()
                prefill_seconds += time.perf_counter() - before
                before = time.perf_counter()
                losses = torch.zeros(len(batch_rows), dtype=torch.float64, device=device)
                for step in range(steps):
                    pos = prefix + step
                    audit.begin('decode')
                    output = model.model(input_ids=tokens[:, pos:pos + 1], past_key_values=cache, use_cache=True)
                    cache = output.past_key_values
                    audit.end(len(batch_rows))
                    logits = model.lm_head(output.last_hidden_state[:, -1]).float()
                    if digest is not None:
                        _update_logits_hash(digest, logits)
                    losses += F.cross_entropy(logits, tokens[:, pos + 1], reduction='none').double()
                sync()
                decode_seconds += time.perf_counter() - before
                for row, nll, values in zip(batch_rows, losses.tolist(), tokens.cpu().tolist()):
                    if not math.isfinite(nll):
                        raise RuntimeError('nonfinite NLL in segment ' + str(row['segment_id']))
                    records.append(dict(row, start_token=row['begin'],
                        first_target_token=row['first_target'], last_target_token=row['last_target_exclusive'] - 1,
                        nll_sum=nll, token_ids_sha256_le_int64=ids_sha256(values),
                        target_positions_sha256_le_int64=ids_sha256(target_positions(row))))
                del cache, output, logits, tokens, losses
        if controller:
            sampling = controller.stats()
            # Replace the historical attention-only scope declaration. Ising
            # draws select V directly; there is no second PV sampling stage.
            sampling['scope'] = ('all 24 single-token decode attention layers; original QKV/RoPE/cache/Wo; '
                'multi-token prefill attention is original SDPA; FFN follows joint case configuration')
            if sampling['installed_layers'] != 24:
                raise RuntimeError('attention replacement is not installed in every layer')
            for i, layer in enumerate(layers):
                state = sampling['layers'][str(i)]
                if state['decode_calls'] != audit.decode_steps or state['prefill_calls'] != audit.prefill_steps:
                    raise RuntimeError('attention controller call count differs from audit')
                if state['query_rows'] != metadata['scored_tokens'] * layer.self_attn.num_heads:
                    raise RuntimeError('not all scored target/head rows used attention replacement')
        if case['ffn'] != 'none':
            ffn_stats = {str(i): layer.mlp.diagnostics() for i, layer in enumerate(layers)}
            if any(layer.mlp.calls != audit.decode_steps + audit.prefill_steps for layer in layers):
                raise RuntimeError('FFN sampler calls differ from independent phase audit')
        if audit.query_targets != metadata['scored_tokens'] or any(
                n != metadata['scored_tokens'] for n in audit.ffn_decode_tokens_by_layer):
            raise RuntimeError('scored targets differ from actual 24-layer operator executions')
    finally:
        if audit:
            audit.close()
        if controller:
            controller.close()
        if guard:
            guard.verify()
    summary = summarize_records(records)
    return dict(test='cached_teacher_forced_joint_stratified_ffn_attention', protocol=case['protocol'],
        args=copy.deepcopy(case), **summary, source_tokens=count, examples=records,
        scoring_plan=metadata, token_ids_sha256_le_int64=ids_sha256(ids.tolist()),
        attention_layers=24, ffn_layers=24, ffn=case['ffn'], ffn_stats=ffn_stats,
        ffn_scope=('original Qwen2MLP' if case['ffn'] == 'none' else
            'all 24 FFNs, both multi-token prefill and every scored single-token decode; '
            'fixed historical W8; shared-64 A8 stratified input and post-SwiGLU streams; '
            'continuous FP32 SiLU(g)*u; BF16 interface'),
        parameter_guard='parameter and six immutable FFN weight-buffer identity/data_ptr/version; mutable diagnostics excluded',
        input_provenance=case.get('input_provenance'), sampling_stats=sampling,
        scored_logits_sha256=digest.hexdigest() if digest is not None else None,
        logits_hash_protocol='FP32 little-endian C-order bytes plus ndim/shape per decode step, execution order' if digest else None,
        execution_audit=dict(decode_calls_per_layer=audit.decode_by_layer,
            prefill_calls_per_layer=audit.prefill_by_layer, scored_query_tokens=audit.query_targets,
            ffn_decode_calls_per_layer=audit.ffn_decode_by_layer,
            ffn_prefill_calls_per_layer=audit.ffn_prefill_by_layer,
            ffn_decode_tokens_per_layer=audit.ffn_decode_tokens_by_layer,
            ffn_prefill_tokens_per_layer=audit.ffn_prefill_tokens_by_layer,
            every_scored_target_executed_all_24_layers=True,
            every_scored_target_executed_all_24_ffns=True),
        attention_sampling=('finite-time hard-constraint CTMC Ising chain; sampled indices directly select and average V; no second PV draw'
            if case['mode'] == 'screen_ising' else case['mode']),
        rng_scope='FFN input/product 700001/700002+1000*seed+7*layer; selector 2100+10000*seed+layer; attention sampler 5100+10000*seed+layer; independent generators',
        precision='original model/cache/output dtype; FP32 FFN arithmetic, logits/cross_entropy; FP64 NLL accumulation',
        prefill_attention='original multi-token SDPA', prefill_seconds=prefill_seconds,
        decode_seconds=decode_seconds, elapsed_seconds=time.perf_counter() - started,
        training=False, physical_PPA=None,
        limitations=['suffix protocol scores selected suffixes and must not be called full WT2 PPL',
            'full cached every-target protocol differs from vectorized BF16 sliding-window environment anchor',
            'multi-token prefill attention is accurate SDPA; stochastic FFNs still run during prefill',
            'fixed batch shapes and segment order required for paired random-stream comparisons',
            'finite CTMC process time and GPU reference elapsed time are not physical ASIC cycles',
            'stratified FFN draws enforce interval coverage and are not unconstrained IID'])
