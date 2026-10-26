"""Spectre 18.1 characterization. Python >=3.6, standard library only.

Candidate circuit, not a validated comparator. Gate noisy jobs on DC/pulse
checks. Reuse verified PDK discovery, Spectre invocation and hash utilities.
"""
import argparse
from collections import deque
from datetime import datetime
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import engine as e
from pdk_discovery import discover_model

SOURCE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(c):
    for key in ('vdd_V', 'comparator_bias_A', 'output_load_F', 'stop_s',
                'strobe_s', 'maxstep_s', 'noisefmin_Hz', 'noisefmax_Hz',
                'case_timeout_s', 'gate_timeout_s', 'cextra_F'):
        require(math.isfinite(c[key]) and c[key] > 0, key)
    require(c['seeds'] == [17, 29, 43], 'Three specified noise seeds required')
    require(c['reference_offsets_V'] == [-.012, -.006, 0, .006, .012], 'Unexpected sweep')
    require(0 < c['discard_s'] < c['stop_s'], 'Discard window')
    require(c['maxstep_s'] <= .5/c['noisefmax_Hz'], 'Noise maximum frequency timestep')
    require(c['noisefmin_Hz'] < c['noisefmax_Hz'], 'Noise band')
    require(abs(c['stop_s']/c['strobe_s']-round(c['stop_s']/c['strobe_s'])) < 1e-7, 'Grid')
    require(c['vdd_V'] == 1.2 and c['temperature_C'] == 25, 'Protocol is TT 1.2V 25C')


def header(model, c):
    require(not any(x in model.as_posix() for x in ('"', '\n', '\r')), 'PDK path')
    return '''simulator lang=spectre insensitive=yes
include "{model}" section=tt_mos
simulatorOptions options temp={temperature_C:.16g} reltol=1e-5 vabstol=1e-7 iabstol=1e-16 gmin=1e-14
'''.format(model=model.as_posix(), **c)


def core(c):
    return '''VDD (vdd 0) vsource dc={vdd_V:.16g}
VGN (gn 0) vsource dc={vn_V:.16g}
VGP (gp 0) vsource dc={vp_V:.16g}
XN (out gn 0 0) nm1p2_svt_lp w=1u l=1u nf=1 mr=1 prelayout=1
XP (out gp vdd vdd) pm1p2_svt_lp w=1u l=1u nf=1 mr=1 prelayout=1
Ccore (out 0) capacitor c={cextra_F:.16g}
'''.format(**c)


def comparator(c):
    # Separate same-voltage supplies permit direct core/comparator accounting.
    # IBIAS is ideal, but its current is drawn from VDC and is included in power.
    return '''// Candidate: NMOS differential pair, PMOS mirror load, NMOS tail mirror,
// followed by TWO CMOS inverters. bit high corresponds to out > ref.
VDC (vdc 0) vsource dc={vdd_V:.16g}
IBIAS (vdc nbias) isource dc={comparator_bias_A:.16g}
XBIAS (nbias nbias 0 0) nm1p2_svt_lp w=2u l=1u nf=1 mr=1 prelayout=1
XTAIL (tail nbias 0 0) nm1p2_svt_lp w=2u l=1u nf=1 mr=1 prelayout=1
XIP (mirror out tail 0) nm1p2_svt_lp w=4u l=1u nf=1 mr=1 prelayout=1
XIN (sense ref tail 0) nm1p2_svt_lp w=4u l=1u nf=1 mr=1 prelayout=1
XLP (mirror mirror vdc vdc) pm1p2_svt_lp w=2u l=1u nf=1 mr=1 prelayout=1
XLM (sense mirror vdc vdc) pm1p2_svt_lp w=2u l=1u nf=1 mr=1 prelayout=1
XB1N (inv sense 0 0) nm1p2_svt_lp w=1u l=0.5u nf=1 mr=1 prelayout=1
XB1P (inv sense vdc vdc) pm1p2_svt_lp w=2u l=0.5u nf=1 mr=1 prelayout=1
XB2N (bit inv 0 0) nm1p2_svt_lp w=1u l=0.5u nf=1 mr=1 prelayout=1
XB2P (bit inv vdc vdc) pm1p2_svt_lp w=2u l=0.5u nf=1 mr=1 prelayout=1
Cbit (bit 0) capacitor c={output_load_F:.16g}
'''.format(**c)


def dc_deck(model, c, low, high, step):
    return header(model, c)+comparator(c)+'''parameters vref={low:.16g}
VIN (out 0) vsource dc=0.6
VREF (ref 0) vsource dc=vref
save out ref bit sense inv tail nbias VDC:p
dcTransfer dc param=vref start={low:.16g} stop={high:.16g} step={step:.16g}
'''.format(low=low, high=high, step=step)


def op_deck(model, c, center=None):
    deck=header(model, c)+core(c)
    if center is not None:
        deck+=comparator(c)+'VREF (ref 0) vsource dc={:.16g}\n'.format(center)
        deck+='save bit ref sense tail nbias VDC:p\n'
    return deck+'''save out VDD:p
dcOp dc
opInfo info what=oppoint where=file file="oppoint.txt"
'''


def step_deck(model, c, center, loaded):
    deck=header(model, c)+comparator(c)
    pulse='type=pulse val0={:.16g} val1={:.16g} delay=10u rise=10n fall=10n width=10u period=20u'
    if loaded:
        deck+=core(c)+'VREF (ref 0) vsource '+pulse.format(center-.01, center+.01)+'\nsave VDD:p\n'
    else:
        deck+='VIN (out 0) vsource '+pulse.format(.59, .61)+'\n'
        deck+='VREF (ref 0) vsource dc={:.16g}\n'.format(center)
    return deck+'''save out ref bit sense VDC:p
tranStep tran stop=100u maxstep=5n strobeperiod=20n strobeoutput=strobeonly
'''


def noise_settings(c):
    cases=[]
    for seed in c['seeds']:
        cases.append(dict(name='bare_seed{}'.format(seed), loaded=False, seed=seed, offset=0.))
    for offset in c['reference_offsets_V']:
        tag=('m' if offset < 0 else 'p')+str(int(round(abs(offset)*1000)))
        for seed in c['seeds']:
            cases.append(dict(name='loaded_ref{}_seed{}'.format(tag, seed), loaded=True, seed=seed, offset=offset))
    for name, change in [('fmax25M', dict(noisefmax_Hz=25e6)),
                         ('fmax100M', dict(noisefmax_Hz=100e6, maxstep_s=5e-9)),
                         ('step5ns', dict(maxstep_s=5e-9)),
                         ('fmin5000', dict(noisefmin_Hz=5000))]:
        cases.append(dict(name='convergence_'+name, loaded=True, seed=17, offset=0., **change))
    return cases


def noise_deck(model, c, center, setting):
    p=dict(c); p.update(setting)
    deck=header(model, c)+core(c)
    if setting['loaded']:
        deck+=comparator(c)+'VREF (ref 0) vsource dc={:.16g}\n'.format(center+setting['offset'])
        deck+='save bit VDC:p\n'
    deck+='save out VDD:p\n'
    return deck+('tranNoise tran stop={stop_s:.16g} maxstep={maxstep_s:.16g} '
                 'strobeperiod={strobe_s:.16g} strobeoutput=strobeonly '
                 'noisefmin={noisefmin_Hz:.16g} noisefmax={noisefmax_Hz:.16g} '
                 'noiseseed={seed} noisescale=1\n').format(**p)


def rows(path, axis):
    current=None
    for key, value in e.read_values(path):
        if key == axis:
            if current is not None:
                yield current
            current={axis:value}
        elif current is not None:
            require(key not in current, 'Duplicate scalar in PSF row: '+key)
            current[key]=value
    if current is not None:
        yield current


def transfer(path, start, stop, step, vdd, require_rails=True):
    points=list(rows(path, 'vref'))
    count=int(round((stop-start)/step))+1
    require(len(points)==count, 'Incomplete DC sweep')
    for i,r in enumerate(points):
        require(abs(r['vref']-(start+i*step))<1e-9, 'Nonuniform DC sweep')
        require(-.05 < r['bit'] < vdd+.05, 'Output outside supply rails')
    points.sort(key=lambda r:r['vref'])
    if require_rails:
        require(points[0]['bit']>.9*vdd and points[-1]['bit']<.1*vdd, 'Comparator must produce high/low rails with correct polarity')
    require(all(b['bit']-a['bit']<.01*vdd for a,b in zip(points,points[1:])), 'Non-monotonic transfer')
    crossings=[]
    for a,b in zip(points,points[1:]):
        if a['bit'] >= .5*vdd and b['bit'] < .5*vdd:
            crossings.append(a['vref']+(b['vref']-a['vref'])*(a['bit']-.5*vdd)/(a['bit']-b['bit']))
    require(len(crossings)==1, 'Ambiguous comparator threshold')
    return dict(reference_trip_V=crossings[0], input_V=.6, points=len(points),
                reference_grid_V=abs(step), high_V=points[0]['bit'], low_V=points[-1]['bit'])


def checked_trace(path, stop, strobe, signals):
    expected=int(round(stop/strobe))+1
    n=0; duplicate=False; last=None
    for r in rows(path, 'time'):
        require(all(k in r for k in signals), 'Missing required trace signal')
        if n == expected:
            require(not duplicate and last is not None and
                    abs(r['time']-stop)<=1e-12 and abs(last['time']-stop)<=1e-12 and
                    r['time']>=last['time'], 'Unexpected extra transient point')
            require(all(abs(r[k]-last[k]) <= (1e-12 if k.endswith(':p') else 1e-6)
                        for k in signals), 'Conflicting terminal duplicate')
            duplicate=True
            continue
        require(abs(r['time']-n*strobe)<=1e-12, 'Missing/nonuniform transient sample')
        n+=1; last=r
        yield r
    require(n==expected and last is not None and abs(last['time']-stop)<=1e-12, 'Incomplete transient')


def check_step(path, c, loaded):
    rr=list(checked_trace(path, 100e-6, 20e-9, ['out','ref','bit','vdc:p']))
    # Gate only late plateaus, safely away from the finite input ramps.
    plateaus=[]
    for lo,hi,expected in [(6e-6,9e-6,int(loaded)), (16e-6,19e-6,int(not loaded)),
                           (26e-6,29e-6,int(loaded)), (36e-6,39e-6,int(not loaded))]:
        values=[r['bit'] for r in rr if lo <= r['time'] <= hi]
        require(values and all(v>.9*c['vdd_V'] if expected else v<.1*c['vdd_V'] for v in values),
                'Comparator failed 10us plateau check; inspect waveforms before noise statistics')
        plateaus.append(dict(start_s=lo, stop_s=hi, expected_bit=expected))
    delays=[]
    for edge,new_input in [(10e-6,1),(20.01e-6,0),(30e-6,1),(40.01e-6,0)]:
        target=1-new_input if loaded else new_input
        hits=[r['time'] for r in rr if edge<=r['time']<edge+9e-6 and
              (r['bit']>.9*c['vdd_V'] if target else r['bit']<.1*c['vdd_V'])]
        require(hits, 'Missing response transition')
        delays.append(dict(edge_s=edge, target_bit=target, first_rail_delay_s=hits[0]-edge))
    return dict(plateaus=plateaus, delays=delays, timing_resolution_s=20e-9,
                interpretation='NOISELESS_10mV_OVERDRIVE_ONLY; not stochastic probability settling')


class PairStats:
    def __init__(self):
        self.n=0; self.sx=self.sy=self.sxy=0.
    def add(self, x,y):
        self.n+=1; self.sx+=x; self.sy+=y; self.sxy+=x*y
    def result(self):
        if self.n<2: return dict(pairs=self.n, correlation=None)
        px=self.sx/self.n; py=self.sy/self.n
        denom=math.sqrt(px*(1-px)*py*(1-py))
        return dict(pairs=self.n, correlation=(self.sxy/self.n-px*py)/denom if denom else None,
                    p11=self.sxy/self.n, p_left=px, p_right=py)


def summarize_trace(path, c, loaded):
    signals=['out','vdd:p']+(['bit','vdc:p'] if loaded else [])
    lags=[1,10,50,100]; pairs={k:PairStats() for k in lags}
    history=deque(maxlen=max(lags)); n=0; mean=m2=0.; ones=invalid=0
    core_power=cmp_power=0.; block_n=block_ones=0; blocks=[]
    block_size=int(round(500e-6/c['strobe_s']))
    for r in checked_trace(path,c['stop_s'],c['strobe_s'],signals):
        # Half-open retained window; preserve endpoint only for integrity checks.
        if r['time'] < c['discard_s']-1e-12 or r['time'] >= c['stop_s']-1e-12: continue
        n+=1; delta=r['out']-mean; mean+=delta/n; m2+=delta*(r['out']-mean)
        b=int(r['bit']>.5*c['vdd_V']) if loaded else int(r['out']>.6)
        ones+=b
        if loaded:
            invalid+=int(.2*c['vdd_V']<r['bit']<.8*c['vdd_V'])
            cmp_power+=-c['vdd_V']*r['vdc:p']
        core_power+=-c['vdd_V']*r['vdd:p']
        for k in lags:
            if len(history)>=k:pairs[k].add(history[-k],b)
        history.append(b); block_n+=1; block_ones+=b
        if block_n==block_size:
            blocks.append(block_ones/float(block_n)); block_n=block_ones=0
    require(n>1, 'No retained samples')
    return dict(samples=n, mean_out_V=mean, std_out_V=math.sqrt(m2/(n-1)),
                p1=ones/float(n), comparator_midrail_fraction=invalid/float(n) if loaded else None,
                core_power_W=core_power/n, comparator_power_W=cmp_power/n if loaded else None,
                lag_correlations={str(k*c['strobe_s']):pairs[k].result() for k in lags},
                block_duration_s=500e-6, block_probabilities=blocks,
                leftover_block_samples=block_n,
                bit_definition='Vbit>VDD/2' if loaded else 'IDEAL_OUT_THRESHOLD_0.6V',
                acceptance='DESCRIPTIVE_ONLY; correlated samples; no IID confidence interval or entropy claim')


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--verify',action='store_true')
    ap.add_argument('--generate-only',action='store_true')
    ap.add_argument('--out',type=Path)
    ap.add_argument('--finalize',type=Path)
    ap.add_argument('--pdk',default=os.environ.get('PBIT_PDK_ROOT',e.DEFAULT_PDK))
    args=ap.parse_args()
    e.verify_source()
    if args.finalize:e.finalize(args.finalize.resolve());return 0
    c=json.loads((SOURCE/'config.json').read_text(encoding='utf-8')); validate(c)
    if args.verify:print('Source checksums and configuration: PASS');return 0
    if args.out is None:ap.error('--out required')
    out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    e.write_json(out/'config.json',c)
    _,model,discovery=discover_model(args.pdk);e.write_json(out/'pdk_discovery.json',discovery)
    if model is None:e.write_json(out/'summary.json',dict(status='BLOCKED_PDK'));return 2
    expected=json.loads((SOURCE/'local_pdk_hashes.json').read_text(encoding='utf-8'))
    hashes={'model/spectre/'+p.relative_to(model.parent).as_posix():e.digest(p)
            for p in model.parent.rglob('*') if p.is_file()}
    matches=all(hashes.get(k)==v for k,v in expected.items())
    e.write_json(out/'pdk_comparison.json',dict(matches_local=matches,hashes=hashes))
    if not matches:e.write_json(out/'summary.json',dict(status='BLOCKED_PDK_HASH'));return 2
    e.write_json(out/'metadata.json',dict(utc=datetime.utcnow().isoformat()+'Z',
        job=os.environ.get('SLURM_JOB_ID'),host=os.environ.get('HOSTNAME'),python=sys.version,
        model=str(model),config_sha256=e.digest(SOURCE/'config.json'),scope=c['scope'],
        baseline_job=c['baseline_job'],git_revision='N/A standalone EDA; source/package_manifest.json',
        comparator='10 MOS + ideal reference current + two output inverters included in 10 MOS',
        physical_entropy_validated=False, calibration='nominal static threshold only'))
    exe=shutil.which(os.environ.get('SPECTRE_BIN','spectre')) if not args.generate_only else None
    if not exe and not args.generate_only:
        e.write_json(out/'summary.json',dict(status='BLOCKED_NO_SPECTRE'));return 2
    if exe:
        with (out/'version.txt').open('w') as f:
            subprocess.run([exe,'-W'],stdout=f,stderr=subprocess.STDOUT,timeout=30)
    records=[]; calibration={}

    def persist(status):
        e.write_json(out/'summary.json',dict(status=status,cases=records,calibration=calibration,
            statistical_acceptance='PENDING_REVIEW',physical_entropy_validated=False))

    def run(name,deck,suffixes,check=None,timeout=None,setting=None):
        folder=out/name;folder.mkdir()
        with (folder/'input.scs').open('w',encoding='utf-8',newline='\n') as f:f.write(deck)
        if args.generate_only:
            result=dict(status='GENERATED_NOT_SIMULATED')
        else:
            result=e.run_case(exe,folder,suffixes,timeout or c['gate_timeout_s'])
            if result['status']=='COMPLETED_REVIEW_REQUIRED' and check:
                try:result['measurements']=check(folder,result)
                except (ValueError,KeyError,IndexError,OSError) as exc:
                    result.update(status='FAILED_OUTPUT_CHECK',check_error=str(exc))
        e.write_json(folder/'status.json',result)
        records.append(dict(case=name,setting=setting,**result));persist('IN_PROGRESS')
        print(name+': '+result['status'],flush=True)
        return result

    def gate(result):
        if result['status'] in ('GENERATED_NOT_SIMULATED','COMPLETED_REVIEW_REQUIRED'):return True
        persist('STOPPED_AT_PREREQUISITE; inspect candidate circuit; noisy cases not launched')
        return False

    def opcheck(folder,result,loaded=False):
        d=dict(e.read_values(folder/'raw/dcOp.dc'))
        require(.599<=d['out']<=.601, 'Core DC drift')
        require(15e-9<=-d['vdd:p']<=18e-9, 'Core current drift')
        require((folder/'oppoint.txt').is_file(), 'Missing device operating point')
        if loaded:require(d['vdc:p']<0, 'Comparator supply current sign')
        return dict(out_V=d['out'],core_current_A=-d['vdd:p'],
                    comparator_current_A=-d['vdc:p'] if loaded else None)

    if not gate(run('00_core_op',op_deck(model,c),['.dc'],opcheck)):return 1
    trips=[]
    for name,start,stop,step in [('01_dc_forward',.57,.63,.0001),('02_dc_reverse',.63,.57,-.0001)]:
        def dc_check(folder,result,start=start,stop=stop,step=step):
            return transfer(folder/'raw/dcTransfer.dc',start,stop,step,c['vdd_V'])
        r=run(name,dc_deck(model,c,start,stop,step),['.dc'],dc_check)
        if not gate(r):return 1
        trips.append(.6 if args.generate_only else r['measurements']['reference_trip_V'])
    if abs(trips[0]-trips[1])>.0002:
        persist('STOPPED_DC_DIRECTION_DEPENDENCE');return 1
    coarse=sum(trips)/2
    r=run('03_dc_fine',dc_deck(model,c,coarse-.0005,coarse+.0005,.00001),['.dc'],
        lambda f,r:transfer(f/'raw/dcTransfer.dc',coarse-.0005,coarse+.0005,.00001,c['vdd_V'],False))
    if not gate(r):return 1
    center=.6 if args.generate_only else r['measurements']['reference_trip_V']
    calibration.update(reference_center_V=center,coarse_trips_V=trips,
                       preview_placeholder=args.generate_only,
                       interpretation='DC-only nominal calibration; not p=0.5 noise calibration')
    e.write_json(out/'calibration.json',calibration)
    for name,loaded in [('04_comparator_step',False),('06_loaded_reference_step',True)]:
        r=run(name,step_deck(model,c,center,loaded),['.tran'],
              lambda f,r,loaded=loaded:check_step(f/r['result_files']['.tran'][0],c,loaded))
        if not gate(r):return 1
    if not gate(run('05_loaded_op',op_deck(model,c,center),['.dc'],
                    lambda f,r:opcheck(f,r,True))):return 1
    for setting in noise_settings(c):
        local=dict(c);local.update(setting)
        run(setting['name'],noise_deck(model,c,center,setting),['.tran'],
            lambda f,r,local=local: summarize_trace(f/r['result_files']['.tran'][0],local,local['loaded']),
            c['case_timeout_s'],setting)
    if args.generate_only:persist('GENERATED_NOT_SIMULATED; calibration provisional');return 0
    complete=all(r['status']=='COMPLETED_REVIEW_REQUIRED' for r in records)
    persist('COMPLETED_REVIEW_REQUIRED' if complete else 'INCOMPLETE_OR_FAILED')
    return 0 if complete else 1


if __name__=='__main__':
    sys.exit(main())
