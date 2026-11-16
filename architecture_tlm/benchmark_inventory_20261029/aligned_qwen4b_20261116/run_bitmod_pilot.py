"""Run the pinned BitMoD author's matrix-cycle model on the frozen Qwen shape."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


COMMIT = "e445a5f31100a5057b4c5c4373da223ce95f1c3b"
MODEL_INDEX = Path("architecture_tlm/process_28nm/cross_models_20261110/MODELS.json")
BLOBS = {
    "bitmod_sim/accelerator.py": "4988f7c5833cc06472f70a587d99f521be4ff744",
    "bitmod_sim/pe_array.py": "61e8c0e0aebbd1a9159c8f8164f78341ebb3c1e9",
    "bitmod_sim/test_bitmod.py": "d70a723f038c6837b624bf3bfbf7be9bd207e1d2",
    "bitmod_sim/mem/mem_instance.py": "0089286e5e904d232e368d9531a9d3c8efea6915",
    "bitmod_sim/mem/cacti_simulation.py": "49a123cade6c9e025a8cfd98fc5a32c1126a6297",
    "bitmod_sim/mem/cacti_config.py": "87abafee4016e34f92770441a1f1d8502181589b",
    "bitmod_sim/mem/__init__.py": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
    "LICENSE": "1f546f870c2763d73071e8ec049e6c64164db0f5"
}


def verify_author_files(root):
    for file, expected in BLOBS.items():
        data = (root / file).read_bytes()
        git_blob = f"blob {len(data)}\0".encode("ascii") + data
        if hashlib.sha1(git_blob).hexdigest() != expected:
            raise ValueError(f"BitMoD blob mismatch: {file}")


def qwen_workload(shape, context):
    hidden, intermediate = shape["hidden"], shape["ffn"]
    q_heads, kv_heads, head_dim = shape["q_heads"], shape["kv_heads"], shape["head_dim"]
    heads_per_group = q_heads // kv_heads
    q_width, kv_width = q_heads * head_dim, kv_heads * head_dim
    for layer in range(shape["layers"]):
        prefix = f"model.layers.{layer}."
        yield prefix + "q_proj", "projection", 1, 1, q_width, hidden
        yield prefix + "k_proj", "projection", 1, 1, kv_width, hidden
        yield prefix + "v_proj", "projection", 1, 1, kv_width, hidden
        yield prefix + "attn_qk", "qk", kv_heads, heads_per_group, context, head_dim
        yield prefix + "attn_v", "pv", kv_heads, heads_per_group, head_dim, context
        yield prefix + "o_proj", "projection", 1, 1, hidden, q_width
        yield prefix + "gate_proj", "ffn", 1, 1, intermediate, hidden
        yield prefix + "up_proj", "ffn", 1, 1, intermediate, hidden
        yield prefix + "down_proj", "ffn", 1, 1, hidden, intermediate
    yield "lm_head", "head", 1, 1, shape["vocab"], hidden


def run(artifact, source, context):
    verify_author_files(artifact)
    sys.path.insert(0, str((artifact / "bitmod_sim").resolve()))
    from accelerator import Accelerator

    tasks = list(qwen_workload(source["shape"], context))

    class BitMoDQwen(Accelerator):
        def _init_model_profiler(self, model_name, cxt_len, is_generation):
            self.weight_dim = {}
            self.input_dim = {}
            self.output_dim = {}
            self.layer_name_list = []
            for name, _, groups, tokens, out_dims, reduction in tasks:
                self.layer_name_list.append(name)
                self.weight_dim[name] = [groups, out_dims, reduction]
                self.input_dim[name] = [groups, tokens, reduction]
                self.output_dim[name] = [groups, tokens, out_dims]

    outputs = {}
    for label, weight_bits in (("author_generation_6bit", 6.0625), ("author_generation_3bit", 3.0625)):
        model = BitMoDQwen(
            model_name=source["model_id"], i_prec=16, kv_prec=8,
            w_prec=weight_bits, batch_size=1, is_bit_serial=True,
            pe_dp_size=4, pe_energy=0.56, pe_area=1507.7,
            pe_array_dim=[64, 16], init_mem=False, cxt_len=context, is_generation=True,
        )
        model._calc_compute_cycle()
        measured = model._layer_cycle_compute
        by_stage = {group: {"operators": 0, "macs": 0, "array_cycles": 0}
                    for group in ("projection", "qk", "pv", "ffn", "head")}
        if set(measured) != {task[0] for task in tasks}:
            raise ValueError("Author tool did not cover the full matrix workload")
        for name, stage, groups, tokens, out_dims, reduction in tasks:
            count = by_stage[stage]
            count["operators"] += 1
            count["macs"] += groups * tokens * out_dims * reduction
            count["array_cycles"] += int(measured[name])
        outputs[label] = {
            "weight_bits_in_author_config": weight_bits,
            "total_matrix_array_cycles": sum(v["array_cycles"] for v in by_stage.values()),
            "by_stage": by_stage,
        }
    return {
        "candidate": "BitMoD",
        "scope": "matrix_array",
        "run_status": "component_only",
        "description": "pinned author model with matrix-array cycle counts",
        "implementation_commit": COMMIT,
        "model_id": source["model_id"],
        "model_revision": source["revision"],
        "model_config_sha256": source["config_sha256"],
        "batch": 1,
        "context_tokens": context,
        "matrix_ops": len(tasks),
        "matrix_macs": sum(g*t*m*k for _,_,g,t,m,k in tasks),
        "runs": outputs,
        "excluded": [
            "native LPDDR and all memory stalls", "vector/nonlinear timing and activity",
            "mapped 28 nm PPA", "model weights and numeric quality",
        ],
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--artifact", required=True, type=Path)
    cli.add_argument("--workspace", default=Path.cwd(), type=Path)
    cli.add_argument("--out", required=True, type=Path)
    args = cli.parse_args()
    src = json.loads((args.workspace / MODEL_INDEX).read_bytes())["models"]["qwen3_4b"]
    target = json.loads(Path(__file__).with_name("TARGET.json").read_bytes())
    if (src["model_id"], src["revision"], src["config_sha256"]) != (
        target["model_id"], target["model_revision"], target["model_config_sha256"],
    ):
        raise ValueError("Qwen source differs from the comparison target")
    if (src["shape"]["layers"], src["shape"]["vocab"]) != (
        target["decoder_layers"], target["head_vocabulary"],
    ):
        raise ValueError("Qwen decoder scope differs from the comparison target")
    result = run(args.artifact, src, target["cache_tokens"])
    args.out.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    for mode, record in result["runs"].items():
        print(mode, record["total_matrix_array_cycles"], "matrix-array cycles")


if __name__ == "__main__":
    main()
