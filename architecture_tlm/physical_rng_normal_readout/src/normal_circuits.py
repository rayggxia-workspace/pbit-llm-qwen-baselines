"""Conventional 10MOS continuous comparator, unstarved CMOS output buffers."""
import math,re
import zero_core as z

def validate(c):
    assert c['protocol']=='normal_readout_v1' and c['vdd_V']==1.2 and c['temperature_C']==25
    assert c['maxstep_s']==2.5e-9 and c['noisefmax_Hz']==1e8 and c['noisescale']==1
    seeds=sum([c[k] for k in ['numeric_seeds','calibration_seeds','validation_seeds']],[])
    assert len(seeds)==9 and len(set(seeds))==9
    assert round((c['validation_stop_s']-c['validation_discard_s'])/c['sample_interval_s'])==20000
    assert all(v['bias_A']>=1e-5 for v in c['candidates'])

def mos(name,nodes,model,w,l):
    return '{} ({}) {} w={:.16g}u l={:.16g}u nf=1 mr=1 prelayout=1\n'.format(name,nodes,model,w,l)

def comparator(c,v):
    s='// Normal current bias; no output current starvation, no behavioral gain.\n'
    s+='VDC (vdc 0) vsource dc=1.2\nIBIAS (vdc nbias) isource dc={:.16g}\n'.format(v['bias_A'])
    s+=mos('XBIAS','nbias nbias 0 0','nm1p2_svt_lp',v['tail_w_um'],.12)
    s+=mos('XTAIL','tail nbias 0 0','nm1p2_svt_lp',v['tail_w_um'],.12)
    s+=mos('XIP','mirror out tail 0',v['input_model'],v['input_w_um'],.12)
    s+=mos('XIN','sense ref tail 0',v['input_model'],v['input_w_um'],.12)
    s+=mos('XLP','mirror mirror vdc vdc','pm1p2_svt_lp',2,.18)
    s+=mos('XLM','sense mirror vdc vdc','pm1p2_svt_lp',2,.18)
    for n,node,gate,scale in [(1,'inv','sense',1),(2,'bit','inv',2)]:
        s+=mos('XB{}N'.format(n),'{} {} 0 0'.format(node,gate),'nm1p2_svt_lp',.5*scale,.12)
        s+=mos('XB{}P'.format(n),'{} {} vdc vdc'.format(node,gate),'pm1p2_svt_lp',scale,.12)
    return s+'Cbit (bit 0) capacitor c={:.16g}\n'.format(c['output_load_F'])

def q(c,seed,long=False,step=None,fmax=None):
    r=dict(stop_s=c['validation_stop_s'] if long else c['short_stop_s'],
        discard_s=c['validation_discard_s'] if long else c['short_discard_s'],strobe_s=c['strobe_s'],
        noisefmin_Hz=c['noisefmin_Hz'],noisefmax_Hz=fmax or c['noisefmax_Hz'],
        maxstep_s=step or c['maxstep_s'],seed=seed)
    if r['stop_s']+1e-12<1./r['noisefmin_Hz']:raise ValueError('Transient too short for noisefmin')
    return r

def deck(model,b,c,v,kind,ref=None,sweep=None,overdrive=.01,loaded=True,parameters=None):
    s=z.old.header(model,b).replace('gmin=1e-14','gmin=1e-15')
    s+=('VIN (out 0) vsource dc=0.6\n' if kind=='dc' or (kind=='step' and not loaded) else z.core(b))
    s+=comparator(c,v)
    if kind=='dc':
        s+='parameters vref={:.16g}\nVREF (ref 0) vsource dc=vref\n'.format(sweep[0])
        s+='save out ref bit\ndcTransfer dc param=vref start={:.16g} stop={:.16g} step={:.16g}\n'.format(*sweep)
    elif kind=='op':
        s+='VREF (ref 0) vsource dc={:.16g}\n'.format(ref)
        s+='save out ref bit sense inv tail nbias mirror VDD:p VDC:p\ndcOp dc\nopInfo info what=oppoint where=file file="oppoint.txt"\n'
    elif kind=='step':
        s+='VREF (ref 0) vsource type=pulse val0={:.16g} val1={:.16g} delay=2u rise=1n fall=1n width=1.999u period=4u\n'.format(ref-overdrive,ref+overdrive)
        s+='save out ref bit\ntranStep tran stop={step_stop_s:.16g} maxstep={step_maxstep_s:.16g} strobeperiod={step_strobe_s:.16g} strobeoutput=strobeonly method=trap\n'.format(**c)
    elif kind=='noise':
        s+='VREF (ref 0) vsource dc={:.16g}\nsave out bit\n'.format(ref)
        s+=('tranNoise tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} strobeperiod={strobe_s:.16g} strobeoutput=strobeonly '
            'method=trap noisefmin={noisefmin_Hz:.16g} noisefmax={noisefmax_Hz:.16g} noiseseed={seed} noisescale=1\n').format(**parameters)
    else:raise ValueError('Unknown deck kind')
    expected=10 if kind=='dc' or (kind=='step' and not loaded) else 12
    if len(re.findall(r'^X\w+\s+\(',s,re.M))!=expected:raise ValueError('MOS count changed')
    if 'Ccore ' in s or 'noiseoff' in s:raise ValueError('Unexpected core capacitor/noise disable')
    return s
