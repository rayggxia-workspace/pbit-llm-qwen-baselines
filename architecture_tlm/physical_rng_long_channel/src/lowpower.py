"""Current-starved comparator exploration. Python >=3.6, stdlib only.

Extropic discloses subthreshold digitization, not the transistor topology below.
Gate every candidate on DC, bias headroom and deterministic settling; preserve
rejections as results. Digital interface loading is simulated in a separate phase.
"""
import argparse
from collections import deque
from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import engine as e
import run_characterization as old
import support
from pdk_discovery import discover_model

SOURCE = Path(__file__).resolve().parent
BRANCHES = ('vbias:p','vana:p','vbuf1:p','vbuf2:p')
IO_BRANCHES = ('viols:p','viobuf:p')
R = old.require


def validate(c):
    R(c['seeds']==[17,29,43], 'Three independent noise seeds required')
    R(c['vdd_V']==1.2 and c['temperature_C']==25, 'Fixed baseline corner')
    for k in ('stop_s','discard_s','strobe_s','maxstep_s','noisefmin_Hz','noisefmax_Hz',
              'step_stop_s','step_strobe_s','step_maxstep_s','output_load_F','gate_timeout_s',
              'case_timeout_s','dc_step_V','dc_fine_step_V','min_headroom_V','audit_stop_s',
              'audit_discard_s','audit_timeout_s'):
        R(math.isfinite(c[k]) and c[k]>0,k)
    R(c['discard_s']<c['stop_s'] and c['noisefmin_Hz']<c['noisefmax_Hz'],'Trace/band')
    R(c['maxstep_s']<=.5/c['noisefmax_Hz'],'Noise bandwidth/timestep')
    R(c['local_rails_V']==[.5,.65,.8] and c['bias_currents_A']==[1e-9,3e-9,1e-8],'Exploration grid')
    R(c['step_stop_s']==.001,'Step plateaus require 1 ms')
    R(0<c['audit_discard_s']<c['audit_stop_s'],'Adaptive audit window')
    for a,b in [('stop_s','strobe_s'),('discard_s','strobe_s'),('step_stop_s','step_strobe_s')]:
        R(abs(c[a]/c[b]-round(c[a]/c[b]))<1e-6,'Nonintegral time grid')
    R(all(math.isfinite(v) and v>0 for v in c['geometry_um'].values()),'Geometry')


def variants(c):
    result=[dict(name='old_input_slim',rail_V=1.2,bias_A=1e-7,baseline=True)]
    for rail in c['local_rails_V']:
        for current in c['bias_currents_A']:
            result.append(dict(name='lp{}m_i{}n'.format(int(round(rail*1000)),int(round(current*1e9))),
                               rail_V=rail,bias_A=current,baseline=False))
    return result


def comparator(c,v,phase):
    g=dict(c['geometry_um']);g.update(v.get('geometry_um',{}));lines=[]
    def mos(name,nodes,p,w,l):
        lines.append('{} ({}) {}m1p2_svt_lp w={:.16g}u l={:.16g}u nf=1 mr=1 prelayout=1'.format(
            name,nodes,'p' if p else 'n',w,l))
    if v['baseline']:
        bc=dict(vdd_V=1.2,comparator_bias_A=1e-7,output_load_F=c['output_load_F'],
                variants={'ref':dict(input_w_um=1,input_l_um=.5,buffer_n_w_um=.25,buffer_p_w_um=.5,buffer_l_um=1)})
        lines.append(support.comparator(bc,'ref'))
    else:
        lines+=['// Local rail; no ideal gain, limiter or noiseless behavioral comparator.',
                'VDC (vdc 0) vsource dc={:.16g}'.format(v['rail_V'])]
        for name,node in [('VBIAS','vrbias'),('VANA','vana'),('VBUF1','vbuf1'),('VBUF2','vbuf2')]:
            lines.append('{} (vdc {}) vsource dc=0'.format(name,node))
        # One counted reference leg derives both mirror biases. Check compliance
        # pb-nbias so an ideal current source cannot hide missing voltage headroom.
        mos('XPBIAS','pb pb vrbias vrbias',True,g['bias_p_w'],g['bias_l'])
        lines.append('IREF (pb nbias) isource dc={:.16g}'.format(v['bias_A']))
        mos('XBIAS','nbias nbias 0 0',False,g['bias_n_w'],g['bias_l'])
        mos('XTAIL','tail nbias 0 0',False,g['bias_n_w']*v.get('tail_scale',1.),g['bias_l'])
        mos('XIP','mirror out tail 0',False,g['input_w'],g['input_l'])
        mos('XIN','sense ref tail 0',False,g['input_w'],g['input_l'])
        mos('XLP','mirror mirror vana vana',True,g['mirror_p_w'],g['mirror_p_l'])
        mos('XLM','sense mirror vana vana',True,g['mirror_p_w'],g['mirror_p_l'])
        for n,dest,gate in [(1,'inv','sense'),(2,'bit','inv')]:
            rail='vbuf'+str(n);top='head'+str(n);bottom='foot'+str(n)
            mos('XB{}PL'.format(n),'{} pb {} {}'.format(top,rail,rail),True,g['bias_p_w']*v.get('buf{}_p_scale'.format(n),1.),g['bias_l'])
            mos('XB{}P'.format(n),'{} {} {} {}'.format(dest,gate,top,rail),True,g['switch_p_w'],g['switch_l'])
            mos('XB{}N'.format(n),'{} {} {} 0'.format(dest,gate,bottom),False,g['switch_n_w'],g['switch_l'])
            mos('XB{}NL'.format(n),'{} nbias 0 0'.format(bottom),False,g['bias_n_w']*v.get('buf{}_n_scale'.format(n),1.),g['bias_l'])
        lines.append('Cbit (bit 0) capacitor c={:.16g}'.format(c['output_load_F']))
    if phase=='interface' and not v['baseline']:
        lines+=['// Conventional cross-coupled level shifter; test loading and contention.',
                'VIO (vio 0) vsource dc={:.16g}'.format(c['vdd_V']),
                'VIOLS (vio vls) vsource dc=0','VIOBUF (vio vobuf) vsource dc=0']
        mos('XLSN0','lsn bit 0 0',False,g['shifter_n_w'],g['shifter_n_l'])
        mos('XLSN1','lsp inv 0 0',False,g['shifter_n_w'],g['shifter_n_l'])
        mos('XLSP0','lsn lsp vls vls',True,g['shifter_p_w'],g['shifter_p_l'])
        mos('XLSP1','lsp lsn vls vls',True,g['shifter_p_w'],g['shifter_p_l'])
        mos('XDN','dig lsn 0 0',False,g['digital_n_w'],g['digital_l'])
        mos('XDP','dig lsn vobuf vobuf',True,g['digital_p_w'],g['digital_l'])
        lines.append('Cdigital (dig 0) capacitor c={:.16g}'.format(c['output_load_F']))
    return '\n'.join(lines)+'\n'


def has_io(v,phase):return phase=='interface' and not v['baseline']


def save(v,phase,bare=False):
    line='save out VDD:p\n'
    if bare:return line
    line+='save ref bit inv sense mirror tail nbias VDC:p VBIAS:p VANA:p VBUF1:p VBUF2:p\n'
    if not v['baseline']:line+='save pb head1 foot1 head2 foot2\n'
    if has_io(v,phase):line+='save dig lsn lsp VIO:p VIOLS:p VIOBUF:p\n'
    return line


def deck(model,c,v,phase,kind,reference=None,sweep=None,bare=False):
    s=old.header(model,c)
    if kind=='dc':s+='VIN (out 0) vsource dc=0.6\n'
    else:s+=old.core(c)
    if not bare:
        s+=comparator(c,v,phase)
        if kind=='dc':
            start,stop,step=sweep
            s+='parameters vref={:.16g}\nVREF (ref 0) vsource dc=vref\n'.format(start)
        elif kind=='step':
            s+=('VREF (ref 0) vsource type=pulse val0={:.16g} val1={:.16g} '
                'delay=100u rise=100n fall=100n width=100u period=200u\n').format(
                    reference-c['step_overdrive_V'],reference+c['step_overdrive_V'])
        else:s+='VREF (ref 0) vsource dc={:.16g}\n'.format(reference)
    saved=save(v,phase,bare)
    if kind=='dc':saved=saved.replace('save out VDD:p','save out')
    s+=saved
    if kind=='dc':
        s+='dcTransfer dc param=vref start={:.16g} stop={:.16g} step={:.16g}\n'.format(*sweep)
    elif kind=='op':
        s+='dcOp dc\nopInfo info what=oppoint where=file file="oppoint.txt"\n'
    elif kind=='step':
        s+=('tranStep tran stop={step_stop_s:.16g} maxstep={step_maxstep_s:.16g} '
            'strobeperiod={step_strobe_s:.16g} strobeoutput=strobeonly method=trap\n').format(**c)
    return s


def noise_deck(model,c,v,phase,reference,seed,bare=False):
    s=old.header(model,c)+old.core(c)
    if not bare:s+=comparator(c,v,phase)+'VREF (ref 0) vsource dc={:.16g}\n'.format(reference)
    return s+save(v,phase,bare)+('tranNoise tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} '
        'strobeperiod={strobe_s:.16g} strobeoutput=strobeonly method=trap '
        'noisefmin={noisefmin_Hz:.16g} noisefmax={noisefmax_Hz:.16g} noiseseed='+str(seed)+' noisescale=1\n').format(**c)


def device_points(path):
    """Spectre operating-point text to SI numbers, retaining every MOS field."""
    result={};units={'':1.,'m':1e-3,'u':1e-6,'n':1e-9,'p':1e-12,'f':1e-15,'a':1e-18}
    for block in path.read_text(errors='replace').split('Instance: ')[1:]:
        name=block.split()[0].split('.')[0].upper();values={}
        for field in ('ids','vgs','vds','vbs','vgd','vgb','vth','vdsat','gmoverid'):
            m=re.search(r'^\s*'+field+r'\s*=\s*([-+0-9.eE]+)(?:\s+([munpfa]?)[AV])?',block,re.M)
            if m:values[field]=float(m.group(1))*units[m.group(2) or '']
        if 'gmoverid' in values:
            values['below_threshold_at_this_point']=abs(values['vgs'])<abs(values['vth'])
            result[name]=values
    return result


def op_check(folder,c,v,phase):
    d=dict(e.read_values(folder/'raw/dcOp.dc'));points=device_points(folder/'oppoint.txt')
    # Preserve diagnostics even when the physical bias/headroom gate rejects it.
    e.write_json(folder/'device_diagnostics.json',points)
    R(.599<=d['out']<=.601 and 15e-9<=-d['vdd:p']<=18e-9,'Core DC drift')
    R(all(k in points for k in ['XIP','XIN','XLP','XLM','XTAIL','XBIAS']),'Missing MOS operating points')
    residual=-d['vdc:p']-sum(d[k] for k in BRANCHES)
    R(abs(residual)<max(1e-15,abs(d['vdc:p'])*1e-5),'DC branch accounting')
    checks=[]
    if not v['baseline']:
        R(d['pb']-d['nbias']>=c['min_bias_compliance_V'],'Ideal bias source lacks compliance')
        for name in ['XIP','XIN','XLP','XLM','XTAIL']:
            signed=points[name]['vds']*(-1 if name in ('XLP','XLM') else 1)
            checks.append(dict(device=name,signed_vds_V=signed,minimum_V=c['min_headroom_V']))
            R(signed>=c['min_headroom_V'],'Insufficient center headroom: '+name)
        for name in ['XIP','XIN','XLP','XLM','XTAIL','XBIAS','XPBIAS','XB1PL','XB1NL','XB2PL','XB2NL']:
            R(name in points,'Missing bias device: '+name)
            R(points[name]['gmoverid']>=c['min_bias_gmoverid_per_V'],'Bias device outside chosen gm/Id gate: '+name)
    for name,values in points.items():
        R(all(abs(values[k])<=1.21 for k in ('vgs','vgd','vgb','vds') if k in values),'Terminal stress: '+name)
    return dict(out_V=d['out'],comparator_dc_power_W=-v['rail_V']*d['vdc:p'],
                bias_compliance_V=None if v['baseline'] else d['pb']-d['nbias'],
                center_headroom=checks,devices=points,
                interpretation='DC-point diagnostics only; switching devices need not remain weak-inversion at all times')


def adaptive_deck(model,c,v,phase,reference):
    q=dict(c,stop_s=c['audit_stop_s'])
    return noise_deck(model,q,v,phase,reference,17).replace('strobeoutput=strobeonly','strobeoutput=all')


def adaptive_power_check(path,c,v,phase):
    """Integrate ALL adaptive points, clipping both ends of retained window.

    Includes strobe and solver points. Narrow interface-current pulses must not
    be priced using a sparse uniform sample mean. Short audits are diagnostics,
    not substitutes for the long-run operating-point energy statistics.
    """
    io=has_io(v,phase)
    sources={'vdd:p':c['vdd_V'],'vdc:p':v['rail_V']}
    if io:sources['vio:p']=c['vdd_V']
    probes={k:v['rail_V'] for k in BRANCHES}
    if io:probes.update({k:c['vdd_V'] for k in IO_BRANCHES})
    all_keys=list(sources)+list(probes)
    signals=all_keys+['out','bit']+(['dig'] if io else [])
    energy={k:0. for k in all_keys};before=None;first=None;last=None;points=0;maxdt=0.
    for row in old.rows(path,'time'):
        R(all(k in row for k in signals),'Missing adaptive trace signal')
        t=row['time'];R(math.isfinite(t),'Nonfinite time')
        if first is None:first=t
        if before is not None:
            dt=t-before['time'];R(dt>=0,'Adaptive time reversed')
            if dt==0:
                R(all(abs(row[k]-before[k])<1e-12 for k in all_keys),'Conflicting duplicate adaptive point')
            else:
                maxdt=max(maxdt,dt)
                lo=max(before['time'],c['audit_discard_s']);hi=min(t,c['audit_stop_s'])
                if hi>lo:
                    a=(lo-before['time'])/dt;b=(hi-before['time'])/dt
                    for k in energy:
                        i0=before[k]+a*(row[k]-before[k]);i1=before[k]+b*(row[k]-before[k])
                        energy[k]+=.5*(i0+i1)*(hi-lo)
        points+=1;before=row;last=t
    R(first is not None and abs(first)<1e-12 and abs(last-c['audit_stop_s'])<1e-12,'Incomplete adaptive endpoints')
    R(maxdt<=c['maxstep_s']*1.01,'Unexpected gap in adaptive power trace')
    duration=c['audit_stop_s']-c['audit_discard_s']
    powers={k:-rail*energy[k]/duration for k,rail in sources.items()}
    branch={k:rail*energy[k]/duration for k,rail in probes.items()}
    R(abs(powers['vdc:p']-sum(branch[k] for k in BRANCHES))<max(1e-15,abs(powers['vdc:p'])*1e-5),
      'Integrated comparator accounting')
    if io:R(abs(powers['vio:p']-sum(branch[k] for k in IO_BRANCHES))<max(1e-15,abs(powers['vio:p'])*1e-5),'Integrated interface accounting')
    return dict(points=points,max_saved_gap_s=maxdt,retained_duration_s=duration,
                supply_power_W=powers,branch_power_W=branch,total_power_W=sum(powers.values()),
                integrated_energy_J={k:-sources[k]*energy[k] for k in sources},
                interpretation='Trapezoid integration of adaptive ALL output; short seed17 audit, not long-run energy certification')


def check_step(path,c,v,phase):
    signals=['out','bit','inv'];io=has_io(v,phase)
    if io:signals+=['dig']
    rr=list(old.checked_trace(path,c['step_stop_s'],c['step_strobe_s'],signals))
    outputs={'bit':v['rail_V']}
    if io:outputs['dig']=c['vdd_V']
    result={}
    for output,rail in outputs.items():
        for i in range(10):
            lo,hi,high=(60+100*i)*1e-6,(90+100*i)*1e-6,i%2==0
            values=[r[output] for r in rr if lo<=r['time']<=hi]
            R(values and all(x>.9*rail if high else x<.1*rail for x in values),'Failed settled plateau: '+output)
        delays=[]
        for i in range(1,10):
            edge=(100*i+(.1 if i%2==0 else 0))*1e-6;high=i%2==0
            hits=[r['time'] for r in rr if edge<=r['time']<edge+90e-6 and
                  (r[output]>.9*rail if high else r[output]<.1*rail)]
            R(hits,'Missing step response: '+output)
            delays.append(hits[0]-edge)
        result[output]=dict(first_rail_delay_s=delays)
    return dict(outputs=result,timing_resolution_s=c['step_strobe_s'],
                interpretation='Noiseless 10mV overdrive only; not stochastic independence or settling certification')


def summarize(path,c,v,phase):
    io=has_io(v,phase);signals=['out','bit','vdd:p','vdc:p']+list(BRANCHES)
    if io:signals+=['dig','vio:p']+list(IO_BRANCHES)
    outputs={'bit':v['rail_V']}
    if io:outputs['dig']=c['vdd_V']
    lags=[1,10,50,100,500,1000]
    states={k:dict(history=deque(maxlen=max(lags)),pairs={lag:old.PairStats() for lag in lags},
                  ones=0,mid=0,transitions=0,last=None,block_ones=0,blocks=[]) for k in outputs}
    currents={k:0. for k in signals if k.endswith(':p')}
    n=0;mean=m2=0.;max_balance=0.;max_io_balance=0.;block=int(round(.0005/c['strobe_s']))
    for r in old.checked_trace(path,c['stop_s'],c['strobe_s'],signals):
        if r['time']<c['discard_s']-1e-12 or r['time']>=c['stop_s']-1e-12:continue
        n+=1;delta=r['out']-mean;mean+=delta/n;m2+=delta*(r['out']-mean)
        for k in currents:currents[k]+=r[k]
        max_balance=max(max_balance,abs(r['vdc:p']+sum(r[k] for k in BRANCHES)))
        if io:max_io_balance=max(max_io_balance,abs(r['vio:p']+sum(r[k] for k in IO_BRANCHES)))
        for k,rail in outputs.items():
            R(-.05<=r[k]<=rail+.05,'Output outside rail: '+k)
            state=states[k];b=int(r[k]>.5*rail);state['ones']+=b
            state['mid']+=int(.2*rail<r[k]<.8*rail)
            state['transitions']+=int(state['last'] is not None and b!=state['last']);state['last']=b
            for lag in lags:
                if len(state['history'])>=lag:state['pairs'][lag].add(state['history'][-lag],b)
            state['history'].append(b);state['block_ones']+=b
            if n%block==0:state['blocks'].append(state['block_ones']/float(block));state['block_ones']=0
    R(n>max(lags),'Too few samples')
    R(max_balance<1e-12 and max_io_balance<1e-12,'Instantaneous branch accounting')
    means={k:x/n for k,x in currents.items()}
    branch_power={k:v['rail_V']*means[k] for k in BRANCHES}
    core=-c['vdd_V']*means['vdd:p'];cmp=-v['rail_V']*means['vdc:p']
    interface=-c['vdd_V']*means['vio:p'] if io else 0.
    R(abs(cmp-sum(branch_power.values()))<max(1e-15,abs(cmp)*1e-5),'Average comparator accounting')
    result={}
    for k,state in states.items():
        p=state['ones']/float(n);mid=state['mid']/float(n)
        result[k]=dict(p1=p,midrail_fraction=mid,transitions=state['transitions'],
            block_probabilities=state['blocks'],
            lag_correlations={str(l*c['strobe_s']):state['pairs'][l].result() for l in lags},
            review_flags=(['NEAR_STUCK_OR_OFF_CENTER'] if p<.05 or p>.95 else [])+
                         (['EXCESS_MIDRAIL_DWELL'] if mid>.05 else []))
    return dict(samples=n,mean_out_V=mean,std_out_V=math.sqrt(m2/(n-1)),outputs=result,
        core_power_W=core,comparator_power_W=cmp,interface_power_W=interface,total_power_W=core+cmp+interface,
        power_estimator='UNIFORM_STROBE_MEAN; PROVISIONAL, MAY_MISS_NARROW_CURRENT_PULSES',
        adaptive_power_audit_case=v['name']+'_adaptive_power_seed17',
        comparator_branch_power_W=branch_power,
        interface_branch_power_W={k:c['vdd_V']*means[k] for k in IO_BRANCHES} if io else {},
        max_balance_error_A=max_balance,max_io_balance_error_A=max_io_balance,
        energy_per_read_J={str(dt):(core+cmp+interface)*dt for dt in [1e-7,1e-6,5e-6,1e-5]},
        acceptance='DESCRIPTIVE; energy per read includes correlated samples, not energy per independent bit')


class Study:
    def __init__(self,out,model,c,exe,preview,phase):
        self.out,self.model,self.c,self.exe=out,model,c,exe
        self.preview,self.phase=preview,phase
        self.records=[];self.rejected=[];self.calibrations={};self.eligible=[]

    def persist(self,status):
        e.write_json(self.out/'summary.json',dict(status=status,phase=self.phase,cases=self.records,
            rejected_candidates=self.rejected,noise_eligible=self.eligible,calibrations=self.calibrations,
            scope=self.c['scope'],physical_entropy_validated=False,
            numerical_acceptance='PENDING_OFFLINE_REVIEW',statistical_acceptance='PENDING_OFFLINE_REVIEW'))

    def run(self,name,text,suffix,check=None,setting=None,noise=False,timeout=None):
        folder=self.out/name;folder.mkdir()
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as f:f.write(text)
        if self.preview:result=dict(status='GENERATED_NOT_SIMULATED')
        else:
            result=e.run_case(self.exe,folder,[suffix],timeout or (self.c['case_timeout_s'] if noise else self.c['gate_timeout_s']))
            result['diagnostics']=support.log_diagnostics(folder/'spectre.log')
            if self.ok(result) and check:
                try:result['measurements']=check(folder,result)
                except (ValueError,KeyError,IndexError,OSError) as exc:
                    result.update(status='FAILED_OUTPUT_CHECK',check_error=str(exc))
        e.write_json(folder/'status.json',result)
        self.records.append(dict(case=name,setting=setting,**result));self.persist('IN_PROGRESS')
        print(name+': '+result['status'],flush=True)
        return result

    @staticmethod
    def ok(r):return r['status'] in ('COMPLETED_REVIEW_REQUIRED','GENERATED_NOT_SIMULATED')

    def gate_ok(self,r):return self.ok(r) and not r.get('diagnostics',{}).get('trapezoidal_ringing',False)

    def run_all(self):
        c=self.c;vs=variants(c);base=vs[0]
        def bare_check(folder,r):
            d=dict(e.read_values(folder/'raw/dcOp.dc'))
            R(.599<=d['out']<=.601 and 15e-9<=-d['vdd:p']<=18e-9,'Bare core drift')
            return dict(out_V=d['out'],core_power_W=-c['vdd_V']*d['vdd:p'])
        r=self.run('00_bare_op',deck(self.model,c,base,self.phase,'op',bare=True),'.dc',bare_check)
        if not self.gate_ok(r):return False
        for seed in c['seeds']:
            self.run('bare_noise_seed'+str(seed),noise_deck(self.model,c,base,self.phase,None,seed,True),'.tran',
                lambda f,r:old.summarize_trace(f/r['result_files']['.tran'][0],c,False),
                dict(seed=seed,bare=True),noise=True)
        for v in vs:
            trips=[];reason=None
            for tag,start,stop,step in [('forward',c['dc_low_V'],c['dc_high_V'],c['dc_step_V']),
                                       ('reverse',c['dc_high_V'],c['dc_low_V'],-c['dc_step_V'])]:
                r=self.run(v['name']+'_dc_'+tag,deck(self.model,c,v,self.phase,'dc',sweep=(start,stop,step)),'.dc',
                    lambda f,r,start=start,stop=stop,step=step:old.transfer(f/'raw/dcTransfer.dc',start,stop,step,v['rail_V']),v)
                if not self.gate_ok(r):reason='DC_'+tag.upper();break
                trips.append(c['baseline_reference_V'] if self.preview else r['measurements']['reference_trip_V'])
            if not reason and abs(trips[0]-trips[1])>c['dc_fine_step_V']:
                reason='DIRECTION_DEPENDENT_TRIP'
            if reason:self.rejected.append(dict(variant=v,reason=reason));continue
            center=sum(trips)/2;span=c['dc_fine_halfspan_V'];step=c['dc_fine_step_V']
            r=self.run(v['name']+'_dc_fine',deck(self.model,c,v,self.phase,'dc',sweep=(center-span,center+span,step)),'.dc',
                lambda f,r:old.transfer(f/'raw/dcTransfer.dc',center-span,center+span,step,v['rail_V'],False),v)
            if not self.gate_ok(r):self.rejected.append(dict(variant=v,reason='DC_FINE'));continue
            center=center if self.preview else r['measurements']['reference_trip_V']
            self.calibrations[v['name']]=dict(reference_V=center,preview_placeholder=self.preview,
                interpretation='DC only; not calibrated to p=0.5')
            r=self.run(v['name']+'_loaded_op',deck(self.model,c,v,self.phase,'op',reference=center),'.dc',
                lambda f,r:op_check(f,c,v,self.phase),v)
            if not self.gate_ok(r):self.rejected.append(dict(variant=v,reason='BIAS_OR_HEADROOM'));continue
            r=self.run(v['name']+'_reference_step',deck(self.model,c,v,self.phase,'step',reference=center),'.tran',
                lambda f,r:check_step(f/r['result_files']['.tran'][0],c,v,self.phase),v)
            if not self.gate_ok(r):self.rejected.append(dict(variant=v,reason='STEP_OR_RINGING'));continue
            self.eligible.append(v['name'])
            self.run(v['name']+'_adaptive_power_seed17',adaptive_deck(self.model,c,v,self.phase,center),'.tran',
                lambda f,r:adaptive_power_check(f/r['result_files']['.tran'][0],c,v,self.phase),
                dict(variant=v,seed=17,reference_V=center),True,timeout=c['audit_timeout_s'])
            for seed in c['seeds']:
                self.run(v['name']+'_noise_seed'+str(seed),noise_deck(self.model,c,v,self.phase,center,seed),'.tran',
                    lambda f,r:summarize(f/r['result_files']['.tran'][0],c,v,self.phase),dict(variant=v,seed=seed,reference_V=center),True)
        return True

    def finish(self,prerequisite):
        if self.preview:self.persist('GENERATED_NOT_SIMULATED');return 0
        # Candidate rejection is an expected exploration outcome, not silently
        # relabeled as a successful design. Baseline or any attempted noise failure
        # still makes the job incomplete. No candidate is automatically selected.
        noise_ok=all(self.ok(r) for r in self.records if '_noise_' in r['case'] or '_adaptive_power_' in r['case'])
        baseline_ok='old_input_slim' in self.eligible
        run_ok=all(r['status']!='FAILED' for r in self.records)
        good=prerequisite and noise_ok and baseline_ok and run_ok
        self.persist('SCREENING_COMPLETED_REVIEW_REQUIRED' if good else 'INCOMPLETE_REVIEW_REQUIRED')
        return 0 if good else 1


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--phase',choices=['screen','interface'],default='screen')
    p.add_argument('--verify',action='store_true');p.add_argument('--generate-only',action='store_true')
    p.add_argument('--out',type=Path);p.add_argument('--finalize',type=Path);p.add_argument('--pack',type=Path)
    p.add_argument('--pdk',default=os.environ.get('PBIT_PDK_ROOT',e.DEFAULT_PDK))
    a=p.parse_args();e.verify_source()
    if a.finalize:e.finalize(a.finalize.resolve());return 0
    if a.pack:support.pack_results(a.pack);return 0
    c=json.loads((SOURCE/'config.json').read_text(encoding='utf-8'));validate(c)
    if a.verify:print('Source checksums and config: PASS');return 0
    if a.out is None:p.error('--out required')
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);e.write_json(out/'config.json',c)
    _,model,discovery=discover_model(a.pdk);e.write_json(out/'pdk_discovery.json',discovery)
    if model is None:e.write_json(out/'summary.json',dict(status='BLOCKED_PDK'));return 2
    expected=json.loads((SOURCE/'local_pdk_hashes.json').read_text(encoding='utf-8'))
    hashes={'model/spectre/'+q.relative_to(model.parent).as_posix():e.digest(q) for q in model.parent.rglob('*') if q.is_file()}
    matches=all(hashes.get(k)==v for k,v in expected.items())
    e.write_json(out/'pdk_comparison.json',dict(matches_local=matches,hashes=hashes))
    if not matches:e.write_json(out/'summary.json',dict(status='BLOCKED_PDK_HASH'));return 2
    e.write_json(out/'metadata.json',dict(utc=datetime.utcnow().isoformat()+'Z',phase=a.phase,python=sys.version,
        generated_only=a.generate_only,
        job=os.environ.get('SLURM_JOB_ID'),host=os.environ.get('HOSTNAME'),model=str(model),scope=c['scope'],
        config_sha256=e.digest(SOURCE/'config.json'),source_manifest_sha256=e.digest(SOURCE/'package_manifest.json'),
        baseline_job=c['baseline_job'],baseline_archive_sha256=c['baseline_archive_sha256'],
        git_revision='N/A standalone EDA; source snapshot identified by SHA256',
        cost_boundary='core + local comparator + optional digital interface; ideal supply/reference generators excluded'))
    exe=None if a.generate_only else shutil.which(os.environ.get('SPECTRE_BIN','spectre'))
    if not a.generate_only and not exe:e.write_json(out/'summary.json',dict(status='BLOCKED_NO_SPECTRE'));return 2
    if exe:
        for label,opts in [('version',['-W']),('tran_help',['-h','tran'])]:
            with (out/(label+'.txt')).open('w') as f:subprocess.run([exe]+opts,stdout=f,stderr=subprocess.STDOUT,timeout=30)
    study=Study(out,model,c,exe,a.generate_only,a.phase)
    try:good=study.run_all()
    except Exception:
        study.persist('DRIVER_EXCEPTION; inspect retained logs');raise
    return study.finish(good)


if __name__=='__main__':sys.exit(main())
