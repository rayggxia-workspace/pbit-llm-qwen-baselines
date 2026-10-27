"""Same 500MHz/32 arrays/SRAM/HBM/streams; only three scheduling switches."""
from architecture_tlm.clock500_resource_20261026.profiles import configuration as original
def configuration(case,bridge,output):
    c,m=original(case,bridge,output)
    c['digital_shared_prefill']=case.get('digital_prefill',False)
    c['local_pipeline']['cross_window_program']=case.get('cross_window_program',False)
    c['scheduling_v2']=dict(calendar=case.get('calendar',False),digital_prefill=c['digital_shared_prefill'],cross_window_program=c['local_pipeline']['cross_window_program'])
    c['trace_event_limit']=120
    return c,m
