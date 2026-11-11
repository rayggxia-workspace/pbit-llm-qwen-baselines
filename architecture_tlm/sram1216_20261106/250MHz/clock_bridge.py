"""Integer-cycle ingress audit matching the parent's1e-6ns event tolerance."""
from types import MethodType
import math

def install(model):
    from architecture_tlm.unified_v6.ingress_sweep import FiniteIngress
    h=model.h
    assert h.now==0 and not h.ingress_scheduled
    # SharedMemory.run dispatches events up to1e-6ns ahead of self.now.
    # The owner prefix's1e-7ns delta check cannot be imposed on that dispatcher.
    # Check integer clock edges instead; never permit two ticks in one cycle.
    epsilon=1e-6
    h.ingress_clock_audit=dict(ticks=0,off_edge_ticks=0,min_spacing_ns=None,
        min_spacing_cycles=None,last_tick_ns=None,last_cycle=None,
        max_dispatch_offset_ns=0,dispatcher_tolerance_ns=epsilon,
        ledger='integer4ns cycles; parent event dispatcher tolerance retained')
    def wake(self):
        if not self.ingress_scheduled and any(self.ingress):
            cycle=math.floor((self.now+epsilon)/4)+1
            last=self.ingress_clock_audit['last_cycle']
            if last is not None:cycle=max(cycle,last+1)
            self.ingress_scheduled=True
            self.later(cycle*4,self._ingress_tick)
    def tick(self):
        a=self.ingress_clock_audit;cycle=round(self.now/4)
        error=abs(self.now-cycle*4)
        if error>epsilon+1e-9:
            a['off_edge_ticks']+=1
            raise AssertionError(('off4ns edge',self.now,error))
        if a['last_cycle'] is not None:
            spacing=cycle-a['last_cycle']
            assert spacing>=1,('multiple ingress services in one clock cycle',cycle)
            a['min_spacing_cycles']=spacing if a['min_spacing_cycles'] is None else min(a['min_spacing_cycles'],spacing)
            a['min_spacing_ns']=a['min_spacing_cycles']*4
        a['ticks']+=1;a['last_cycle']=cycle;a['last_tick_ns']=cycle*4
        a['max_dispatch_offset_ns']=max(a['max_dispatch_offset_ns'],error)
        return FiniteIngress._ingress_tick(self)
    h._ingress_wake=MethodType(wake,h);h._ingress_tick=MethodType(tick,h)
    model.unified_clock_contract['return_ingress_audit']='integer-cycle bridge for parent1e-6ns dispatch tolerance'
