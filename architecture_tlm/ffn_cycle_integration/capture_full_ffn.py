"""Capture one full Qwen FFN on an explicitly CPU-only Slurm allocation.

Derived weights stay in personal storage. This is a full-shape single-token
fixture, not full-model PPL, training or physical hardware evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', type=Path, required=True)
    ap.add_argument('--text', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--layer', type=int, default=0)
    ap.add_argument('--context', type=int, default=64)
    args = ap.parse_args()
    if not os.environ.get('SLURM_JOB_ID') or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('Requires explicit CPU-only Slurm allocation and hidden GPUs')
    if args.output.exists():
        raise FileExistsError(args.output)
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(int(os.environ.get('SLURM_CPUS_PER_TASK', '4')))
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').eval().to('cpu')
    if (model.config.hidden_size, model.config.intermediate_size) != (896, 4864):
        raise ValueError('Expected Qwen2.5-0.5B full shape 896/4864')
    if not 0 <= args.layer < len(model.model.layers):
        raise ValueError('Layer out of range')
    if any(t.device.type != 'cpu' for t in list(model.parameters()) + list(model.buffers())):
        raise AssertionError('Unexpected non-CPU tensor')
    ids = tokenizer(args.text.read_text(encoding='utf-8'), return_tensors='pt').input_ids[:, :args.context]
    if ids.shape[1] != args.context:
        raise ValueError('Insufficient input tokens')
    block = model.model.layers[args.layer]
    cache = {}
    def save_x(module, inputs):
        cache['x'] = inputs[0][0, -1].detach().float().clone()
    def save_residual(module, inputs):
        cache['residual'] = inputs[0][0, -1].detach().float().clone()
    def save_output(module, inputs, output):
        cache['original_bf16_mlp'] = output[0, -1].detach().float().clone()
    hooks = [block.mlp.register_forward_pre_hook(save_x),
             block.post_attention_layernorm.register_forward_pre_hook(save_residual),
             block.mlp.register_forward_hook(save_output)]
    with torch.inference_mode():
        out = model(ids, use_cache=False)
        if not torch.isfinite(out.logits).all():
            raise AssertionError('Nonfinite reference logits')
    for hook in hooks:
        hook.remove()

    def quantize(weight):
        w = weight.detach().float().contiguous()
        nr, nc = w.shape
        if nr % 64 or nc % 64:
            raise ValueError('This full-shape capture requires aligned 64x64 tiles')
        tiles = w.reshape(nr//64, 64, nc//64, 64).permute(0, 2, 1, 3)
        scales = tiles.abs().amax(dim=(2, 3)).clamp_min(1e-20) / 127.
        codes = (tiles / scales[:, :, None, None]).round().clamp(-127, 127).to(torch.int8)
        codes = codes.permute(0, 2, 1, 3).reshape(nr, nc)
        return dict(codes=codes.tolist(), scales=scales.tolist(),
                    quantization='W8 symmetric maxabs/127 per complete 64x64 tile; FP32 scale; nearest-even; no crop')

    provenance = dict(kind='real_model_full_ffn_single_token', model='Qwen/Qwen2.5-0.5B',
        model_revision='identified by source file hashes below; no unchecked revision claim',
        layer=args.layer, shape=[896,4864,896], context=args.context, seed=0,
        dtype='BF16 CPU reference inference; FP32 exported activations and W8 tile scales',
        token_ids_sha256=hashlib.sha256(ids.numpy().tobytes()).hexdigest(),
        config_sha256=digest(args.model/'config.json'), text_sha256=digest(args.text),
        model_files={p.name:digest(p) for p in sorted(args.model.glob('*.safetensors'))},
        python=platform.python_version(), torch=torch.__version__, transformers=transformers.__version__,
        device='cpu', cuda_visible=os.environ['CUDA_VISIBLE_DEVICES'], job_id=os.environ['SLURM_JOB_ID'],
        source_sha256=digest(Path(__file__)),
        scope='Full gate/up/down matrices and real residual, one token, one layer. No PPL or baseline-equivalence claim for stochastic FFN.')
    fixture = dict(provenance=provenance, ffn=dict(x=cache['x'].tolist(),
        residual=cache['residual'].tolist(), wg=quantize(block.mlp.gate_proj.weight),
        wu=quantize(block.mlp.up_proj.weight), wd=quantize(block.mlp.down_proj.weight)),
        original_bf16_mlp=cache['original_bf16_mlp'].tolist())
    args.output.mkdir(parents=True)
    path = args.output/'full_ffn.json'
    path.write_text(json.dumps(fixture, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8')
    manifest = dict(provenance=provenance, artifacts=[dict(path=path.name, bytes=path.stat().st_size, sha256=digest(path))],
                    publication='Derived weights remain in personal server storage; publish only hashes, summaries and source.')
    (args.output/'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest), flush=True)


if __name__ == '__main__':
    main()
