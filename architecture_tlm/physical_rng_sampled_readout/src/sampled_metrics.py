"""Sample after regenerative hold; preserve every invalid Q and capture ambiguity."""
from collections import deque
from pathlib import Path
import statistics
import engine as e
import long_metrics as m
import run_characterization as parser
import scan_measurements as scan

def valid(row,c):
    a=m.logic_level(row['q'],1.2,c);b=m.logic_level(row['qb'],1.2,c)
    return a in ('LOW','HIGH') and b in ('LOW','HIGH') and a!=b

def deterministic(path,c,kind,setting):
    fields=['out','bit','q','qb','track','ref','x','xi']
    step=c['deterministic_strobe_s'];stride=round(c['period_s']/step)
    delay=round(c['read_delay_s']/step);history=deque(maxlen=delay+1)
    reads=[];hold_bad=hold_changes=0;current=None
    for j,row in enumerate(parser.checked_trace(path,c['deterministic_stop_s'],step,fields)):
        history.append(row)
        k=j//stride;phase=j%stride
        if k>=2 and phase==0 and row['time']<c['deterministic_stop_s']-1e-12:
            capture=history[0];bit=int(row['q']>.6)
            r=dict(cycle=k,time_s=row['time'],sample_edge_s=row['time']-c['read_delay_s'],q_V=row['q'],qb_V=row['qb'],bit=bit,
                read_valid=valid(row,c),capture_D_V=capture['bit'],capture_level=m.logic_level(capture['bit'],1.2,c),reference_at_capture_V=capture['ref'])
            if kind=='functional':r['expected_bit']=int(capture['ref']<c['reference_V'])
            elif k==5 and abs(setting['offset_s'])>=5e-9:
                after=setting['offset_s']<0;r['expected_bit']=int(setting['up'] if after else not setting['up'])
            reads.append(r);current=bit
        if current is not None and row['time']<c['deterministic_stop_s']-1e-12 and phase<=round(.8*c['period_s']/step):
            hold_bad+=int(not valid(row,c));hold_changes+=int(int(row['q']>.6)!=current)
    if len(reads)!=18:raise ValueError('Missing deterministic sample cycles')
    wrong=[r for r in reads if 'expected_bit' in r and (not r['read_valid'] or r['bit']!=r['expected_bit'])]
    critical=next((r for r in reads if r['cycle']==5),None)
    return dict(reads=reads,read_invalid=sum(not r['read_valid'] for r in reads),wrong_known_stable_inputs=len(wrong),
        hold_invalid_saved_points=hold_bad,hold_changed_saved_points=hold_changes,critical_cycle=critical,
        required_gate=(kind=='functional' or abs(setting['offset_s'])>=5e-9),
        hold_check_resolution_s=step,note='Near-edge unit stress is diagnostic, not a proof of rare metastability failure rate.')

def trace(path,c,p,folder=None):
    scan.complete_psf(path)
    stride=round(c['period_s']/p['strobe_s']);start=round(p['start_s']/p['strobe_s']);total=p['samples']*stride
    assert round(c['read_delay_s']/p['strobe_s'])==1
    raw=[];previous=None;current=None;bad_hold=changed_hold=0
    comparator_bits=[]
    for j,row in enumerate(parser.checked_trace(path,p['stop_s'],p['strobe_s'],['out','bit','q','qb','track'])):
        rel=j-start
        if 0<=rel<total:
            comparator_bits.append(int(row['bit']>.6));phase=rel%stride
            if phase==0:
                if previous is None:raise ValueError('Missing capture-edge sample')
                expected=p['start_s']+len(raw)*c['period_s']
                if abs(row['time']-expected)>1e-12:raise ValueError('Wrong read timestamp')
                if row['track']>.12:raise ValueError('Read occurred in transparent phase')
                level=m.logic_level(row['q'],1.2,c);ok=valid(row,c);current=int(row['q']>.6)
                raw.append(dict(raw_index=len(raw),sample_edge_s=previous['time'],time_s=row['time'],
                    core_V_at_capture=previous['out'],comparator_V_at_capture=previous['bit'],
                    capture_level=m.logic_level(previous['bit'],1.2,c),core_V_at_read=row['out'],comparator_V_at_read=row['bit'],
                    q_V=row['q'],qb_V=row['qb'],bit=current,level=level,level_valid=ok))
            if phase<=round(.8*c['period_s']/p['strobe_s']):
                bad_hold+=int(not valid(row,c));changed_hold+=int(int(row['q']>.6)!=current)
        previous=row
    if len(raw)!=p['samples']:raise ValueError('Wrong timed sample count')
    bits=[r['bit'] for r in raw]
    quality=m.bit_statistics(raw,dict(c,sample_interval_s=c['period_s']),p['start_s'],p['samples']*c['period_s'])
    result=dict(actual_samples=len(raw),P1=sum(bits)/float(len(bits)),invalid_Q=sum(not r['level_valid'] for r in raw),
        Q_MID=sum(r['level']=='MID' for r in raw),capture_MID=sum(r['capture_level']=='MID' for r in raw),
        hold_invalid_saved_points=bad_hold,hold_changed_saved_points=changed_hold,
        acf={str(k):m.lagged(bits,k) for k in c['lag_samples']},
        comparator_dense_acf_us={str(us):m.lagged(comparator_bits,round(us*1e-6/p['strobe_s'])) for us in [.1,.5,1,2,5]},
        hold_check_resolution_s=p['strobe_s'],capture_policy='All captures, including comparatorMID, kept; validity comes from actual latchedQ/Qbar.')
    if folder:
        folder=Path(folder);m.write_csv(folder/'sampled_1us.csv',list(raw[0]),raw)
        with (folder/'sampled_1us_bits.txt').open('w',encoding='ascii',newline='\n') as f:
            for r in raw:f.write(str(r['bit'])+'\n')
        vn,pairs=m.von_neumann(raw)
        m.write_csv(folder/'vn_pairs.csv',list(pairs[0]),pairs)
        if vn:m.write_csv(folder/'vn_all_emitted.csv',list(vn[0]),vn)
        # Do not turn failed Q observations into a claimed valid hardware stream.
        quality=dict(raw=quality,vn_all=m.bit_statistics(vn,dict(c,sample_interval_s=c['period_s']),p['start_s'],p['samples']*c['period_s']),
            vn_retention_per_raw=len(vn)/float(len(raw)),seed_packets={},readout_pass=result['invalid_Q']==0 and bad_hold==0 and changed_hold==0,
            conditioning_policy='All Q threshold bits and invalid flags retained; no valid-only filtering or analog capture-level oracle.',physical_entropy_certified=False)
        for label,rows in [('raw',raw),('vn_all',vn)]:
            words=m.words32(rows);quality['seed_packets'][label]=dict(lfsr32=m.packet_statistics(words,32,1),bivium177=m.packet_statistics(words,177,6))
            if words:m.write_csv(folder/(label+'_words32.csv'),list(words[0]),words)
        e.write_json(folder/'quality.json',quality)
    return result

def screen(rows,c):
    groups={tag:{r['setting']['q']['seed']:r['metrics'] for r in rows if r['setting']['tag']==tag} for tag in ['base','fine','wide']}
    differences=[]
    for a,b in [('base','fine'),('fine','wide')]:
        each=[]
        for seed in c['numeric_seeds']:
            x,y=groups[a][seed],groups[b][seed]
            each.append(dict(seed=seed,P1=abs(x['P1']-y['P1']),ACF=max(abs(x['acf'][k]['correlation']-y['acf'][k]['correlation']) for k in x['acf'])))
        differences.append(dict(left=a,right=b,seeds=each,mean_P1=statistics.mean(r['P1'] for r in each),mean_ACF=statistics.mean(r['ACF'] for r in each)))
    rails=all(r['metrics']['invalid_Q']==0 and r['metrics']['hold_invalid_saved_points']==0 and r['metrics']['hold_changed_saved_points']==0 for r in rows)
    ok=rails and all(d['mean_P1']<=c['numeric_mean_P1_tolerance'] and d['mean_ACF']<=c['numeric_mean_ACF_tolerance'] for d in differences)
    return dict(passed=ok,all_short_readouts_valid=rails,comparisons=differences,note='Finite short engineering screen, not strict bandwidth convergence or entropy qualification.')
