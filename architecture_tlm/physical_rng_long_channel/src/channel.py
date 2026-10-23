"""Same 2-MOS source + old 15-MOS comparator, no new ideal readout."""
import math
import re
import lowpower as lp
import zero_core as z


def candidate(c,b):
    return next(v for v in b['candidates'] if v['name']==c['circuit'])


def validate(c,b):
    z.validate(b)
    assert c['protocol']=='long_channel_v1'
    assert c['operating_mode']=='CORE_AND_COMPARATOR_ALWAYS_ON_SINGLE_CHANNEL'
    assert c['circuit']=='buffers_x2'
    assert c['noisescale']==1 and c['noisefmax_Hz']==1e8 and c['maxstep_s']==2.5e-9
    assert c['sample_interval_s']==1e-4 and c['long_strobe_s']==1e-5
    assert c['long_effective_s']==1 and c['extension_effective_s']==4
    assert c['long_warmup_s']==.02 and c['noise_minima_Hz']==[10,500]
    assert c['calibration_warmup_s']+c['calibration_effective_s']>=.1
    assert c['calibration_bisections']==4 and c['calibration_half_width_V']==.004
    seeds=sum([c[k] for k in ['calibration_seeds','pilot_seeds','lowfreq_check_seeds','validation_seeds','extension_seeds']],[])+[c['probe_seed']]
    assert len(set(seeds))==len(seeds) and all(isinstance(s,int) and s>0 for s in seeds)
    historical={17,29,43,401,503,607,809,907,1009,1201,1303,1409,1601,1709,1801,2203,2309,2411}
    assert not historical.intersection(seeds)
    assert c['logic_low_fraction']==.2 and c['logic_high_fraction']==.8
    assert c['lag_samples']==[1,2,5,10,20,50]
    return candidate(c,b)


def transient_parameters(stop,discard,strobe,fmin=500,fmax=1e8,maxstep=2.5e-9,seed=1):
    values=(stop,strobe,fmin,fmax,maxstep)
    if not all(math.isfinite(v) and v>0 for v in values):raise ValueError('Positive finite time/frequency required')
    if not 0<=discard<stop or fmin>=fmax:raise ValueError('Invalid record window/noise band')
    if stop+1e-12<1./fmin:raise ValueError('Spectre requires stop >= 1/noisefmin; do not silently change fmin')
    if abs(stop/strobe-round(stop/strobe))>1e-6:raise ValueError('Stop must be on strobe grid')
    return dict(stop_s=stop,discard_s=discard,strobe_s=strobe,noisefmin_Hz=fmin,
                noisefmax_Hz=fmax,maxstep_s=maxstep,seed=seed)


def noise_deck(model,b,v,reference,q,audit='all'):
    transient_parameters(q['stop_s'],q['discard_s'],q['strobe_s'],q['noisefmin_Hz'],q['noisefmax_Hz'],q['maxstep_s'],q['seed'])
    s=z.old.header(model,b).replace('gmin=1e-14','gmin=1e-15')+z.core(b)+lp.comparator(b,v,'screen')
    s+='VREF (ref 0) vsource dc={:.16g}\n'.format(reference)
    s+='// Always-powered source AND comparator. No gating, mux, latch, ADC or ideal amplifier.\n'
    s+='save out bit'+(' sense' if audit!='all' else '')+'\n'
    mos=re.findall(r'^(X\w+)\s+\(',s,re.M)
    core=['XN','XP'];cmp=[n for n in mos if n not in core]
    if len(core)!=2 or len(cmp)!=15:raise ValueError('Unexpected transistor count')
    off={'all':[], 'core_only':cmp, 'comparator_only':core,'none':mos}[audit]
    suffix=' noiseoff=[{}]'.format(' '.join(off)) if off else ''
    s+=('tranNoise tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} strobeperiod={strobe_s:.16g} '
        'strobeoutput=strobeonly method=trap noisefmin={noisefmin_Hz:.16g} '
        'noisefmax={noisefmax_Hz:.16g} noiseseed={seed} noisescale=1{suffix}\n').format(suffix=suffix,**q)
    if 'Ccore ' in s or 'noiseon_inst' in s:raise ValueError('Unexpected circuit/noise override')
    return s
