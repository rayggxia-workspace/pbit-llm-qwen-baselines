"""One-time, checked correction of the Issue159 design; no experiment mutation."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
D = ROOT / 'qwen3/training/sc_qat_20261023'
def write(p, s):
    p.write_bytes(s.encode('utf-8'))
def replace(p, old, new):
    s = p.read_text(encoding='utf-8')
    assert old in s, (p, old)
    write(p, s.replace(old, new))

notice = '''> **2026-10-24 硬件边界更正，优先于旧版清单。** 旧版把FP32 g/u、SiLU及乘积列为训练前向，这不符合目标电路。它现在只作高精度诊断参考。部署训练必须先落实有限位宽恢复、g/u量化、随机非线性/乘积和尺度对齐；尚未实现，不能启动原57项部署验收扫描。GPU主权重、优化器和反向可保留浮点，前向必须显式执行硬件数值约束。详见 [HARDWARE_FORWARD_AUDIT_ZH.md](HARDWARE_FORWARD_AUDIT_ZH.md)。

'''
for name in ('REMOTE_AGENT_START_HERE_ZH.md', 'TRAINING_PLAN_ZH.md'):
    p = D/name
    s = p.read_text(encoding='utf-8')
    first, rest = s.split('\n', 1)
    write(p, first+'\n\n'+notice+rest)
p = D/'REMOTE_AGENT_START_HERE_ZH.md'
replace(p, 'refs/pull/161/head:refs/remotes/origin/plan-161', 'refs/heads/task/159-hardware-forward-contract:refs/remotes/origin/hardware-plan-159')
replace(p, 'git switch --detach origin/plan-161', 'git switch --detach origin/hardware-plan-159')
replace(p, '→g/u→FP32 SiLU乘积→z独立采样→Wd', '→有限位宽g/u→已冻结契约的随机非线性/乘积→z独立采样→Wd')
replace(p, '### 3.1 不可改变的前向契约', '### 3.1 更正后的部署前向要求（硬件契约尚待实现）')
replace(p, '→ Wg_b/Wu_b → FP32 g/u → z = SiLU(g) * u', '→ Wg_b/Wu_b → 有限位宽计数/尺度对齐 → 量化g/u\n  → 按硬件响应及独立性约束采样，实现g·sigmoid(g)·u → 有限位宽z')
replace(p, '- 第一版FFN数值参考保持FP32计算、BF16边界。不要因autocast自动变为BF16 GEMM而声称严格复现旧参考；提速后端需单列验证。', '- FP32/BF16旧路径仅作oracle，不作为部署学生前向。先填写HARDWARE_CONTRACT.example.json，验证有限位宽标量参考、逐拍参考与压缩后端一致，再做短训。不能只把张量cast到BF16就宣称非线性已量化。\n- T_nonlinear、概率响应精度、流相关性和z重编码必须单列；原T_x/T_z预算不包含新增非线性采样。')
replace(p, '它与相同随机序列的逐拍线性累加在实数算术下等价，浮点归约顺序的差异需设定并记录容差。', '它仅在实数线性运算下等价。部署后端必须与相同随机序列的有限位宽逐拍参考核对，包括每个饱和、截断、移位和舍入边界；不能仅用FP32容差证明硬件等价。')
p = D/'TRAINING_PLAN_ZH.md'
replace(p, '→ 连续计算SiLU(g) × u → z', '→ 有限位宽恢复/量化g、u → 按冻结硬件契约执行随机非线性与乘积 → 有限位宽z')
replace(p, 'FFN恢复、矩阵数值参考及SiLU/乘积先保持FP32，接口BF16；非FFN部分按匹配BF16模型执行。若后续用BF16 GEMM提速，必须另做匹配性检查并标为新的数值后端。', '上述权重实数scale和旧FP32恢复仅为参考定义。部署前向须先规定scale存储格式、乘法/移位、对齐和舍入；g/u必须量化并接入目标随机非线性，不能直接调用未约束的FP32 SiLU/乘法。接口可按已有方案保留BF16。非FFN部分暂按匹配BF16参考执行，这不表示其全部内部运算已满足目标电路。')
p = D/'scan.py'
replace(p, '"schema": "sc_qat_design_v2"', '"schema": "sc_qat_design_v3_hardware_gate"')
replace(p, '"required_before_launch": ["pinned_model_revision_and_artifact_sha",', '"required_before_launch": ["hardware_forward_contract_and_sha",\n            "finite_width_g_u_and_stochastic_nonlinearity_verified",\n            "integer_alignment_overflow_rounding_and_stream_replay_verified",\n            "pinned_model_revision_and_artifact_sha",')
replace(p, '"initial_ffn_numeric_backend": "PR147_FP32_oracle_BF16_boundary",', '"initial_ffn_numeric_backend": "unimplemented_hardware_constrained_forward",\n            "diagnostic_reference_only": "PR147_FP32_oracle_BF16_boundary",\n            "hardware_contract_sha256": None,\n            "hardware_forward_validated": False,\n            "nonlinear_sampling_budget": None,')
replace(p, 'Design only; trainer, verified model artifacts, data and Slurm binding are not ready.', 'Design only; hardware forward contract, quantized g/u, stochastic nonlinearity, trainer, model/data and Slurm binding are not ready.')
for name in ('REMOTE_ENV.example.json', 'RUN_RESULT.example.json'):
    p = D/name
    v = json.loads(p.read_bytes())
    v['hardware_forward'] = dict(contract_path=None, contract_sha256=None,
        implementation_sha256=None, finite_width_replay_validation_sha256=None,
        stochastic_nonlinearity_enabled=None, nonlinear_samples=None,
        target_circuit_supported=False, oracle_only_results_must_be_labelled=True)
    write(p, json.dumps(v, ensure_ascii=False, indent=2)+'\n')
contract = dict(schema='hardware_forward_contract_template_v1', status='unresolved_not_executable',
    purpose='Required before deployment-oriented QAT; nulls are blockers, not defaults.',
    gpu_training_master_weights_and_backward_may_float=True,
    deployment_unquantized_fp32_ffn_allowed=False,
    fields={k: None for k in [
        'weight_scale_format_and_application', 'activation_exponent_bounds',
        'bin_alignment_shifts_and_rounding', 'per_bin_counter_width_and_overflow',
        'cross_tile_accumulator_width_and_overflow', 'g_fixed_format', 'u_fixed_format',
        'g_u_clipping_rounding_and_scale', 'sigmoid_input_code_gain_offset_and_clip',
        'sigmoid_transfer_law_or_lut_sha', 'sigmoid_probability_resolution',
        'nonlinear_product_stream_encoding_and_sign', 'stream_independence_and_sharing',
        'nonlinear_samples_and_rng_budget', 'nonlinear_counter_and_restore_format',
        'z_format_and_reencoding', 'down_accumulation_format', 'bf16_boundary_rounding',
        'rtl_or_independent_bittrue_reference_sha', 'forward_replay_validation_sha',
        'tlm_operations_latency_ii_and_cost_mapping']})
write(D/'HARDWARE_CONTRACT.example.json', json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
