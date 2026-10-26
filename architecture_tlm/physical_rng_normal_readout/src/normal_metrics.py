"""Physical bias gates and rail-aware statistics; no independence certification."""
from array import array
from pathlib import Path
import math,statistics
import engine as e
import run_characterization as parser
import lowpower as lp
import long_metrics as m
import scan_measurements as scan

def bias_checks(points,c):
    checks=[]
    for name in ['XIP','XIN','XTAIL','XLP','XLM']:
        p=points.get(name,{})
        if not all(k in p for k in ['vgs','vth','vds','vdsat','gmoverid']):raise ValueError('Missing operating-point fields '+name)
        over=abs(p['vgs'])-abs(p['vth']);margin=abs(p['vds'])-abs(p['vdsat'])
        is_input=name in ['XIP','XIN']
        minimum=c['input_min_overdrive_V'] if is_input else c['other_analog_min_overdrive_V']
        maximum=c['input_max_gmoverid_per_V'] if is_input else c['other_analog_max_gmoverid_per_V']
        ok=over>=minimum and 0<p['gmoverid']<=maximum and margin>=0
        checks.append(dict(device=name,overdrive_V=over,saturation_margin_V=margin,gmoverid=p['gmoverid'],pass_gate=ok))
    return dict(passed=all(x['pass_gate'] for x in checks),devices=checks,
        policy='Input pair positive>=60mV overdrive,gm/Id<=22; other conducting analog devices>=30mV,gm/Id<=26; nonnegativeVDS-VDSAT. Not a claim that off digital transistors conduct in strong inversion.')

def op(folder,c):
    values=dict(e.read_values(folder/'raw/dcOp.dc'));points=lp.device_points(folder/'oppoint.txt')
    gate=bias_checks(points,c)
    gate.update(core_V=values['out'],core_A=-values['vdd:p'],comparator_DC_W=-1.2*values['vdc:p'],points=points)
    e.write_json(folder/'bias_diagnostics.json',gate)
    if not .598<=values['out']<=.602 or not 15e-9<=-values['vdd:p']<=18e-9:raise ValueError('Core working point drift')
    if not 0<=values['nbias']<=1.1:raise ValueError('Current reference compliance')
    if not gate['passed']:raise ValueError('Rejected weak inversion or analog saturation margin')
    for name,p in points.items():
        if any(abs(p[k])>1.21 for k in ['vgs','vds','vgd','vgb'] if k in p):raise ValueError('Terminal voltage stress '+name)
    return gate

def step(path,c,reference):
    rows=list(parser.checked_trace(path,c['step_stop_s'],c['step_strobe_s'],['out','ref','bit']))
    edges=[];previous=rows[0]['ref']>reference
    for i,r in enumerate(rows[1:],1):
        side=r['ref']>reference
        if side!=previous:edges.append((i,not side));previous=side
    delays=[]
    for j,(i,high) in enumerate(edges):
        end=edges[j+1][0] if j+1<len(edges) else len(rows)
        segment=rows[i:end];target=lambda v:v>=1.08 if high else v<=.12
        hits=[r['time'] for r in segment if target(r['bit'])]
        if not hits:raise ValueError('Missing valid step rail')
        delay=hits[0]-rows[i]['time'];delays.append(delay)
        tail=[r for r in segment if r['time']>=rows[i]['time']+1e-6]
        if not tail or not all(target(r['bit']) for r in tail):raise ValueError('Step output failed to remain settled')
    if len(delays)<8:raise ValueError('Missing pulse transitions')
    return dict(maximum_delay_s=max(delays),first_rail_delay_s=delays,edges=len(delays),
        meets_speed_target=max(delays)<=c['maximum_step_delay_s'],resolution_s=c['step_strobe_s'],
        independent_bit_rate_proved=False)

def wave(path,q,c,folder=None):
    scan.complete_psf(path);core=array('d');voltage=array('d');raw=[]
    start=round(q['discard_s']/q['strobe_s']);count=round((q['stop_s']-q['discard_s'])/q['strobe_s'])
    stride=round(c['sample_interval_s']/q['strobe_s'])
    for j,r in enumerate(parser.checked_trace(path,q['stop_s'],q['strobe_s'],['out','bit'])):
        index=j-start
        if not 0<=index<count:continue
        core.append(r['out']);voltage.append(r['bit'])
        if index%stride==0:
            level=m.logic_level(r['bit'],1.2,c)
            raw.append(dict(raw_index=index//stride,time_s=r['time'],core_V=r['out'],comparator_V=r['bit'],
                bit=int(r['bit']>.6),level=level,level_valid=level in ['LOW','HIGH']))
    if len(core)!=count:raise ValueError('Wrong dense sample count')
    if any(abs(r['time_s']-(q['discard_s']+i*c['sample_interval_s']))>1e-12 for i,r in enumerate(raw)):raise ValueError('Wrong sampling timestamps')
    bits=[int(v>.6) for v in voltage];levels=[m.logic_level(v,1.2,c) for v in voltage]
    dense_acf={str(us):m.lagged(bits,round(us*1e-6/q['strobe_s'])) for us in [.1,.5,1,2,5,10,20,50,100]}
    result=dict(dense_points=len(bits),p1=sum(bits)/float(len(bits)),midrail_fraction=levels.count('MID')/float(len(bits)),
        core_distribution=m.distribution(core,[.4+i*.002 for i in range(201)]),
        comparator_distribution=m.distribution(voltage,[-.05+i*.005 for i in range(261)]),dense_acf=dense_acf,
        actual_sample_bits=len(raw),actual_P1=sum(r['bit'] for r in raw)/float(len(raw)),
        actual_MID=sum(not r['level_valid'] for r in raw),actual_acf={str(k):m.lagged([r['bit'] for r in raw],k) for k in c['lag_samples']})
    if folder:
        if len(raw)!=20000:raise ValueError('Expected exactly20000 actual samples')
        folder=Path(folder);m.write_csv(folder/'raw_1us.csv',list(raw[0]),raw)
        with (folder/'raw_1us_bits.txt').open('w',encoding='ascii',newline='\n') as f:
            for r in raw:f.write(str(r['bit'])+'\n')
        vn,pairs=m.von_neumann(raw);eligible=[r for r in vn if r['level_valid']]
        m.write_csv(folder/'vn_pairs.csv',list(pairs[0]),pairs)
        if vn:m.write_csv(folder/'vn_all_emitted.csv',list(vn[0]),vn)
        if eligible:m.write_csv(folder/'vn_valid_emitted.csv',list(eligible[0]),eligible)
        quality=dict(raw=m.bit_statistics(raw,c,q['discard_s'],q['stop_s']-q['discard_s']),
            vn_all=m.bit_statistics(vn,c,q['discard_s'],q['stop_s']-q['discard_s']),
            vn_valid=m.bit_statistics(eligible,c,q['discard_s'],q['stop_s']-q['discard_s']),
            vn_retention_per_raw=len(eligible)/float(len(raw)),seed_packets={},physical_entropy_certified=False,
            invalid_policy='All rawMID retained; VN invalid outputs excluded explicitly with original timestamps')
        for label,rows in [('raw',raw),('vn_valid',eligible)]:
            words=m.words32(rows)
            quality['seed_packets'][label]=dict(lfsr32=m.packet_statistics(words,32,1),bivium177=m.packet_statistics(words,177,6))
            if words:m.write_csv(folder/(label+'_words32.csv'),list(words[0]),words)
        e.write_json(folder/'quality.json',quality)
    return result

def numerical_screen(rows,c):
    groups={tag:{r['setting']['q']['seed']:r['metrics'] for r in rows if r['setting']['tag']==tag} for tag in ['base','fine','wide']}
    out=[];tol=c['numerical_tolerances']
    for a,b in [('base','fine'),('fine','wide')]:
        differences=[]
        for seed in c['numeric_seeds']:
            x,y=groups[a][seed],groups[b][seed]
            differences.append(dict(seed=seed,P1=abs(x['p1']-y['p1']),MID=abs(x['midrail_fraction']-y['midrail_fraction']),
                CDF=max(max(abs(u-v) for u,v in zip(x[k]['cdf'],y[k]['cdf'])) for k in ['core_distribution','comparator_distribution']),
                sigma_relative=max(abs(x[k]['std_V']-y[k]['std_V'])/max(1e-12,x[k]['std_V']) for k in ['core_distribution','comparator_distribution']),
                ACF=max(abs(x['dense_acf'][k]['correlation']-y['dense_acf'][k]['correlation']) for k in x['dense_acf'] if x['dense_acf'][k]['correlation'] is not None and y['dense_acf'][k]['correlation'] is not None)))
        means={k:statistics.mean(d[k] for d in differences) for k in tol}
        out.append(dict(left=a,right=b,seeds=differences,means=means,passed=all(means[k]<=tol[k] for k in tol)))
    return dict(status='SHORT_SCREEN_PASS' if all(r['passed'] for r in out) else 'SHORT_SCREEN_REVIEW_REQUIRED',comparisons=out,tolerances=tol)
