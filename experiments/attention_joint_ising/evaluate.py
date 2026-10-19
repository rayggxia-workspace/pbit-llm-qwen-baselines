"""Cached teacher-forced model PPL, with per-target 24-layer execution checks.

Torch, Transformers and the adapter are loaded lazily. No model execution occurs
on import. CLI inference requires an allocated Slurm GPU and verified inputs.
"""
import argparse
import copy
import json
import math
import re
import time
from pathlib import Path

from .scoring import (full_window_plan, ids_sha256, plan_batches, plan_metadata,
                      suffix_plan, summarize_records, target_positions)

MODES = ('sdpa', 'digital_sdpa', 'digital_exact', 'screen_exact', 'screen_iid', 'screen_ising', 'ising_only')


class ModelGuard:
    """Identity/storage/version guard; full input weight SHA comes from staging."""
    def __init__(self, model):
        self.model = model
        self.layers = list(model.model.layers)
        if len(self.layers) != 24 or model.training:
            raise ValueError('24-layer model in eval mode required')
        if any(type(layer.mlp).__name__ != 'Qwen2MLP' for layer in self.layers):
            raise ValueError('all FFNs must be original Qwen2MLP')
        self.mlp_ids = [id(layer.mlp) for layer in self.layers]
        self.parameters = self.snapshot()

    def snapshot(self):
        return {name: (id(p), p.data_ptr(), tuple(p.shape), str(p.dtype), str(p.device),
                       p.requires_grad, p._version) for name, p in self.model.named_parameters()}

    def verify(self):
        if self.mlp_ids != [id(layer.mlp) for layer in self.model.model.layers]:
            raise RuntimeError('FFN objects changed during attention evaluation')
        if self.parameters != self.snapshot():
            raise RuntimeError('parameter identity/storage/version changed during evaluation')


class ExecutionAudit:
    def __init__(self, layers):
        self.handles, self.active, self.seen = [], None, []
        self.decode_steps = self.prefill_steps = self.query_targets = 0
        self.decode_by_layer = [0] * len(layers)
        self.prefill_by_layer = [0] * len(layers)
        for index, layer in enumerate(layers):
            def hook(module, args, kwargs, index=index):
                hidden = kwargs.get('hidden_states', args[0] if args else None)
                if self.active is None or hidden is None:
                    raise RuntimeError('attention outside the declared scoring phase')
                if index in self.seen:
                    raise RuntimeError('attention layer executed twice for one query')
                self.seen.append(index)
                if self.active == 'decode':
                    if hidden.shape[1] != 1:
                        raise RuntimeError('scored target bypassed the single-token decode path')
                    self.decode_by_layer[index] += 1
                else:
                    if hidden.shape[1] <= 1:
                        raise RuntimeError('exact prefill must be multi-token; one-token prefix needs a separate protocol')
                    self.prefill_by_layer[index] += 1
            self.handles.append(layer.self_attn.register_forward_pre_hook(hook, with_kwargs=True))

    def begin(self, phase):
        if self.active is not None:
            raise RuntimeError('unfinished model execution audit')
        self.active, self.seen = phase, []

    def end(self, batch):
        if self.seen != list(range(len(self.decode_by_layer))):
            raise RuntimeError('every forward must execute all 24 attention layers in order')
        if self.active == 'decode':
            self.decode_steps += 1
            self.query_targets += batch
        else:
            self.prefill_steps += 1
        self.active = None

    def close(self):
        for handle in self.handles:
            handle.remove()


def _case(case):
    result = dict(mode='screen_ising', samples=512, burn=16., spacing=4., seed=0,
                  context=2048, decode=128, examples=32, batch=8, selection='fixed',
                  budget_blocks=8, target_fraction=.30, protocol='suffix', stride=1024)
    result.update(case)
    if result['mode'] not in MODES or result['protocol'] not in ('suffix', 'full'):
        raise ValueError('unknown mode/protocol')
    for key in ('samples', 'context', 'decode', 'examples', 'batch', 'budget_blocks', 'stride'):
        if type(result[key]) is not int or result[key] < 1:
            raise ValueError('positive integer required: ' + key)
    if type(result['seed']) is not int or result['seed'] < 0:
        raise ValueError('seed must be a nonnegative integer')
    if result['selection'] not in ('fixed', 'variable'):
        raise ValueError('unknown selection policy')
    for key in ('burn', 'spacing', 'target_fraction'):
        if not isinstance(result[key], (int, float)) or not math.isfinite(result[key]):
            raise ValueError('finite value required: ' + key)
    if result['burn'] < 0 or result['spacing'] <= 0 or not 0 < result['target_fraction'] <= 1:
        raise ValueError('invalid sampler/router parameters')
    if result['mode'].startswith('screen') and result.get('calibration_required', True) is False:
        raise ValueError('screening cannot silently disable calibration')
    return result


def evaluate_case(model, token_ids, case, calibration):
    """Evaluate one case on an already loaded model. No output files are written.

    Fixed batching/segment order and independent selector/sampler streams pair
    the sweep. Changed batch shapes are a different random-stream protocol.
    """
    import torch
    from torch.nn import functional as F

    case = _case(case)
    if case['mode'].startswith('screen') and calibration is None:
        raise ValueError('screening requires the fixed train-derived calibration')
    if token_ids.ndim == 2 and token_ids.shape[0] == 1:
        token_ids = token_ids[0]
    if token_ids.ndim != 1 or token_ids.dtype != torch.long:
        raise ValueError('token_ids must be one-dimensional int64 IDs')
    ids = token_ids.detach().cpu().contiguous()
    count = ids.numel()
    plan = (suffix_plan(count, case['context'], case['decode'], case['examples'])
            if case['protocol'] == 'suffix' else full_window_plan(count, case['context'], case['stride']))
    if any(row['prefill_tokens'] == 1 for row in plan):
        raise ValueError('this plan contains one-token exact prefill; use a compatible context/stride')
    metadata = plan_metadata(plan, count, case['protocol'])
    guard = ModelGuard(model)
    device = next(model.parameters()).device
    if device.type == 'cuda':
        torch.backends.cuda.matmul.allow_tf32 = False
    controller = None
    audit = ExecutionAudit(guard.layers)
    records, prefill_seconds, decode_seconds = [], 0., 0.
    started = time.perf_counter()
    sampling = None

    def sync():
        if device.type == 'cuda':
            torch.cuda.synchronize(device)

    try:
        if case['mode'] != 'sdpa':
            from .attention import JointAttentionController
            controller = JointAttentionController(**{key: case[key] for key in
                ('mode', 'samples', 'burn', 'spacing', 'seed', 'budget_blocks', 'selection', 'target_fraction')},
                calibration=calibration)
            controller.install(model)
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
            if sampling['installed_layers'] != 24:
                raise RuntimeError('replacement is not installed in every layer')
            for i in range(24):
                state = sampling['layers'][str(i)]
                if state['decode_calls'] != audit.decode_steps or state['prefill_calls'] != audit.prefill_steps:
                    raise RuntimeError('controller call count differs from execution audit')
                if state['query_rows'] != metadata['scored_tokens'] * 14:
                    raise RuntimeError('not all scored target/head rows used replacement')
        if audit.query_targets != metadata['scored_tokens']:
            raise RuntimeError('scored targets differ from actual 24-layer decode executions')
    finally:
        audit.close()
        if controller:
            controller.close()
        guard.verify()
    summary = summarize_records(records)
    return dict(test='cached_teacher_forced_attention_joint_ising', protocol=case['protocol'],
        args=copy.deepcopy(case), **summary, source_tokens=count, examples=records,
        scoring_plan=metadata, token_ids_sha256_le_int64=ids_sha256(ids.tolist()),
        attention_layers=24, ffn='original Qwen2MLP; original parameter objects/storage/version preserved',
        parameter_guard='identity/data_ptr/version only; full weight checksum indexed by input_provenance',
        input_provenance=case.get('input_provenance'), sampling_stats=sampling,
        execution_audit=dict(decode_calls_per_layer=audit.decode_by_layer,
            prefill_calls_per_layer=audit.prefill_by_layer, scored_query_tokens=audit.query_targets,
            every_scored_target_executed_all_24_layers=True),
        precision='original model/cache/output dtype; FP32 logits/cross_entropy; FP64 NLL accumulation',
        prefill_attention='original multi-token SDPA', prefill_seconds=prefill_seconds,
        decode_seconds=decode_seconds, elapsed_seconds=time.perf_counter() - started,
        training=False, physical_PPA=None,
        limitations=['suffix is full-model inference on selected suffixes, not full WT2',
            'full is cached matched scoring of every target, not bitwise equality to vectorized BF16 anchor',
            'router/sampler pairing assumes identical batch shapes and segment order; not batch-invariant',
            'finite hard-constraint CTMC simulation is not measured physical hardware',
            'different S/backend can change subsequent hidden states and therefore candidate masks'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for option in ('model', 'text', 'calibration', 'input-report', 'source-commit', 'output'):
        p.add_argument('--' + option, required=True)
    p.add_argument('--mode', choices=MODES, required=True)
    p.add_argument('--samples', type=int, default=512)
    p.add_argument('--burn', type=float, default=16.)
    p.add_argument('--spacing', type=float, default=4.)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--context', type=int, default=2048)
    p.add_argument('--decode', type=int, default=128)
    p.add_argument('--examples', type=int, default=32)
    p.add_argument('--batch', type=int, default=8)
    p.add_argument('--selection', choices=('fixed', 'variable'), default='fixed')
    p.add_argument('--budget-blocks', type=int, default=8)
    p.add_argument('--protocol', choices=('suffix', 'full'), default='suffix')
    p.add_argument('--stride', type=int, default=1024)
    p.add_argument('--personal-root', default='/home/Weican_Chen')
    args = p.parse_args()
    from experiments.attention_e01.capture import (QWEN_SOURCE_SHA256, TEST_IDS_SHA256,
        TEST_IDS_TOKENS, TRANSFORMERS_VERSION, require_gpu_allocation)
    from experiments.attention_e01.verify_inputs import owned_path, recheck_report, sha256_file
    require_gpu_allocation()
    if not re.fullmatch('[0-9a-f]{40}', args.source_commit):
        raise ValueError('exact source Git SHA required')
    output = owned_path(args.output, args.personal_root, exists=False)
    if output.exists():
        raise FileExistsError('refusing to overwrite an existing result')
    verification = recheck_report(args.input_report, args.model, args.text, args.personal_root)
    calibration_path = owned_path(args.calibration, args.personal_root)
    import torch
    import transformers
    import transformers.models.qwen2.modeling_qwen2 as qwen_module
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if transformers.__version__ != TRANSFORMERS_VERSION or sha256_file(qwen_module.__file__) != QWEN_SOURCE_SHA256:
        raise RuntimeError('Transformers/Qwen source differs from pinned baseline')
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError('allocated BF16 CUDA device required')
    tokenizer = AutoTokenizer.from_pretrained(verification['model'], local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(verification['model'], local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.bfloat16, attn_implementation='sdpa').cuda().eval()
    ids = tokenizer(Path(verification['text']).read_text(encoding='utf-8'),
                    add_special_tokens=False, return_tensors='pt').input_ids[0]
    if ids.numel() != TEST_IDS_TOKENS or ids_sha256(ids.tolist()) != TEST_IDS_SHA256:
        raise RuntimeError('full corpus token IDs differ from pinned WT2 reference')
    outer = torch.load(calibration_path, map_location='cpu', weights_only=True)
    calibration = outer if 'parameter' in outer else outer[f'{args.context}_0.3_max4']
    case = {key: getattr(args, key) for key in ('mode', 'samples', 'burn', 'spacing', 'seed',
        'context', 'decode', 'examples', 'batch', 'selection', 'budget_blocks', 'protocol', 'stride')}
    case['input_provenance'] = dict(verification, input_report_sha256=sha256_file(args.input_report),
        calibration_sha256=sha256_file(calibration_path), calibration_path=str(calibration_path))
    result = evaluate_case(model, ids, case, calibration)
    result['source_commit'] = args.source_commit
    result['environment'] = dict(torch=torch.__version__, transformers=transformers.__version__,
        GPU=torch.cuda.get_device_name(), Slurm_job_id=__import__('os').environ['SLURM_JOB_ID'])
    result['source_sha256'] = {path.name: sha256_file(path) for path in Path(__file__).parent.glob('*.py')}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('perplexity', 'scored_tokens', 'protocol')}))


if __name__ == '__main__':
    main()
