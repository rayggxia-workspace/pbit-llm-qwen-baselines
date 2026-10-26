"""Per-record statistics and timestamped bit/seed artifacts; no entropy claim."""
import bisect
import csv
import math
from pathlib import Path
from array import array
import common
from measurements import Moments
import run_characterization as old
import scan_measurements as scan


def corr(a,b):
    n=len(a)
    if n<2:return dict(pairs=n,correlation=None)
    ma=sum(a)/float(n);mb=sum(b)/float(n)
    xx=sum((x-ma)**2 for x in a);yy=sum((x-mb)**2 for x in b)
    rho=sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(xx*yy) if xx>0 and yy>0 else None
    return dict(pairs=n,correlation=rho,
                nominal_iid_95_reference=1.96/math.sqrt(n),
                uncertainty_note='IID reference only, not a confidence interval for a correlated process')


def lagged(values,lag):
    return corr(values[:-lag],values[lag:]) if lag<len(values) else dict(pairs=0,correlation=None)


def distribution(values,grid):
    n=len(values)
    if not n:return dict(n=0,mean_V=None,std_V=None,quantiles_V=[],cdf_grid_V=grid,cdf=[])
    moments=Moments()
    for x in values:moments.add(x)
    ordered=sorted(values)
    qs=[]
    for p in [.01,.1,.25,.5,.75,.9,.99]:
        f=p*(n-1);i=int(f);qs.append(ordered[i]+(ordered[min(i+1,n-1)]-ordered[i])*(f-i))
    return dict(n=n,mean_V=moments.mean,std_V=math.sqrt(moments.variance() or 0),
                quantile_probabilities=[.01,.1,.25,.5,.75,.9,.99],quantiles_V=qs,
                cdf_grid_V=grid,cdf=[bisect.bisect_right(ordered,x)/float(n) for x in grid])


def logic_level(voltage,rail,c):
    if not -.05<=voltage<=rail+.05:return 'OUT_OF_RAIL'
    if voltage<=c['logic_low_fraction']*rail+1e-12:return 'LOW'
    if voltage>=c['logic_high_fraction']*rail-1e-12:return 'HIGH'
    return 'MID'


def wave(path,q,rail,c,include_sense=False):
    scan.complete_psf(path)
    fields=['out','bit']+(['sense'] if include_sense else [])
    values={key:array('d') for key in fields};saved=0
    for row in old.checked_trace(path,q['stop_s'],q['strobe_s'],fields):
        if q['discard_s']-1e-12<=row['time']<q['stop_s']-1e-12:
            for key in fields:values[key].append(row[key])
        saved+=1
    n=len(values['bit']);expected=int(round((q['stop_s']-q['discard_s'])/q['strobe_s']))
    if n!=expected:raise ValueError('Incomplete effective saved record')
    bits=[int(v>.5*rail) for v in values['bit']]
    levels=[logic_level(v,rail,c) for v in values['bit']]
    result=dict(saved_points=saved,effective_saved_points=n,p1=sum(bits)/float(n),
                midrail_fraction=levels.count('MID')/float(n),out_of_rail_count=levels.count('OUT_OF_RAIL'),
                core_distribution=distribution(values['out'],[.4+i*.002 for i in range(201)]),
                comparator_distribution=distribution(values['bit'],[-.05+i*.005 for i in range(181)]),
                dense_bit_acf={})
    for interval in [1e-7,5e-7,1e-6,2e-6,5e-6,1e-5,1e-4]:
        k=int(round(interval/q['strobe_s']))
        if k>0 and abs(k*q['strobe_s']-interval)<1e-12:result['dense_bit_acf'][str(interval)]=lagged(bits,k)
    if include_sense:result['sense_distribution']=distribution(values['sense'],[])
    return result


def write_csv(path,fieldnames,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,lineterminator='\n');w.writeheader();w.writerows(rows)


def bit_statistics(rows,c,start,duration):
    bits=[r['bit'] for r in rows];n=len(bits)
    result=dict(bits=n,p1=sum(bits)/float(n) if n else None,
                bias_from_half=sum(bits)/float(n)-.5 if n else None,
                invalid_level_bits=sum(not r['level_valid'] for r in rows),
                sequence_lag_acf={},physical_time_lag_acf={},blocks={})
    for lag in c['lag_samples']:
        d=lagged(bits,lag)
        gaps=[rows[i+lag]['time_s']-rows[i]['time_s'] for i in range(max(0,n-lag))]
        d['elapsed_s_range']=[min(gaps),max(gaps)] if gaps else None
        result['sequence_lag_acf'][str(lag)]=d
        by_index={r['raw_index']:r['bit'] for r in rows}
        a=[];b=[]
        for r in rows:
            if r['raw_index']+lag in by_index:a.append(r['bit']);b.append(by_index[r['raw_index']+lag])
        result['physical_time_lag_acf'][str(lag*c['sample_interval_s'])]=corr(a,b)
    for width in c['block_durations_s']:
        count=int(round(duration/width));groups=[[] for _ in range(count)]
        for r in rows:
            index=int(math.floor((r['time_s']-start+1e-12)/width))
            if 0<=index<count:groups[index].append(r)
        result['blocks'][str(width)]=[dict(start_s=start+i*width,end_s=start+(i+1)*width,
            n=len(g),p1=sum(r['bit'] for r in g)/float(len(g)) if g else None,
            invalid_level_bits=sum(not r['level_valid'] for r in g)) for i,g in enumerate(groups)]
    if n>1:
        gaps=sorted(rows[i+1]['time_s']-rows[i]['time_s'] for i in range(n-1))
        result['arrival_gap_s']=dict(min=gaps[0],median=gaps[len(gaps)//2],max=gaps[-1])
    result['interpretation']='Descriptive per-seed statistics, no IID/entropy/crypto certification; VN sequence lag is not a uniform time lag'
    return result


def von_neumann(raw):
    emitted=[];pairlog=[]
    for i in range(0,len(raw)-1,2):
        a,b=raw[i:i+2];valid=a['level_valid'] and b['level_valid'];different=a['bit']!=b['bit']
        row=dict(pair_index=i//2,first_raw_index=a['raw_index'],second_raw_index=b['raw_index'],
                 first_time_s=a['time_s'],time_s=b['time_s'],pair=str(a['bit'])+str(b['bit']),
                 level_valid=valid,emitted=int(different),reason='INVALID_LEVEL' if not valid else 'EMIT' if different else 'EQUAL')
        pairlog.append(row)
        if different:emitted.append(dict(raw_index=b['raw_index'],time_s=b['time_s'],bit=a['bit'],level_valid=valid,
                                        first_raw_index=a['raw_index'],pair_index=i//2))
    return emitted,pairlog


def words32(rows):
    words=[]
    for i in range(0,len(rows)-31,32):
        part=rows[i:i+32]
        words.append(dict(word=sum(r['bit']<<k for k,r in enumerate(part)),start_s=part[0]['time_s'],
                          available_s=part[-1]['time_s'],level_valid=all(r['level_valid'] for r in part),
                          first_raw_index=part[0]['raw_index'],last_raw_index=part[-1]['raw_index']))
    return words


def packet_statistics(words,width,beats):
    packets=[]
    for i in range(0,len(words)-beats+1,beats):
        part=words[i:i+beats];value=sum(w['word']<<(32*j) for j,w in enumerate(part))&((1<<width)-1)
        packets.append(dict(value=value,available_s=part[-1]['available_s'],level_valid=all(w['level_valid'] for w in part)))
    values=[p['value'] for p in packets];n=len(values)
    distances=[bin(a^b).count('1') for a,b in zip(values,values[1:])]
    result=dict(state_width_bits=width,bus_beats_per_packet=beats,padding_bits_discarded=32*beats-width,
        complete_packets=n,unused_partial_words=len(words)%beats,zero_state_packets=values.count(0),
        invalid_level_packets=sum(not p['level_valid'] for p in packets),
        adjacent_repeat_count=sum(a==b for a,b in zip(values,values[1:])),
        repeated_packet_occurrences=n-len(set(values)),
        adjacent_hamming_histogram=[distances.count(k) for k in range(width+1)],
        adjacent_hamming_mean=sum(distances)/float(len(distances)) if distances else None,
        corresponding_bit_lag1=[dict(bit=k,**corr([(x>>k)&1 for x in values[:-1]],[(x>>k)&1 for x in values[1:]])) for k in range(width)],
        packet_completion_times_s=[p['available_s'] for p in packets],
        note='Includes zero/invalid diagnostic packets, does not select good seeds; transport trace eligibility is explicit, not an entropy claim')
    return result


def long_record(path,folder,q,rail,c,provenance):
    scan.complete_psf(path);raw=[];stride=int(round(c['sample_interval_s']/q['strobe_s']))
    if stride!=10 or abs(stride*q['strobe_s']-c['sample_interval_s'])>1e-12:raise ValueError('Require every tenth exact 10us strobe')
    start_index=int(round(q['discard_s']/q['strobe_s']));effective=int(round((q['stop_s']-q['discard_s'])/q['strobe_s']))
    for j,r in enumerate(old.checked_trace(path,q['stop_s'],q['strobe_s'],['out','bit'])):
        rel=j-start_index
        if 0<=rel<effective and rel%stride==0:
            level=logic_level(r['bit'],rail,c)
            raw.append(dict(raw_index=rel//stride,time_s=r['time'],core_V=r['out'],comparator_V=r['bit'],
                            bit=int(r['bit']>.5*rail),level=level,level_valid=level in ['LOW','HIGH']))
    expected=int(round((q['stop_s']-q['discard_s'])/c['sample_interval_s']))
    if len(raw)!=expected:raise ValueError('Wrong 100us sample count')
    for i,r in enumerate(raw):
        if abs(r['time_s']-(q['discard_s']+i*c['sample_interval_s']))>1e-12:raise ValueError('Sample timestamp mismatch')
    folder=Path(folder)
    write_csv(folder/'raw_100us.csv',['raw_index','time_s','core_V','comparator_V','bit','level','level_valid'],raw)
    vn,pairs=von_neumann(raw);eligible=[r for r in vn if r['level_valid']]
    write_csv(folder/'vn_pairs.csv',['pair_index','first_raw_index','second_raw_index','first_time_s','time_s','pair','level_valid','emitted','reason'],pairs)
    write_csv(folder/'vn_all_emitted.csv',['raw_index','time_s','bit','level_valid','first_raw_index','pair_index'],vn)
    duration=q['stop_s']-q['discard_s'];result=dict(effective_duration_s=duration,actual_sample_interval_s=c['sample_interval_s'],
        expected_raw_bits=expected,raw=bit_statistics(raw,c,q['discard_s'],duration),
        vn_all_threshold_outputs=bit_statistics(vn,c,q['discard_s'],duration),
        vn_valid_level_outputs=bit_statistics(eligible,c,q['discard_s'],duration),
        vn_policy='Nonoverlap (0,1),(2,3)...; 01->0,10->1, equal pairs discarded. Raw decisions retained even if MID. Invalid emitted bits retained in diagnostic CSV, excluded explicitly from VN transport.',
        vn_pair_count=len(pairs),vn_pairs_invalid_level=sum(not r['level_valid'] for r in pairs),
        vn_retained_bits_per_raw_bit=len(eligible)/float(len(raw)) if raw else None,
        vn_hardware_valid_selection_can_bias=True,unused_trailing_raw_bit=len(raw)%2,seed_packets={})
    for name,rows in [('raw',raw),('vn',eligible)]:
        words=words32(rows)
        write_csv(folder/(name+'_seed_words.csv'),['word','start_s','available_s','level_valid','first_raw_index','last_raw_index'],words)
        result['seed_packets'][name]=dict(words32=len(words),unused_partial_bits=len(rows)%32,
            lfsr32=packet_statistics(words,32,1),bivium177=packet_statistics(words,177,6))
        common.save(folder/(name+'_seed_trace.json'),dict(format='timestamped_simulation_seed_words_v1',
            provenance=provenance,physical_entropy_certified=False,entropy_per_word_bits=None,
            bit_order='earliest bit is LSB; earliest 32bit word is least significant bus beat',
            eligibility_note='level_valid only checks readout rails, not entropy. Adapter refuses false flags; no hidden deletion in raw sequence.',
            words=words))
    common.save(folder/'quality.json',result)
    return result
