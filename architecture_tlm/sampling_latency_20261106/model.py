from types import MethodType
from architecture_tlm.sram1216_20261106.model import make_model as compact_model

def install_samples(model,gu_samples=8,wd_samples=32):
    if gu_samples not in range(1,257) or wd_samples not in range(1,257):
        raise ValueError('positive1..256 sample counts')
    original=model.delay
    contract=dict(GU_samples=gu_samples,NL_Wd_samples=wd_samples,clock_MHz=100,
        frame_overhead_cycles=2,GU_frame_ns=(gu_samples+2)*10,
        NL_Wd_frame_ns=(wd_samples+2)*10,
        latency_basis='existing T64 actor66cycles=1load+64sample+1readout; same pipeline per-cycle',
        timing_only=True,new_counter_PPA=False,new_model_quality=False)
    def delay(self,ns,name):
        if name=='common_GU_core':ns=contract['GU_frame_ns']
        elif name=='common_Wd_core':ns=contract['NL_Wd_frame_ns']
        yield from original(ns,name)
    model.delay=MethodType(delay,model);model.sampling_latency_contract=contract
    parent=model.run
    def run(self):
        result=parent()
        # The frozen owner actor has literal660ns bookkeeping; actual service
        # above is already variable. Correct the reported aggregate after run.
        for row in self.common_stats:
            t=gu_samples if row['mode']=='GU' else wd_samples
            row['sample_core_ns']=row['frames']*(t+2)*10
            row['core_sampling_utilization']=row['sample_core_ns']/(self.common_cores*row['elapsed_ns'])
        frames=self.kernel_active
        self.actions['GU_logical_R8_ports']=frames['GU_frames']*64*gu_samples
        self.actions['NL_logical_R8_ports']=frames['Wd_M128_frames']*192*wd_samples
        self.actions['common_R8_words']=frames['GU_frames']*gu_samples+frames['Wd_M128_frames']*3*wd_samples
        result['actions']=dict(self.actions)
        result['common_FFN']['weight_policy']='one8KiB tile write; GU%d / NL_Wd%d in-place sample cycles; no ordinary operand read per sample'%(gu_samples,wd_samples)
        result['sampling_latency_contract']=contract
        lm=sum(p['duration_ns'] for p in self.phases if p['stage']=='lm_head')
        result['decode_timing_ms']=dict(including_lm_head=self.h.now*1e-6,
            lm_head_stage=lm*1e-6,excluding_lm_head_stage=(self.h.now-lm)*1e-6)
        result['lm_head_exclusion_note']='subtract lm_head phase; keeps final norm and any lm_head prefetch already overlapped with NL_Wd; not a no-head hardware rerun'
        return result
    model.run=MethodType(run,model)
    return model

def make_model(backend,gu_samples=8,wd_samples=32,**kwargs):
    h,m=compact_model(backend,configuration='compact1216',**kwargs)
    install_samples(m,gu_samples,wd_samples)
    return h,m
