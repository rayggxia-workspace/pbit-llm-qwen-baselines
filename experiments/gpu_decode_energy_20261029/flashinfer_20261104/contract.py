"""Dependency-free configuration checks and result conventions."""
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
