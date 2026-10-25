"""Bounded-memory diagnostics for correlated comparator output; Python >=3.6."""
from collections import deque
import math
import run_characterization as parser
import scan_measurements as scan


class Moments:
    def __init__(self):self.n=0;self.mean=0.;self.m2=0.
    def add(self,value):
        self.n+=1;delta=value-self.mean;self.mean+=delta/self.n;self.m2+=delta*(value-self.mean)
    def variance(self):return self.m2/(self.n-1) if self.n>1 else None


def probability(path,c):
    """Fixed strobe marginal; currents intentionally absent in calibration."""
    scan.complete_psf(path)
    ones=n=mid=0
    for row in parser.checked_trace(path,c['stop_s'],c['strobe_s'],['out','bit']):
        if not c['discard_s']-1e-12<=row['time']<c['stop_s']-1e-12:continue
        parser.require(-.05<=row['bit']<=.85,'Calibration bit outside rail')
        n+=1;ones+=int(row['bit']>.4);mid+=int(.16<row['bit']<.64)
    parser.require(n==int(round((c['stop_s']-c['discard_s'])/c['strobe_s'])),'Calibration count')
    return dict(samples=n,p1=ones/float(n),midrail_fraction=mid/float(n),
                interpretation='Correlated finite calibration record; no IID confidence bound')


def long_trace(path,c):
    scan.complete_psf(path)
    dt=c['strobe_s'];lags=[1,2,5,10,20,50,100,200,500,1000]
    pairs={lag:parser.PairStats() for lag in lags};history=deque(maxlen=max(lags))
    out=Moments();ones=mid=transitions=0;previous=None;power_core=Moments();power_cmp=Moments()
    block_sizes=[int(round(seconds/dt)) for seconds in [.0005,.001,.002,.005]]
    blocks={k:dict(count=0,ones=0,values=[]) for k in block_sizes}
    windows={}
    for us in c.get('window_intervals_us',[.1,.2,.5,1,2,5,10]):
        for length in c.get('window_lengths',[32,128]):
            windows[(us,length)]=dict(stride=int(round(us*1e-6/dt)),count=0,ones=0,stats=Moments())
    signals=['out','bit','vdd:p','vdc:p']
    for row in parser.checked_trace(path,c['stop_s'],dt,signals):
        if not c['discard_s']-1e-12<=row['time']<c['stop_s']-1e-12:continue
        parser.require(-.05<=row['bit']<=.85,'Bit voltage outside rail')
        index=out.n;out.add(row['out']);b=int(row['bit']>.4);ones+=b
        mid+=int(.16<row['bit']<.64);transitions+=int(previous is not None and previous!=b);previous=b
        power_core.add(-1.2*row['vdd:p']);power_cmp.add(-.8*row['vdc:p'])
        for lag,state in pairs.items():
            if len(history)>=lag:state.add(history[-lag],b)
        history.append(b)
        for k,state in blocks.items():
            state['count']+=1;state['ones']+=b
            if state['count']==k:
                state['values'].append(state['ones']/float(k));state['count']=state['ones']=0
        for (us,length),state in windows.items():
            if index%state['stride']:continue
            state['count']+=1;state['ones']+=b
            if state['count']==length:
                state['stats'].add(state['ones']/float(length));state['count']=state['ones']=0
    expected=int(round((c['stop_s']-c['discard_s'])/dt))
    parser.require(out.n==expected and expected>max(lags),'Validation sample count')
    p=ones/float(out.n);window_report={}
    for (us,length),state in windows.items():
        stats=state['stats'];var=stats.variance();iid=p*(1-p)/length
        window_report['{}us_T{}'.format(us,length)]=dict(sampling_interval_us=us,T=length,
            nonoverlapping_windows=stats.n,discarded_partial_bits=state['count'],
            mean_window_probability=stats.mean if stats.n else None,variance_window_probability=var,
            iid_variance_at_record_p=iid,variance_ratio_to_iid=var/iid if var is not None and iid>0 else None,
            sample_mse_to_half=(stats.m2/stats.n+(stats.mean-.5)**2) if stats.n else None,
            review='TOO_FEW_WINDOWS' if stats.n<8 else 'DESCRIPTIVE_WINDOWS_CAN_STILL_BE_CORRELATED')
    flags=[]
    if abs(p-.5)>.02:flags.append('P1_MORE_THAN_2PP_FROM_TARGET_REVIEW_ONLY')
    if mid/float(out.n)>.02:flags.append('MIDRAIL_OVER_2_PERCENT_REVIEW_ONLY')
    return dict(samples=out.n,p1=p,mean_out_V=out.mean,std_out_V=math.sqrt(out.variance()),
        midrail_fraction=mid/float(out.n),transitions=transitions,
        core_power_W=power_core.mean,comparator_power_W=power_cmp.mean,total_power_W=power_core.mean+power_cmp.mean,
        power_estimator='PROVISIONAL_UNIFORM_STROBE_MEAN; no new adaptive audit in this protocol',
        lag_correlations={str(lag*dt):state.result() for lag,state in pairs.items()},
        block_probabilities={str(k*dt):v['values'] for k,v in blocks.items()},window_statistics=window_report,
        review_flags=flags,interpretation='No independence, entropy-rate, PVT or bit-energy certification')


def interpolate(points):
    """Calibration only. Refuse missing/nonmonotonic data and extrapolation."""
    points=sorted(points,key=lambda p:p['reference_V'])
    if len(points)!=5 or any(len(p['seed_p1'])!=3 for p in points):
        return dict(status='BLOCKED_INCOMPLETE_CALIBRATION')
    if any(p['mean_p1'] is None or not math.isfinite(p['mean_p1']) for p in points):
        return dict(status='BLOCKED_NONFINITE_CALIBRATION')
    if any(b['mean_p1']>a['mean_p1'] for a,b in zip(points,points[1:])):
        return dict(status='BLOCKED_NONMONOTONIC_CALIBRATION')
    exact=[p for p in points if p['mean_p1']==.5]
    if len(exact)>1:return dict(status='BLOCKED_AMBIGUOUS_HALF_PLATEAU')
    if len(exact)==1:return dict(status='CALIBRATED_NOT_YET_VALIDATED',reference_V=exact[0]['reference_V'])
    for a,b in zip(points,points[1:]):
        if a['mean_p1']>=.5>=b['mean_p1'] and a['mean_p1']>b['mean_p1']:
            ref=a['reference_V']+(b['reference_V']-a['reference_V'])*(a['mean_p1']-.5)/(a['mean_p1']-b['mean_p1'])
            return dict(status='CALIBRATED_NOT_YET_VALIDATED',reference_V=ref,
                bracketing_reference_V=[a['reference_V'],b['reference_V']],
                method='Local linear interpolation of calibration seeds only; frozen before fresh-seed checks')
    return dict(status='BLOCKED_P_HALF_NOT_BRACKETED')
