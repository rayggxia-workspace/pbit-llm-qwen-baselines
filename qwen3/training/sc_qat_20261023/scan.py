"""Generate/check a training-design manifest. Does not train or submit jobs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODES = {
    "D": ("dynamic", "dynamic"),
    "F": ("calibrated_static", "calibrated_static"),
    "L": ("learned_static", "learned_static"),
    "H": ("calibrated_static", "dynamic"),
}


def build():
    shared = {
        "status": "planned_not_run", "train_seed": 20261023,
        "inference_seeds": [0, 1, 2], "supervised_tokens": 200_000_000,
        "train_scope": "full_model", "attention_algorithm": "original_exact",
        "weight_bits": 8, "weight_tile": [64, 64],
        "activation_probability_bits": 8, "input_group": 64, "rng_sharing": 64,
        "bins_x": 4, "bins_z": 4, "gap_log2_x": 2, "gap_log2_z": 2,
        "gate_up_share_x_draw": True, "z_independent_draw": True,
        "full_one_bypass": True, "probability_denominator": 256,
    }
    cases = []
    for label, (x, z) in MODES.items():
        for t in (8, 16, 32, 64):
            case = copy.deepcopy(shared)
            case.update(id=f"A_{label}_B4_d2_T{t}", kind="sampled_sc",
                        scale_x=x, scale_z=z, samples_x=t, samples_z=t,
                        strata_x=t, strata_z=t, rng_rule="random_stratified",
                        freeze_scale_at_fraction=0.8 if label == "L" else None)
            cases.append(case)
    for label in ("bf16", "w8_only", "a8_encoded_mean"):
        case = dict(id="A_control_" + label, kind=label, status="planned_not_run",
                    supervised_tokens=200_000_000, train_seed=20261023,
                    train_scope="full_model", attention_algorithm="original_exact",
                    inference_seeds=[0], weight_bits=16 if label == "bf16" else 8,
                    samples_x=0, samples_z=0, strata_x=0, strata_z=0,
                    rng_rule="none")
        if label == "a8_encoded_mean":
            case.update(scale_x="calibrated_static", scale_z="calibrated_static",
                        bins_x=4, bins_z=4, gap_log2_x=2, gap_log2_z=2,
                        input_group=64, activation_probability_bits=8,
                        full_one_bypass=True, probability_denominator=256)
        cases.append(case)
    return {
        "schema": "sc_qat_design_v1", "created_date": "2026-10-23",
        "issue": 159, "owner": "jieruiz", "launch_ready": False,
        "model": {"id": "Qwen/Qwen3-4B", "revision": None,
                  "teacher_id": "Qwen/Qwen3-4B", "teacher_frozen": True,
                  "layers": 36, "hidden": 2560, "ffn_width": 9728,
                  "weight_sha_manifest": None, "chat_template_sha256": None},
        "not_execution_config": True,
        "required_before_launch": ["pinned_model_revision_and_artifact_sha",
            "licensed_train_calibration_validation_data_manifest",
            "trainable_ffn_forward_and_gradient_validation", "legal_scale_exponent_bounds_from_calibration",
            "H200_Slurm_partition_personal_root_and_environment_lock",
            "non_Base_BF16_reference"],
        "references": {"pr147": "357db5884726a66d988d75f92447ff8ecf8698e6",
                       "pr153": "c28549b7d19ad3fc1f0b8e961ac5c61ca4ddbfcc",
                       "numbers_are_not_target_model_baselines": True},
        "training_defaults": {
            "optimizer": "AdamW", "lr_ffn": 1e-5, "lr_other": 2.5e-6,
            "lr_scale": 1e-4, "scale_weight_decay": 0.0,
            "betas": [0.9, 0.95], "weight_decay": 0.01, "gradient_clip": 1.0,
            "lr_warmup_fraction": 0.03, "lr_schedule": "cosine",
            "loss": "CE + lambda_KD * temperature^2 * KL(teacher||student)",
            "lambda_KD": 0.5, "temperature": 1.0,
            "sequence_length": 4096, "target_supervised_tokens_per_update": 131072,
            "data_token_mix": {"general_text_code_multilingual": 0.4,
                               "non_thinking_instruction": 0.3, "thinking_instruction": 0.3},
            "instruction_loss_mask": "assistant_targets_only_including_current_reasoning",
            "teacher_and_student_identical_tokens_and_masks": True,
            "sampled_curriculum": [
                {"until_fraction": 0.05, "mode": "encoded_mean"},
                {"until_fraction": 0.125, "mode": "sampled", "samples": 128},
                {"until_fraction": 0.20, "mode": "sampled", "samples": 64},
                {"until_fraction": 1.0, "mode": "sampled", "samples": "target"}],
            "recompute_same_random_keys": True,
            "calibration_tokens": 2000000, "calibration_holdout_tokens": 1000000,
            "calibration_top_scale": "max_abs_ceil_power_of_two_no_headroom",
            "calibration_split": "TRAIN_only_x_z_separate_W8_only_and_dynamic_student_paths",
            "calibration_observer_disabled_on_holdout_and_test": True,
            "scale_exponent_bounds": None,
            "initial_ffn_numeric_backend": "PR147_FP32_oracle_BF16_boundary",
        },
        "stage_A_cases": cases,
        "stage_B_template": {
            "status": "await_validation_selection", "parent_selection_split": "validation_not_test",
            "parents": ["best_dynamic", "best_fully_static_F_or_L"],
            "bins_x_equal_z": [2, 4, 8], "gap_log2_x_equal_z": [1, 2, 3],
            "samples": "inherit_exact_parent_T", "supervised_tokens": 200000000,
            "max_cases": 18, "reuse_only_identical_configuration_and_budget": True,
            "initialize_from": "original_Qwen3-4B_not_stage_A_checkpoint",
            "parent_checkpoint_sha_is_selection_evidence_only": True,
        },
        "stage_C_options": {
            "status": "not_expanded", "unequal_samples_x_z": [[8, 16], [16, 32], [32, 64]],
            "extra_z_bins": 8, "static_percentiles": [99.9, 99.99, 99.999],
            "iid_matched_training": {"finalist_structures": 2, "strata": 1,
                                     "samples": [16, 32, 64]},
            "do_not_change_multiple_knobs_at_once": True,
        },
        "stage_D": {"finalists": [2, 4], "tokens_initial": 2000000000,
                    "tokens_if_learning_continues": 5000000000,
                    "training_seeds_for_final_selected_designs": [0, 1, 2],
                    "inference_seeds": [0, 1, 2], "evaluate_samples": [8, 16, 32, 64, 128],
                    "final_context_token_mix": {"4096": 0.5, "8192": 0.3, "16384": 0.2}},
        "evaluation": {"full_wt2": {"window": 2048, "stride": 1024},
                       "tasks": ["piqa", "arc_easy", "arc_challenge", "hellaswag", "winogrande",
                                 "ifeval", "gsm8k_or_math500", "representative_code_task"],
                       "thinking_modes_separate": True, "generation_rng_separate_from_ffn_rng": True,
                       "coverage": "all_36_FFN_layers_prefill_and_decode",
                       "goals_not_measured": {"relative_ppl_increase_max": 0.01,
                                              "mean_task_accuracy_drop_percentage_points": 1.0}},
    }


def check(data):
    assert data == build(), "Manifest differs from reviewed design generator"
    assert data["model"]["id"] == data["model"]["teacher_id"] == "Qwen/Qwen3-4B"
    assert not data["launch_ready"] and data["not_execution_config"]
    cases = data["stage_A_cases"]
    assert len(cases) == len({x["id"] for x in cases}) == 19
    sc = [x for x in cases if x["kind"] == "sampled_sc"]
    assert len(sc) == 16
    for x in sc:
        assert x["samples_x"] == x["samples_z"] == x["strata_x"] == x["strata_z"]
        assert 256 % x["strata_x"] == 0
        assert x["weight_bits"] == x["activation_probability_bits"] == 8
        assert x["gate_up_share_x_draw"] and x["z_independent_draw"] and x["full_one_bypass"]
        assert x["rng_sharing"] == x["input_group"] == 64
    assert sum(data["training_defaults"]["data_token_mix"].values()) == 1.0
    return {"design_manifest_pass": True, "sampled_cases": 16, "training_controls": 3,
            "stage_A_total_planned_supervised_tokens": sum(x["supervised_tokens"] for x in cases),
            "all_status_planned": all(x["status"] == "planned_not_run" for x in cases),
            "training_or_GPU_tests_run": False, "launch_ready": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--require-launch-ready", action="store_true")
    args = parser.parse_args()
    path = HERE / "SCAN_MANIFEST.json"
    if args.write:
        path.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode())
    data = json.loads(path.read_bytes())
    result = check(data)
    result["manifest_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.require_launch_ready:
        raise SystemExit("Design only; trainer, model revision, data and Slurm binding are not ready.")


if __name__ == "__main__":
    main()
