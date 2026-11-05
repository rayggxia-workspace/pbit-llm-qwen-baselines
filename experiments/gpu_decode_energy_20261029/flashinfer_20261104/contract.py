"""Dependency-free configuration checks and result conventions."""
import math
BACKENDS=('sdpa_expanded','sdpa_gqa','flashinfer_cuda','flashinfer_tensor')


def validate(c):
    assert c['model']=='Qwen/Qwen3-4B'
    assert c['revision']=='1cfa9a7208912126459214e8b04321603b3df60c'
    assert c['batch']==1 and c['dtype']=='bfloat16'
    assert c['contexts']==[2048,8192]
    assert tuple(c['backends'])==BACKENDS
    assert c['q_heads']==32 and c['kv_heads']==8 and c['head_dim']==128
    assert c['logit_relative_L2_max']==.01 and c['require_same_top1']
    assert c['module_relative_L2_max']==.01
    assert c['whole_window_s']>=10 and c['module_window_s']>=5 and c['repeats']>=3
    assert c['native_steps']==256
    assert c['probe_offsets']==[0,16384,65536]
    assert c['flashinfer_version']=='0.2.5'
    return c


def guard_values(relative_l2,top1,limit=.01):
    return dict(relative_L2=relative_l2,top1_equal=bool(top1),
                threshold_relative_L2=limit,accepted=relative_l2<=limit and bool(top1))


def whole_measurement_class(whole_gate, module_gate, support_ok, finite_outputs,
                            exploratory=False):
    """Explicit exploratory timing never changes the numerical acceptance."""
    if not (module_gate and support_ok and finite_outputs):
        return 'blocked'
    if whole_gate:
        return 'accepted_numerical_control'
    return 'exploratory_numerical_gate_failed' if exploratory else 'blocked'


def flashinfer_scale(scale, head_dim):
    """Use the identical default scale without triggering FlashInfer0.2.5's bug.

    That version assigns head_dim only when sm_scale is None. Custom scales
    must never be silently replaced or simulated by BF16 rescaling of Q.
    """
    if not isinstance(head_dim, int) or head_dim <= 0:
        raise ValueError('positive integer head dimension required')
    default = 1.0 / math.sqrt(head_dim)
    if scale is not None and not math.isclose(float(scale), default, rel_tol=1e-12, abs_tol=0.0):
        raise ValueError('FlashInfer0.2.5 workaround supports the exact natural scale only')
    return None
