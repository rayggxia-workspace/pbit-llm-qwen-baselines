"""CPU integration test against the ACTUAL SDPA inputs; no 7B weights/GPU.

Run with the inspected Transformers 4.45.2 environment:
python architecture_tlm/llama7b/test_capture_trace.py
"""
import importlib.util
from pathlib import Path
from unittest.mock import patch


def run_test(capture):
    import torch
    import transformers
    from transformers import LlamaConfig, LlamaForCausalLM
    from transformers.cache_utils import DynamicCache
    from transformers.models.llama.modeling_llama import apply_rotary_pos_emb

    if transformers.__version__ != "4.45.2":
        raise RuntimeError("Test requires inspected Transformers 4.45.2")
    torch.manual_seed(7)
    config = LlamaConfig(vocab_size=64, hidden_size=32, intermediate_size=64,
                         num_hidden_layers=2, num_attention_heads=4,
                         num_key_value_heads=4, max_position_embeddings=16,
                         attention_dropout=0.0)
    config._attn_implementation = "sdpa"
    model = LlamaForCausalLM(config).to(dtype=torch.bfloat16).eval()
    ids = torch.randint(0, 64, (1, 9))

    def forward(cache, collector=None):
        if collector is not None:
            collector.token = None
        state = model.model(ids[:, :7], past_key_values=cache, use_cache=True)
        cache = state.past_key_values
        outputs = []
        for token in range(2):
            if collector is not None:
                collector.token = token
            state = model.model(ids[:, 7+token:8+token], past_key_values=cache, use_cache=True)
            cache = state.past_key_values
            outputs.append(model.lm_head(state.last_hidden_state[:, -1]))
        return outputs

    Collector, CaptureCache = capture.make_capture_classes(torch, DynamicCache, apply_rotary_pos_emb)
    collector = Collector(2, 4)
    actual_sdpa_rows = []
    original_sdpa = torch.nn.functional.scaled_dot_product_attention

    def observed_sdpa(query, key, value, *args, **kwargs):
        if query.shape[-2] == 1:
            # Independent oracle: original attention's ACTUAL post-RoPE Q/K,
            # rather than reconstructing them through the capture mechanism.
            actual_sdpa_rows.extend(((query.float() @ key.float().transpose(-1, -2))
                                     / query.shape[-1]**0.5)[0, :, 0].cpu().tolist())
        return original_sdpa(query, key, value, *args, **kwargs)

    with torch.inference_mode():
        baseline = forward(DynamicCache())
        with collector.installed(model), patch("torch.nn.functional.scaled_dot_product_attention", observed_sdpa):
            observed = forward(CaptureCache(collector), collector)
    assert len(collector.rows) == 16
    assert [len(row["logits"]) for row in collector.rows] == [8]*8+[9]*8
    assert all(torch.equal(a, b) for a, b in zip(baseline, observed)), "Capture changed model output"
    assert [row["logits"] for row in collector.rows] == actual_sdpa_rows, "Trace differs from actual SDPA Q/K"
    assert all(not block.self_attn.q_proj._forward_hooks for block in model.model.layers), "Hook leaked"
    print("PASS: BF16 CPU 2-layer/4-head/two-token capture; actual SDPA QK equality; output bitwise equality; hook cleanup")


if __name__ == "__main__":
    path = Path(__file__).with_name("capture_trace.py")
    spec = importlib.util.spec_from_file_location("capture_trace", path)
    capture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(capture)
    run_test(capture)
