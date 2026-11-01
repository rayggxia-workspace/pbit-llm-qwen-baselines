"""Finite DMA resource presets; real DRAMSys limits remain in force."""
DMA_PROFILES={
    'legacy':dict(issue=8,credit=64,response_bytes=8192,return_banks=128,bridge_gap_ps=None,bridge_lanes=None),
    'wide16':dict(issue=16,credit=128,response_bytes=16384,return_banks=256,bridge_gap_ps=0,bridge_lanes=8),
    'wide24':dict(issue=24,credit=256,response_bytes=32768,return_banks=512,bridge_gap_ps=0,bridge_lanes=8),
}

def dma_config(profile,**overrides):
    if profile not in DMA_PROFILES:raise ValueError('unknown DMA profile')
    d=dict(DMA_PROFILES[profile])
    for key,value in overrides.items():
        if key not in d:raise ValueError('unknown DMA override')
        if value is not None:d[key]=value
    if any(d[k]<=0 for k in ['issue','credit','response_bytes','return_banks']):raise ValueError('positive finite DMA resources required')
    if d['response_bytes']%64 or d['return_banks']>512:raise ValueError('DMA storage alignment or physical banks')
    if d['bridge_gap_ps'] is not None and d['bridge_gap_ps']<0:raise ValueError('negative request gap')
    if d['bridge_lanes'] not in (None,1,8):raise ValueError('one or eight native DMA ports required')
    return d
