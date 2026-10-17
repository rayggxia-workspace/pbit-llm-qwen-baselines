"""Foundry macro lookup + held-out CACTI residual calibration, not PVT signoff.

A-F fit/model selection only; H is evaluated after all choices are frozen.
The energy targets are MACRO INTERNAL event energy, not CACTI full-access energy.
"""
import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
from cacti_memory import config as cacti_config,parse as cacti_parse

ROOT=Path(__file__).resolve().parent
TRAIN=list('ABCDEF')
METRICS={
    'area_mm2':('area_um2','area_mm2',1e-6),
    'read_internal_pJ':('Eread_internal_pJ','read_pJ',1),
    'write_internal_pJ':('Ewrite_internal_pJ','write_pJ',1),
    'ce_off_leakage_W':('leakage_ce_off_uW','leakage_W',1e-6),
    'ce_on_leakage_W':('leakage_ce_on_uW','leakage_W',1e-6),
    'read_access_ns':('read_clk_to_q_max_ns','access_ns',1),
    'write_access_ns':('write_clk_to_q_max_ns','access_ns',1),
    'read_cycle_ns':('minimum_read_period_ns','cycle_ns',1),
    'write_cycle_ns':('minimum_write_period_ns','cycle_ns',1),
}


def read_csv(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def prepare(data_dir,raw_root,out):
    manifest=read_csv(data_dir/'manifest.csv');summary=read_csv(data_dir/'macro_summary.csv')
    points=[];files=[]
    for m in manifest:
        if m['status']=='FAILED':
            if m['id']!='G':raise ValueError('unexpected failed geometry')
            continue
        if (m['port_type']!='1RW' or m['mux']!='4' or m['vt_actual']!='RVT' or
                m['power_gating']!='Without Power Gating'):raise ValueError('structure mismatch')
        expected=json.loads(m['sha256s'])
        for kind in ('lib','ds','lef','verilog'):
            p=(raw_root/m[kind+'_path']).resolve();p.relative_to(raw_root.resolve())
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            if h!=expected[kind]:raise ValueError('hash mismatch '+str(p))
            files.append(dict(path=m[kind+'_path'],sha256=h))
        matches=[r for r in summary if r['id']==m['id'] and r['corner'].upper()==m['compiler_corner'] and
            float(r['clock_slew_ns'])==.1 and float(r['output_load_pF'])==.02]
        if len(matches)!=1:raise ValueError('representative point mismatch '+m['id'])
        r=matches[0];D=int(m['actual_depth']);W=int(m['actual_word_bits'])
        if D*W!=int(m['capacity_bits']):raise ValueError('capacity mismatch')
        target={k:float(r[f])*scale for k,(f,_,scale) in METRICS.items()}
        if not all(v>0 and math.isfinite(v) for v in target.values()):raise ValueError('bad target')
        points.append(dict(id=m['id'],corner=m['corner'],depth=D,width=W,bytes=D*W//8,
            role='train' if m['id'] in TRAIN else 'held_out',voltage_V=float(m['voltage_V']),
            temperature_C=float(m['temperature_C']),target=target,source_status=m['status']))
    assert len(points)==14 and len(files)==56
    for i in list('ABCDEFH'):
        a=[p for p in points if p['id']==i];assert len(a)==2
        assert a[0]['target']['area_mm2']==a[1]['target']['area_mm2']
    result=dict(schema=1,train_ids=TRAIN,held_out_ids=['H'],missing_ids=['G'],points=points,
        family='TMHDSPZ055ABA_v0.1_mux4_RVT_lpwr0_1RW',
        target_slew_ns=.1,target_Q_load_pF=.02,
        verified_vendor_files=files,verified_file_count=len(files),
        input_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (data_dir/'manifest.csv',data_dir/'macro_summary.csv')})
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    return result


def run_cacti(points_file,source,out):
    source=source.resolve();out.mkdir(parents=True,exist_ok=True)
    dataset=json.loads(points_file.read_text());template=(source/'cache.cfg').read_text();rows=[]
    for p in dataset['points']:
        name=p['id']+'_'+p['corner'];t=300 if p['corner']=='TT' else 400
        text=cacti_config(template,dict(bytes=p['bytes'],width=p['width']))
        text=text.replace('-operating temperature (K) 400','-operating temperature (K) '+str(t))
        cfg=(out/(name+'.cfg')).resolve();cfg.write_text(text)
        process=subprocess.run([str(source/'cacti'),'-infile',str(cfg)],cwd=str(source),
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=180)
        (out/(name+'.log')).write_text(process.stdout)
        if process.returncode:raise RuntimeError(name+': CACTI failed')
        result=cacti_parse(process.stdout)
        row=dict(id=p['id'],corner=p['corner'],depth=p['depth'],width=p['width'],
            proxy_temperature_K=t,raw=result)
        rows.append(row);print(json.dumps(row),flush=True)
    result=dict(rows=rows,reference_sha256=hashlib.sha256(points_file.read_bytes()).hexdigest(),
        proxy_conditions='55nm interpolated ITRS LSTP; TT proxy 300K, SS proxy 400K; native generic voltage',
        note='proxy is not foundry PVT; correction maps outputs to exact target PVT; '
             'CACTI access/write and total dynamic energy are predictors of library-specific target metrics',
        source_hashes={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source.rglob('*')) if p.is_file() and p.suffix in ('.cc','.h','.dat')})
    (out/'raw_cacti.json').write_text(json.dumps(result,indent=2)+'\n')


def features(p,kind):
    x=[1.]
    if kind=='log_geometry_residual':x += [math.log(p['depth']/256),math.log(p['width']/128)]
    return x


def solve(A,b):
    a=[list(row)+[v] for row,v in zip(A,b)];n=len(b)
    for i in range(n):
        pivot=max(range(i,n),key=lambda j:abs(a[j][i]))
        a[i],a[pivot]=a[pivot],a[i]
        if abs(a[i][i])<1e-12:raise ValueError('singular fit')
        v=a[i][i];a[i]=[x/v for x in a[i]]
        for j in range(n):
            if j!=i:
                v=a[j][i];a[j]=[x-v*y for x,y in zip(a[j],a[i])]
    return [row[-1] for row in a]


def coefficients(rows,kind):
    xs=[features(r,kind) for r in rows];ys=[math.log(r['truth']/r['base']) for r in rows]
    n=len(xs[0]);A=[[sum(x[i]*x[j] for x in xs) for j in range(n)] for i in range(n)]
    b=[sum(x[i]*y for x,y in zip(xs,ys)) for i in range(n)]
    return solve(A,b)


def prediction(row,kind,beta):return row['base']*math.exp(sum(x*b for x,b in zip(features(row,kind),beta)))


def fit_metric(rows):
    train=[r for r in rows if r['id'] in TRAIN]
    # Model family and choice procedure fixed before looking at H.
    candidates=[]
    for kind in ('constant_residual','log_geometry_residual'):
        errors=[]
        for j,r in enumerate(train):
            beta=coefficients(train[:j]+train[j+1:],kind)
            errors.append(abs(prediction(r,kind,beta)/r['truth']-1))
        candidates.append(dict(kind=kind,loo_mape=sum(errors)/len(errors),loo_apes=errors))
    selected=min(candidates,key=lambda r:(r['loo_mape'],r['kind']!='constant_residual'))
    beta=coefficients(train,selected['kind'])
    train_apes=[abs(prediction(r,selected['kind'],beta)/r['truth']-1) for r in train]
    # H never enters fit, model selection, normalization, or thresholds.
    held=[r for r in rows if r['id']=='H'];assert len(held)==1
    h=held[0];pred=prediction(h,selected['kind'],beta);ape=abs(pred/h['truth']-1)
    return dict(kind=selected['kind'],coefficients=beta,candidates=candidates,
        train_mape=sum(train_apes)/len(train_apes),loo_mape=selected['loo_mape'],
        H_prediction=pred,H_truth=h['truth'],H_ape=ape,
        H_within_20pct=ape<=.2,note='20% is a reporting band, not a guarantee for unseen sizes')


def fit(reference_file,raw_file,out):
    dataset=json.loads(reference_file.read_text());raw=json.loads(raw_file.read_text())
    if raw['reference_sha256']!=hashlib.sha256(reference_file.read_bytes()).hexdigest():raise ValueError('reference hash mismatch')
    lookup={(r['id'],r['corner']):r for r in raw['rows']};models={};table=[]
    for corner in ('TT','SS'):
        models[corner]={}
        for metric,(_,basekey,_) in METRICS.items():
            rows=[]
            for p in dataset['points']:
                if p['corner']!=corner:continue
                # Physical area is PVT-independent: use same TT proxy for both.
                proxy_corner='TT' if metric=='area_mm2' else corner
                r=lookup[p['id'],proxy_corner]
                if (r['depth'],r['width'])!=(p['depth'],p['width']):raise ValueError('raw geometry mismatch')
                rows.append(dict(id=p['id'],depth=p['depth'],width=p['width'],
                    truth=p['target'][metric],base=r['raw'][basekey]))
            m=fit_metric(rows);models[corner][metric]=m
            raw_h=next(r['base'] for r in rows if r['id']=='H')
            table.append(dict(corner=corner,metric=metric,model=m['kind'],
                train_MAPE_percent=100*m['train_mape'],LOO_MAPE_percent=100*m['loo_mape'],
                H_truth=m['H_truth'],H_raw_CACTI=raw_h,H_prediction=m['H_prediction'],
                H_raw_APE_percent=100*abs(raw_h/m['H_truth']-1),H_APE_percent=100*m['H_ape']))
    result=dict(schema=1,models=models,reference=dataset,raw_cacti=raw,
        calibration_scope='output residual correction; macro-internal energy only; fixed slew .1ns/load .02pF timing',
        selection='A-F only, leave-one-geometry-out MAPE chooses constant vs 3-parameter log residual',
        area_rule='same TT proxy and model for both corners; no area PVT scaling',
        holdout='H used for evaluation only; no model adjustment after viewing H',
        limitations=['single held-out geometry, not statistical accuracy certification','no G or >=128KiB macro validation',
            'no wrapper, Q load dynamic, clock tree, hold behavior, bank conflict or sleep calibration',
            'generic CACTI voltages/temperature proxy are not physical foundry PVT',
            'do not extrapolate to arbitrary widths or MUX families'],
        source_hashes={Path(__file__).name:hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            reference_file.name:hashlib.sha256(reference_file.read_bytes()).hexdigest(),
            raw_file.name:hashlib.sha256(raw_file.read_bytes()).hexdigest()})
    out.mkdir(parents=True,exist_ok=True)
    (out/'calibration.json').write_text(json.dumps(result,indent=2)+'\n')
    with (out/'validation.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    for r in table:print(json.dumps(r),flush=True)
    return result


def macro_lookup(model,depth,width,corner,clock_hz=None):
    matches=[p for p in model['reference']['points'] if
        (p['depth'],p['width'],p['corner'])==(depth,width,corner)]
    if len(matches)!=1:raise ValueError('no exact macro; use predict_unseen with matching CACTI data')
    p=matches[0];d=dict(p['target']);d.update(source='exact_vendor_library',id=p['id'],corner=corner,
        energy_boundary='macro internal dynamic; Q load/clock tree/wrapper excluded',
        Q_hold='not newly verified',slew_ns=.1,Q_load_pF=.02)
    if clock_hz:
        period=1e9/clock_hz;minimum=max(d['read_cycle_ns'],d['write_cycle_ns'])
        d.update(requested_clock_hz=clock_hz,period_only_eligible=period>=minimum,
            minimum_cycle_ns=minimum,clock_note='period screening only; no interface STA guarantee')
    return d


def predict_unseen(model,depth,width,corner,cacti_by_corner,allow_extrapolation=False):
    pts=[p for p in model['reference']['points'] if p['id'] in TRAIN and p['corner']==corner]
    # Bounding rectangle is a necessary bound, not proof every combination is supported.
    inside=(min(p['depth'] for p in pts)<=depth<=max(p['depth'] for p in pts) and
            min(p['width'] for p in pts)<=width<=max(p['width'] for p in pts))
    if not inside and not allow_extrapolation:raise ValueError('outside calibration bounds')
    result={};status={}
    for metric,(_,basekey,_) in METRICS.items():
        m=model['models'][corner][metric];c='TT' if metric=='area_mm2' else corner
        raw=cacti_by_corner[c]
        if (raw['depth'],raw['width'])!=(depth,width):raise ValueError('CACTI proxy geometry mismatch')
        row=dict(depth=depth,width=width,base=raw['raw'][basekey])
        result[metric]=prediction(row,m['kind'],m['coefficients'])
        status[metric]=dict(H_ape=m['H_ape'],LOO_mape=m['loo_mape'])
    return dict(prediction=result,validation=status,source='exploratory_calibrated_CACTI',
        extrapolation=not inside,coverage_note='range check only; macro compiler legality still required',
        Q_hold='unknown',energy_boundary='macro internal dynamic only')


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('prepare');a.add_argument('--data',type=Path,required=True)
    a.add_argument('--raw-root',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('run-cacti');a.add_argument('--reference',type=Path,required=True)
    a.add_argument('--source',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('fit');a.add_argument('--reference',type=Path,required=True)
    a.add_argument('--raw-cacti',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.mode=='prepare':
        d=prepare(args.data,args.raw_root,args.output);print('verified',d['verified_file_count'],'vendor files;',len(d['points']),'points')
    elif args.mode=='run-cacti':run_cacti(args.reference,args.source,args.output)
    else:fit(args.reference,args.raw_cacti,args.output)


if __name__=='__main__':main()
