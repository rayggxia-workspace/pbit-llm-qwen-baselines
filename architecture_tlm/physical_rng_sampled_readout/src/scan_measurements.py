"""Capacitance screening diagnostics; Python 3.6+, standard library only.

Finite-record correlations and power diagnostics are not an entropy estimate.
Keep waveforms for offline PSD, confidence and full ACF review.
"""
from array import array
import bisect
import math
import re
import engine as e
import lowpower as lp
import run_characterization as old

R = old.require
COMPLEX = re.compile(r'^"([^\"]+)"\s+\(([-+0-9.eE]+)\s+([-+0-9.eE]+)\)\s*$')
LAGS = [1, 2, 3, 5, 10, 15, 20, 25, 40, 50, 75, 100, 150, 200, 250, 500, 1000]


def window_stats(stream,dt,c):
    """Nonoverlapping windows, without presuming adjacent windows are IID."""
    p=sum(stream)/float(len(stream));result={}
    for us in c.get('window_intervals_us',[.1,.2,.5,1,2,5,10]):
        stride=int(round(us*1e-6/dt))
        R(stride>0 and abs(stride*dt-us*1e-6)<1e-12, 'Window sample stride')
        sampled=stream[::stride]
        for length in c.get('window_lengths',[32,128]):
            n=len(sampled)//length;mean=m2=0.
            for i in range(n):
                value=sum(sampled[i*length:(i+1)*length])/float(length)
                delta=value-mean;mean+=delta/(i+1);m2+=delta*(value-mean)
            variance=m2/(n-1) if n>1 else None;iid=p*(1-p)/length
            result['{}us_T{}'.format(us,length)]=dict(sampling_interval_us=us,T=length,nonoverlapping_windows=n,
                discarded_partial_bits=len(sampled)%length,mean_window_probability=mean if n else None,
                variance_window_probability=variance,iid_variance_at_record_p=iid,
                variance_ratio_to_iid=variance/iid if variance is not None and iid>0 else None,
                sample_mse_to_half=m2/n+(mean-.5)**2 if n else None,
                review='TOO_FEW_WINDOWS' if n<8 else 'DESCRIPTIVE_WINDOWS_CAN_STILL_BE_CORRELATED')
    return result


def complete_psf(path):
    # Spectre may leave a file with a plausible last row when interrupted.
    # Demand the explicit end marker as well as the time/frequency checks.
    with path.open('rb') as f:
        f.seek(max(0, path.stat().st_size - 1024))
        R(f.read().strip().endswith(b'END'), 'PSF missing terminal END: ' + str(path))


def correlation(values, lag):
    a, b = values[:-lag], values[lag:]
    n = len(a)
    R(n > 1, 'Insufficient pairs')
    sx, sy = sum(a), sum(b)
    xx = sum(x*x for x in a) - sx*sx/n
    yy = sum(y*y for y in b) - sy*sy/n
    xy = sum(x*y for x, y in zip(a, b)) - sx*sy/n
    rho = xy/math.sqrt(xx*yy) if xx > 0 and yy > 0 else None
    return dict(pairs=n, correlation=rho,
                interpretation='All overlapping pairs at this lag; not independent observations')


def stats(path, c, loaded):
    complete_psf(path)
    signals = ['out', 'vdd:p'] + (['bit', 'vdc:p'] if loaded else [])
    out = array('d'); actual = bytearray(); core = cmp = 0.; mid = 0
    for row in old.checked_trace(path, c['stop_s'], c['strobe_s'], signals):
        if not c['discard_s']-1e-12 <= row['time'] < c['stop_s']-1e-12:
            continue
        R(-.05 <= row['out'] <= 1.25, 'Core output beyond supply')
        out.append(row['out']); core -= c['vdd_V']*row['vdd:p']
        if loaded:
            R(-.05 <= row['bit'] <= .85, 'Comparator output beyond supply')
            actual.append(int(row['bit'] > .4)); mid += int(.16 < row['bit'] < .64)
            cmp -= .8*row['vdc:p']
    n = len(out)
    R(n == int(round((c['stop_s']-c['discard_s'])/c['strobe_s'])) and n > max(LAGS), 'Retained sample count')
    mean = sum(out)/n; centered = array('d', (x-mean for x in out))
    sigma = math.sqrt(sum(x*x for x in centered)/(n-1))
    ordered = sorted(out); median = .5*(ordered[(n-1)//2]+ordered[n//2])
    streams = {'ideal_fixed_0p6V': bytearray(int(x > .6) for x in out),
               'ideal_record_median': bytearray(int(x > median) for x in out)}
    if loaded: streams['actual_comparator'] = actual
    report = {}
    for name, stream in streams.items():
        p = sum(stream)/float(n)
        report[name] = dict(p1=p, transitions=sum(a != b for a, b in zip(stream, stream[1:])),
            lag_correlations={str(k*c['strobe_s']): correlation(stream, k) for k in LAGS},
            window_statistics=window_stats(stream,c['strobe_s'],c),
            block_p1=[sum(stream[i:i+5000])/float(len(stream[i:i+5000])) for i in range(0, n, 5000)],
            threshold_V=median if name == 'ideal_record_median' else .6 if name == 'ideal_fixed_0p6V' else .4)
    flags = []
    if loaded and abs(report['actual_comparator']['p1']-.5) > .02: flags.append('P1_DRIFT_GT_2PP_RECALIBRATION_REQUIRED_FOR_FAIR_P50_COMPARISON')
    if loaded and mid/float(n) > .02: flags.append('MIDRAIL_GT_2_PERCENT')
    if sigma <= 1e-6: flags.append('NOISE_AMPLITUDE_NEAR_ZERO')
    curve = []
    for i in range(81):
        ref = mean + sigma*(i/10.-4)
        curve.append(dict(threshold_V=ref, p1=(n-bisect.bisect_right(ordered, ref))/float(n)))
    return dict(samples=n, mean_out_V=mean, std_out_V=sigma, median_out_V=median,
        min_out_V=ordered[0], max_out_V=ordered[-1], streams=report,
        analog_lag_correlations={str(k*c['strobe_s']): correlation(centered, k) for k in LAGS},
        ideal_probability_curve=curve, midrail_fraction=mid/float(n) if loaded else None,
        core_power_W=core/n, comparator_power_W=cmp/n if loaded else 0., total_power_W=(core+cmp)/n,
        power_estimator='PROVISIONAL_STROBE_MEAN; no new full-solver-point power audit in this protocol',
        review_flags=flags, accepted_independent_bit_rate_Hz=None,
        interpretation='Bare zero-extra-C long record; median readout is descriptive, selected on this same record, not held-out P50 calibration or entropy certification')


def small_signal(folder, loaded, c, variant):
    op_path = folder/'raw/dcOp.dc'; complete_psf(op_path)
    d = dict(e.read_values(op_path))
    R(.599 <= d['out'] <= .601 and 15e-9 <= -d['vdd:p'] <= 18e-9, 'Core DC drift')
    diagnostics = lp.op_check(folder, c, variant, 'screen') if loaded else dict(out_V=d['out'])
    ac_path, noise_path = folder/'raw/acCore.ac', folder/'raw/noiseCore.noise'
    complete_psf(ac_path); complete_psf(noise_path)
    freq = []; z = []; active = False
    with ac_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line == 'VALUE': active = True; continue
            if line == 'END': break
            if not active: continue
            m = e.REAL.match(line)
            if m and m.group(1).lower() == 'freq': freq.append(float(m.group(2)))
            m = COMPLEX.match(line)
            if m and m.group(1).lower() == 'out': z.append(complex(float(m.group(2)), float(m.group(3))))
    R(len(freq) == len(z) and len(z) > 100 and abs(freq[0]-1) < 1e-9 and abs(freq[-1]-1e9) < 1., 'Incomplete AC sweep')
    R(all(a < b for a, b in zip(freq, freq[1:])) and all(math.isfinite(v.real) and math.isfinite(v.imag) for v in z), 'Invalid AC values')
    y = 1/z[0]; conductance = y.real; ceq = y.imag/(2*math.pi*freq[0])
    R(conductance > 0 and ceq > 0, 'Nonpositive low frequency conductance/capacitance; inspect stability')
    rows = list(old.rows(noise_path, 'freq'))
    R(len(rows) > 100 and rows[0]['freq'] == 1 and abs(rows[-1]['freq']-1e9) < 1., 'Incomplete noise sweep')
    R(all(a['freq'] < b['freq'] for a,b in zip(rows, rows[1:])), 'Noise frequency grid')
    R(all(math.isfinite(r['out']) and r['out'] >= 0 for r in rows), 'Noise output must be ASD')
    var = 0.; floor = c['noisefmin_Hz']
    for a, b in zip(rows, rows[1:]):
        lo, hi = max(floor, a['freq']), min(c['noisefmax_Hz'], b['freq'])
        if hi <= lo: continue
        s0, s1 = a['out']**2, b['out']**2
        s_lo = s0+(s1-s0)*(lo-a['freq'])/(b['freq']-a['freq'])
        s_hi = s0+(s1-s0)*(hi-a['freq'])/(b['freq']-a['freq'])
        var += .5*(s_lo+s_hi)*(hi-lo)
    reference = abs(z[0])/math.sqrt(2); crossing = None
    for f, impedance in zip(freq, z):
        if abs(impedance) <= reference: crossing = f; break
    return dict(dc=diagnostics, low_frequency_R_ohm=1/conductance,
        low_frequency_C_equivalent_F=ceq, low_frequency_tau_RC_s=ceq/conductance,
        first_AC_magnitude_minus3dB_grid_Hz=crossing,
        integrated_small_signal_band_Hz=[floor,c['noisefmax_Hz']],small_signal_RMS_V=math.sqrt(var),
        interpretation='PDK small-signal equivalent at frozen DC point; loaded active network need not be a single pole; C includes devices, not PEX')


def power_audit(path, c, loaded, variant):
    complete_psf(path)
    if loaded: return lp.adaptive_power_check(path, c, variant, 'screen')
    previous = None; first = last = None; energy = 0.; maxdt = 0.; points = 0
    for row in old.rows(path, 'time'):
        R('vdd:p' in row, 'Missing core current')
        if first is None: first = row['time']
        if previous is not None:
            dt = row['time']-previous['time']; R(dt >= 0, 'Time reversed')
            maxdt = max(maxdt, dt)
            if dt == 0: R(abs(row['vdd:p']-previous['vdd:p']) < 1e-12, 'Conflicting duplicate current')
            if dt > 0:
                lo = max(previous['time'], c['audit_discard_s']); hi = min(row['time'], c['audit_stop_s'])
                if hi > lo:
                    a = (lo-previous['time'])/dt; b = (hi-previous['time'])/dt
                    i0 = previous['vdd:p']+a*(row['vdd:p']-previous['vdd:p'])
                    i1 = previous['vdd:p']+b*(row['vdd:p']-previous['vdd:p'])
                    energy -= c['vdd_V']*.5*(i0+i1)*(hi-lo)
        points += 1; last = row['time']; previous = row
    R(first is not None and abs(first) < 1e-12 and abs(last-c['audit_stop_s']) < 1e-12, 'Incomplete adaptive endpoints')
    R(maxdt <= c['maxstep_s']*1.01, 'Adaptive gap')
    return dict(points=points, max_saved_gap_s=maxdt, total_power_W=energy/(c['audit_stop_s']-c['audit_discard_s']),
                integrated_energy_J=energy, interpretation='Short all-solver-point audit; no independent-bit energy claim')
