"""Optional explicit diagnostic pass; reductions are not free hardware."""
import torch
from .core import hard_forward


@torch.no_grad()
def diagnose(module,x,key):
    _,cache=hard_forward(x,module.gate_proj.weight,module.up_proj.weight,
                         module.down_proj.weight,module,key)
    _,g,u,gq,uq,sg,su,field,h,z,_,_=cache
    return dict(elements=g.numel(),
        g_clip_fraction=float((g.abs()>sg*255/256).float().mean()),
        u_clip_fraction=float((u.abs()>su*255/256).float().mean()),
        signed8_field_saturation_fraction=float(((field==-16)|(field==15.875)).float().mean()),
        zero_event_fraction=float((z==0).float().mean()),
        mean_joint_probability=float((gq.abs()/sg*uq.abs()/su*h).mean()),
        g_rms=float(g.square().mean().sqrt()),u_rms=float(u.square().mean().sqrt()),
        mode='explicit extra diagnostic forward; not added to hardware energy estimate')

