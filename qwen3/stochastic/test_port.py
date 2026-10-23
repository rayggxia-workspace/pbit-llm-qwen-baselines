"""CPU preflight and GPU native-wrapper gates, with non-square Qwen3 projection."""
import copy
import json
import os
from pathlib import Path
import tempfile
import torch
from transformers import Qwen3Config, Qwen3ForCausalLM
from .adapter import Qwen3Controller
from .scorer import evaluate_case
from .vendor.stratified_core import StratifiedFFN
from .vendor.core import quantize_int8
from .vendor.scoring import full_window_plan, target_positions


def run(device='cpu'):
    torch.manual_seed(17)
    config = Qwen3Config(vocab_size=64, hidden_size=128, intermediate_size=192,
        num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=2, head_dim=64,
        max_position_embeddings=4096, attention_dropout=0., tie_word_embeddings=True)
    config._attn_implementation = 'sdpa'
    model = Qwen3ForCausalLM(config).eval().to(device)
    # Cast only parameters: native nonpersistent RoPE remains FP32.
    if device == 'cuda':
        for p in model.parameters():
            p.data = p.data.to(torch.bfloat16)
    assert model.model.rotary_emb.inv_freq.dtype == torch.float32
    assert model.model.layers[0].self_attn.o_proj.in_features != config.hidden_size
    ids = torch.randint(0, 64, (128,))
    case = dict(mode='sdpa', ffn='none', context=16, decode=4, examples=3,
                batch=2, capture_scored_logits_sha256=True)
    native = evaluate_case(copy.deepcopy(model), ids, case, None)
    wrapped = evaluate_case(copy.deepcopy(model), ids, dict(case, mode='digital_sdpa'), None)
    assert native['scored_logits_sha256'] == wrapped['scored_logits_sha256'], 'native SDPA wrapper is not bitwise identical'
    assert native['scored_tokens'] == wrapped['scored_tokens'] == 12
    calibration = dict(parameter=[[0.] * 4] * 2, temperature=[[1.] * 4] * 2)
    replacement = evaluate_case(copy.deepcopy(model), ids,
        dict(case, mode='screen_exact', ffn='b4_t32'), calibration)
    assert all(v == 12 for v in replacement['execution_audit']['ffn_decode_tokens_per_layer'])
    assert replacement['sampling_stats']['installed_layers'] == 2
    # Lossless compact integer storage; every decoded W8 value is unchanged.
    original = model.model.layers[0].mlp
    compact = StratifiedFFN(original, policy='pot4', mode='sampled', cycles=32, strata=32)
    weights = dict(gu=torch.cat([original.gate_proj.weight, original.up_proj.weight]), down=original.down_proj.weight)
    for name, w in weights.items():
        codes, decoded, lsb = quantize_int8(w)
        assert getattr(compact, name + '_codes').dtype == torch.int8
        assert torch.equal(getattr(compact, name + '_codes').short(), codes)
        assert torch.equal(getattr(compact, name + '_decoded'), decoded)
    # Save/reload has matching buffers/parameters and tight existing tolerance.
    root = Path(os.environ['PBIT_PROJECT_ROOT']).resolve()
    assert str(root).startswith('/home/Hongjie_Zeng/projects/pbit-qwen3-stochastic-')
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        model.save_pretrained(temporary)
        loaded = Qwen3ForCausalLM.from_pretrained(temporary,
            torch_dtype=next(model.parameters()).dtype, attn_implementation='sdpa').to(device).eval()
        for before, after in [(dict(model.named_parameters()), dict(loaded.named_parameters())),
                              (dict(model.named_buffers()), dict(loaded.named_buffers()))]:
            assert before.keys() == after.keys()
            for name in before:
                a, b = before[name], after[name]
                assert (a.shape, a.dtype, a.device) == (b.shape, b.dtype, b.device)
                assert torch.equal(a, b), name
        with torch.inference_mode():
            inp = ids[:8][None].to(device)
            torch.testing.assert_close(model(inp).logits, loaded(inp).logits, atol=1e-5, rtol=1e-5)
    for length in (2, 3, 2048, 2049, 299078):
        plan = full_window_plan(length)
        assert [p for row in plan for p in target_positions(row)] == list(range(1, length))
    # Exceptions must restore owned monkeypatches and aliases.
    c = Qwen3Controller(mode='digital_sdpa').install(model)
    try:
        with torch.inference_mode():
            model(ids[:1][None].to(device), output_attentions=True)
    except ValueError:
        pass
    else:
        raise AssertionError('unsupported call was not rejected')
    finally:
        c.close()
    assert all(not hasattr(x.self_attn, '_joint_attention_owner') and not hasattr(x.self_attn, 'num_heads') for x in model.model.layers)
    return dict(status='PASS', device=device, native_wrapper_bitwise=True,
        non_square_q_projection=True, qk_norm=True, all_layer_scored_targets=12,
        compact_codes_lossless=True, save_reload=True, exact_coverage=True, exception_restore=True)


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
