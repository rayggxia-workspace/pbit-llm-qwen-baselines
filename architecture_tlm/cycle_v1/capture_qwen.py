"""Capture auditable cropped execution fixtures; never a full-model PPL claim.

Run only inside a GPU allocation. Model files remain read-only. The resulting
weight-bearing fixtures belong in personal artifact storage, not in Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                              separators=(',', ':'), allow_nan=False) + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True, type=Path)
    ap.add_argument('--text', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--context', type=int, default=2048)
    args = ap.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('CUDA_VISIBLE_DEVICES'):
        raise RuntimeError('An explicit Slurm GPU allocation is required')
    if args.output.exists():
        raise FileExistsError('Fresh output directory required')
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from transformers.models.qwen2.modeling_qwen2 import apply_rotary_pos_emb
    torch.set_num_threads(int(os.environ.get('SLURM_CPUS_PER_TASK', '2')))
    torch.manual_seed(0)
    if not torch.cuda.is_available():
        raise RuntimeError('Allocated CUDA device unavailable')
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, local_files_only=True, torch_dtype=torch.bfloat16,
        attn_implementation='sdpa').eval().to('cuda')
    token_ids = tokenizer(args.text.read_text(encoding='utf-8'), return_tensors='pt').input_ids[:, :args.context]
    if token_ids.shape[1] != args.context:
        raise ValueError('Input corpus does not contain requested context')
    cache = {}
    hooks = []
    layers = (0, 12, 23)
    for layer in layers:
        block = model.model.layers[layer]
        def capture_x(module, inputs, layer=layer):
            cache[(layer, 'x')] = inputs[0][0, -1].detach().float().cpu()
        hooks.append(block.mlp.register_forward_pre_hook(capture_x))
        def capture_residual(module, inputs, layer=layer):
            cache[(layer, 'residual')] = inputs[0][0, -1].detach().float().cpu()
        hooks.append(block.post_attention_layernorm.register_forward_pre_hook(capture_residual))
        for kind in ('q', 'k', 'v'):
            def capture_projection(module, inputs, output, layer=layer, kind=kind):
                cache[(layer, kind)] = output.detach().float().cpu()
            hooks.append(getattr(block.self_attn, kind + '_proj').register_forward_hook(capture_projection))
    with torch.inference_mode():
        result = model(token_ids.to('cuda'), use_cache=False)
        logits_finite = bool(torch.isfinite(result.logits).all().item())
    for hook in hooks:
        hook.remove()
    if not logits_finite:
        raise AssertionError('Reference model produced nonfinite logits')
    args.output.mkdir(parents=True)
    provenance = dict(
        kind='real_model_cropped_fixture_not_full_layer_or_PPL',
        model='Qwen/Qwen2.5-0.5B', revision='060db6499f32faf8b98477b0a26969ef7d8b9987',
        config_sha256=digest(args.model / 'config.json'), text_sha256=digest(args.text),
        token_ids_sha256=hashlib.sha256(token_ids.numpy().tobytes()).hexdigest(),
        context=args.context, seed=0, dtype='BF16 model; FP32 exported projections',
        torch=torch.__version__, transformers=transformers.__version__, python=platform.python_version(),
        cuda=torch.version.cuda, gpu=torch.cuda.get_device_name(0), job_id=os.environ['SLURM_JOB_ID'],
        source_sha256=digest(Path(__file__)), logits_finite=logits_finite,
        model_files={p.name:digest(p) for p in sorted(args.model.glob('*.safetensors'))},
        precision_note='Q/K projections captured after BF16 linear, RoPE applied in FP32 for exported fixture; not bitwise model-attention evidence')

    def quantized_crop(weight, nrows, ncols):
        # Derive each scale from the full original 64x64 tile, then crop codes.
        w = weight.detach().float().cpu()
        rows, scales = [], []
        for r in range(0, nrows, 64):
            scale_row = []
            for c in range(0, ncols, 64):
                tile = w[r:r+64, c:c+64]
                scale_row.append(float(tile.abs().max().clamp_min(1e-20) / 127.))
            scales.append(scale_row)
        for r in range(nrows):
            row = []
            for c in range(ncols):
                row.append(int(torch.clamp(torch.round(w[r, c] / scales[r//64][c//64]), -127, 127)))
            rows.append(row)
        return dict(codes=rows, scales=scales,
                    quantization='symmetric signed W8, maxabs/127 per original 64x64 tile, nearest-even; crop after scale')

    manifest = []
    for layer in layers:
        block = model.model.layers[layer]
        x = cache[(layer, 'x')]
        ffn = dict(x=x.tolist(), residual=cache[(layer, 'residual')][:16].tolist(),
                   wg=quantized_crop(block.mlp.gate_proj.weight, 70, len(x)),
                   wu=quantized_crop(block.mlp.up_proj.weight, 70, len(x)),
                   wd=quantized_crop(block.mlp.down_proj.weight, 16, 70))
        # RoPE source is the actual pinned Transformers implementation.
        d = model.config.hidden_size // model.config.num_attention_heads
        q = cache[(layer, 'q')].view(1, args.context, model.config.num_attention_heads, d).transpose(1, 2)
        k = cache[(layer, 'k')].view(1, args.context, model.config.num_key_value_heads, d).transpose(1, 2)
        v = cache[(layer, 'v')].view(1, args.context, model.config.num_key_value_heads, d).transpose(1, 2)
        positions = torch.arange(args.context).unsqueeze(0)
        with torch.inference_mode():
            inv = model.model.rotary_emb.inv_freq.detach().float().cpu()
            freqs = (inv[None, :, None] @ positions[:, None, :].float()).transpose(1, 2)
            emb = torch.cat((freqs, freqs), dim=-1)
            q, k = apply_rotary_pos_emb(q, k, emb.cos(), emb.sin())
        ids = sorted(set([0, args.context-1] + [i*(args.context-1)//127 for i in range(128)]))
        fixture = dict(provenance={**provenance, 'layer':layer,
            'ffn_crop':'full 896 input channels; 70 intermediate outputs; 16 final outputs; first 16 true post-attention residual values; omitted intermediate outputs make this a crop, not full FFN equivalence',
            'attention_crop':'last query head0, shared KV head0, 128 deterministic spread candidates; selector/QKV/RoPE timing excluded'},
            ffn=ffn, attention=dict(q=q[0,0,-1].tolist(), k=k[0,0].tolist(), v=v[0,0].tolist(), candidate_ids=ids))
        path = args.output / ('qwen_layer%d.json' % layer)
        write_json(path, fixture)
        manifest.append(dict(path=path.name, sha256=digest(path), bytes=path.stat().st_size, layer=layer))
    write_json(args.output / 'MANIFEST.json', dict(provenance=provenance, artifacts=manifest,
        publication='Fixtures contain derived model weights; keep under personal storage. Publish only source, hashes and compact execution results.'))
    print(json.dumps(dict(status='complete', output=str(args.output), artifacts=manifest)))


if __name__ == '__main__':
    main()
