"""Generate/check a training-design manifest. Does not train or submit jobs."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEIGHT_BITS = (4, 6, 8)
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
        "weight_tile": [64, 64],
        "activation_probability_bits": 8, "input_group": 64, "rng_sharing": 64,
        "bins_x": 4, "bins_z": 4, "gap_log2_x": 2, "gap_log2_z": 2,
        "gate_up_share_x_draw": True, "z_independent_draw": True,
        "full_one_bypass": True, "probability_denominator": 256,
    }
    cases = []
    for bits in WEIGHT_BITS:
        for label, (x, z) in MODES.items():
            for t in (8, 16, 32, 64):
                case = copy.deepcopy(shared)
                case.update(id=f"A_W{bits}_{label}_B4_d2_T{t}", kind="sampled_sc",
                            comparison_suite_weight_bits=bits, weight_bits=bits,
                            weight_code_min=-(2**(bits-1)-1), weight_code_max=2**(bits-1)-1,
                            scale_x=x, scale_z=z, samples_x=t, samples_z=t,
                            strata_x=t, strata_z=t, rng_rule="random_stratified",
                            freeze_scale_at_fraction=0.8 if label == "L" else None)
                cases.append(case)
        for label in ("bf16", "weight_only", "a8_encoded_mean"):
            case = dict(id=f"A_W{bits}_control_" + label, kind=label, status="planned_not_run",
                        comparison_suite_weight_bits=bits,
                        supervised_tokens=200_000_000, train_seed=20261023,
                        train_scope="full_model", attention_algorithm="original_exact",
                        inference_seeds=[0], weight_bits=16 if label == "bf16" else bits,
                        samples_x=0, samples_z=0, strata_x=0, strata_z=0,
                        rng_rule="none")
            if label == "bf16":
                case.update(bf16_matched_repeat=True, quantization_applicable=False)
            else:
                case.update(weight_tile=[64,64],weight_code_min=-(2**(bits-1)-1),
                            weight_code_max=2**(bits-1)-1,quantization_applicable=True)
            if label == "a8_encoded_mean":
                case.update(scale_x="calibrated_static", scale_z="calibrated_static",
                            bins_x=4, bins_z=4, gap_log2_x=2, gap_log2_z=2,
                            input_group=64, activation_probability_bits=8,
                            full_one_bypass=True, probability_denominator=256)
            cases.append(case)
    return {
        "schema": "sc_qat_design_v3_hardware_gate", "created_date": "2026-10-23",
        "weight_bits_sweep": list(WEIGHT_BITS), "workload_multiplier": 3,
        "bf16_controls_note": "Three matched repeats with identical settings; not three bit-width structures or training seeds.",
        "weight_quantization": {"symmetric_qmax": "2**(bits-1)-1", "tile": [64,64],
                                "logical_bits_distinct_from_storage_container_bits": True},
        "issue": 159, "owner": "jieruiz", "launch_ready": False,
        "model": {"id": "Qwen/Qwen3-4B", "revision": "1cfa9a7208912126459214e8b04321603b3df60c",
                  "teacher_id": "Qwen/Qwen3-4B", "teacher_frozen": True,
                  "layers": 36, "hidden": 2560, "ffn_width": 9728,
                  "weight_sha_manifest": None, "chat_template_sha256": None},
        "not_execution_config": True,
        "required_before_launch": ["hardware_forward_contract_and_sha",
            "finite_width_g_u_and_stochastic_nonlinearity_verified",
            "integer_alignment_overflow_rounding_and_stream_replay_verified",
            "pinned_model_revision_and_artifact_sha",
            "licensed_train_calibration_validation_data_manifest",
            "trainable_ffn_forward_and_gradient_validation", "legal_scale_exponent_bounds_from_calibration",
            "H200_Slurm_partition_personal_root_and_environment_lock",
            "non_Base_BF16_reference"],
        "references": {"pr147": "357db5884726a66d988d75f92447ff8ecf8698e6",
                       "pr153": "c28549b7d19ad3fc1f0b8e961ac5c61ca4ddbfcc",
                       "pr160": "989546376f2295990b7712ea553615f0b8d88cb4",
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
            "calibration_split": "TRAIN_only_x_z_separate_Wb_only_and_dynamic_student_paths_per_weight_bits",
            "calibration_observer_disabled_on_holdout_and_test": True,
            "scale_exponent_bounds": None,
            "initial_ffn_numeric_backend": "unimplemented_hardware_constrained_forward",
            "diagnostic_reference_only": "PR147_FP32_oracle_BF16_boundary",
            "hardware_contract_sha256": None,
            "hardware_forward_validated": False,
            "nonlinear_sampling_budget": None,
        },
        "stage_G2_smoke": {"total_optimizer_steps": 120, "per_weight_bits": list(WEIGHT_BITS),
                           "scale_modes": ["D", "F", "L"], "target_samples": 32,
                           "schedule": [{"steps": 20, "mode": "encoded_mean"},
                                        {"steps": 20, "samples": 128},
                                        {"steps": 20, "samples": 64},
                                        {"steps": 60, "samples": 32}],
                           "freeze_L_at_step_zero_based": 100, "does_not_replace_stage_A": True},
        "stage_A_cases": cases,
        "stage_B_template": {
            "status": "await_validation_selection", "parent_selection_split": "validation_not_test",
            "parents": ["best_dynamic", "best_fully_static_F_or_L"],
            "bins_x_equal_z": [2, 4, 8], "gap_log2_x_equal_z": [1, 2, 3],
            "samples": "inherit_exact_parent_T", "supervised_tokens": 200000000,
            "per_weight_bits": list(WEIGHT_BITS), "max_cases_per_weight_bits": 18,
            "max_cases": 54, "reuse_only_identical_configuration_and_budget": True,
            "initialize_from": "original_Qwen3-4B_not_stage_A_checkpoint",
            "parent_checkpoint_sha_is_selection_evidence_only": True,
        },
        "stage_C_options": {
            "status": "not_expanded", "per_weight_bits": list(WEIGHT_BITS),
            "unequal_samples_x_z": [[8, 16], [16, 32], [32, 64]],
            "extra_z_bins": 8, "static_percentiles": [99.9, 99.99, 99.999],
            "iid_matched_training": {"finalist_structures": 2, "strata": 1,
                                     "samples": [16, 32, 64]},
            "do_not_change_multiple_knobs_at_once": True,
        },
        "stage_D": {"finalists_per_weight_bits": [2, 4], "per_weight_bits": list(WEIGHT_BITS),
                    "tokens_initial": 2000000000,
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
    assert len(cases) == len({x["id"] for x in cases}) == 57
    sc = [x for x in cases if x["kind"] == "sampled_sc"]
    assert len(sc) == 48
    for x in sc:
        assert x["samples_x"] == x["samples_z"] == x["strata_x"] == x["strata_z"]
        assert 256 % x["strata_x"] == 0
        assert x["weight_bits"] in WEIGHT_BITS and x["activation_probability_bits"] == 8
        assert x["gate_up_share_x_draw"] and x["z_independent_draw"] and x["full_one_bypass"]
        assert x["rng_sharing"] == x["input_group"] == 64
    assert sum(data["training_defaults"]["data_token_mix"].values()) == 1.0
    for bits in WEIGHT_BITS:
        suite = [x for x in cases if x["comparison_suite_weight_bits"] == bits]
        assert len(suite) == 19
        assert sum(x["kind"] == "sampled_sc" for x in suite) == 16
        for case in suite:
            if case["kind"] == "bf16":
                assert case["weight_bits"] == 16 and not case["quantization_applicable"]
            else:
                assert case["weight_bits"] == bits
                assert case["weight_code_min"] == -(2**(bits-1)-1)
                assert case["weight_code_max"] == 2**(bits-1)-1
    normalized = []
    for bits in WEIGHT_BITS:
        suite = []
        for case in cases:
            if case["comparison_suite_weight_bits"] != bits:
                continue
            keep = {k:v for k,v in case.items() if k not in
                    ("comparison_suite_weight_bits", "weight_bits", "weight_code_min", "weight_code_max")}
            keep["id"] = keep["id"].replace(f"_W{bits}_", "_Wb_")
            suite.append(keep)
        normalized.append(suite)
    assert normalized[0] == normalized[1] == normalized[2], "Non-weight settings changed between suites"
    assert sum(x["steps"] for x in data["stage_G2_smoke"]["schedule"]) == 120
    return {"design_manifest_pass": True, "sampled_cases": 48, "training_controls": 9,
            "cases_per_weight_bits": 19, "weight_bits": list(WEIGHT_BITS),
            "non_weight_settings_identical_across_suites": True,
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
        raise SystemExit("Design only; hardware forward contract, quantized g/u, stochastic nonlinearity, trainer, model/data and Slurm binding are not ready.")


if __name__ == "__main__":
    main()
