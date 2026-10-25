"""Continuous real comparator followed by a 13MOS track/regenerative-hold latch."""
import math,re
import normal_circuits as nc
import zero_core as z

def validate(c):
    assert c['protocol']=='sampled_readout_v1' and c['vdd_V']==1.2 and c['reference_V']==.604745
    assert c['candidate']['name']=='lvt_i20u' and c['noisescale']==1 and c['noisefmin_Hz']==500
    assert len(set(c['numeric_seeds']+c['validation_seeds']))==6
    assert c['period_s']==1e-6 and c['read_delay_s']==5e-8
    assert 0<c['clock_edge_s']<c['dead_s']<c['read_delay_s']
    assert c['track_s']+c['read_delay_s']+2*c['dead_s']<c['period_s']
    for t in (c['period_s'],c['read_delay_s'],c['short_start_s'],c['validation_start_s']):
        assert abs(t/c['strobe_s']-round(t/c['strobe_s']))<1e-8
    assert c['validation_samples']==20000 and c['output_load_F']==5e-15

def pulse(name,node,lo,hi,delay,width,period,edge):
    return '{} ({} 0) vsource type=pulse val0={:.16g} val1={:.16g} delay={:.16g} rise={:.16g} fall={:.16g} width={:.16g} period={:.16g}\n'.format(name,node,lo,hi,delay,edge,edge,width,period)

def clocks(c):
    T,w,d,r,e=[c[k] for k in ('period_s','track_s','dead_s','read_delay_s','clock_edge_s')]
    # Closing midpoint is k*T-r, so read time k*T is exactly on the saved grid.
    delay=T-r-w-e/2;fbdelay=delay-d
    s=pulse('VTRACK','track',0,1.2,delay,w-e,T,e)
    s+=pulse('VTRACKB','trackb',1.2,0,delay,w-e,T,e)
    s+=pulse('VHOLD','hold',1.2,0,fbdelay,w+2*d-e,T,e)
    s+=pulse('VHOLDB','holdb',0,1.2,fbdelay,w+2*d-e,T,e)
    s+=pulse('VRESET','reset',1.2,0,c['reset_release_s'],100.,200.,e)
    return s

def latch(c):
    s='// Real MOS only. Ideal finite-edge two-phase clocks are external testbench stimuli.\nVL (vl 0) vsource dc=1.2\n'
    for name,nodes,model,w in [
        ('XLINN','x track bit 0','nm1p2_svt_lp',.5),('XLINP','x trackb bit vl','pm1p2_svt_lp',1.),
        ('XLFBN','x hold xi 0','nm1p2_svt_lp',.5),('XLFBP','x holdb xi vl','pm1p2_svt_lp',1.),
        ('XL1N','qb x 0 0','nm1p2_svt_lp',.5),('XL1P','qb x vl vl','pm1p2_svt_lp',1.),
        ('XL2N','xi qb 0 0','nm1p2_svt_lp',.5),('XL2P','xi qb vl vl','pm1p2_svt_lp',1.),
        ('XL3N','ob xi 0 0','nm1p2_svt_lp',.5),('XL3P','ob xi vl vl','pm1p2_svt_lp',1.),
        ('XL4N','q ob 0 0','nm1p2_svt_lp',1.),('XL4P','q ob vl vl','pm1p2_svt_lp',2.),
        ('XLRST','x reset 0 0','nm1p2_svt_lp',1.)]:
        s+=nc.mos(name,nodes,model,w,.12)
    return s+'CQ (q 0) capacitor c={:.16g}\n'.format(c['output_load_F'])+clocks(c)

def parameters(c,seed,long=False,step=None,fmax=None):
    start=c['validation_start_s'] if long else c['short_start_s']
    n=c['validation_samples'] if long else c['short_samples']
    return dict(seed=seed,start_s=start,samples=n,stop_s=start+n*c['period_s']+1e-7,
        discard_s=start,strobe_s=c['strobe_s'],maxstep_s=step or c['maxstep_s'],
        noisefmin_Hz=c['noisefmin_Hz'],noisefmax_Hz=fmax or c['noisefmax_Hz'])

def deck(model,b,c,kind,settings):
    s=z.old.header(model,b).replace('gmin=1e-14','gmin=1e-15')
    if kind=='aperture':
        up=settings['up'];level=0 if up else 1.2
        flip=5*c['period_s']-c['read_delay_s']+settings['offset_s']
        s+='VIN (out 0) vsource dc=0.6\n'
        s+=pulse('VD','bit',level,1.2-level,flip-c['clock_edge_s']/2,100.,200.,c['clock_edge_s'])
        s+='VREF (ref 0) vsource dc={:.16g}\n'.format(c['reference_V'])
    else:
        s+=z.core(b)+nc.comparator(c,c['candidate'])
        if kind=='functional':
            a=settings['overdrive_V']
            s+=pulse('VREF','ref',c['reference_V']-a,c['reference_V']+a,2e-6,1.999e-6,4e-6,1e-9)
        else:s+='VREF (ref 0) vsource dc={:.16g}\n'.format(c['reference_V'])
    s+=latch(c)
    if kind=='noise':
        p=settings['q']
        s+='save out bit q qb track\n'
        s+=('tranSample tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} strobeperiod={strobe_s:.16g} strobeoutput=strobeonly method=trap '
            'noisefmin={noisefmin_Hz:.16g} noisefmax={noisefmax_Hz:.16g} noiseseed={seed} noisescale=1\n').format(**p)
    else:
        s+='save out bit q qb track ref x xi\n'
        s+='tranSample tran stop={deterministic_stop_s:.16g} maxstep={deterministic_maxstep_s:.16g} strobeperiod={deterministic_strobe_s:.16g} strobeoutput=strobeonly method=trap\n'.format(**c)
    expected=13 if kind=='aperture' else 25
    assert len(re.findall(r'^X\w+\s+\(',s,re.M))==expected
    assert 'Ccore ' not in s and 'noiseoff' not in s
    return s
