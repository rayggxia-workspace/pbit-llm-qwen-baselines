"""Reproducible CACTI exploration; no foundry-SS or output-hold claims.

Each CACTI instance is a single independent 1RW bank. Replication is explicit;
UCA bank count is NOT treated as a free multiplier of external bandwidth.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path


def designs():
    # Same 36,864 simultaneously visible bits and 32 weight tiles throughout.
    out=[]
    for width in (144,512,1024,2048):
        out.append(dict(name='local_w'+str(width),role='local_weight',
            bytes=32*width//8,width=width,replicas=36864//width))
    # Independent banks: 16 MiB weight cache, 1 MiB scratchpad.
    for role,total in (('weight_cache',16*2**20),('scratchpad',2**20)):
        for count in (8,16):
            out.append(dict(name=role+'_b'+str(count),role=role,
                bytes=total//count,width=512,replicas=count))
    return out


def config(template,d):
    changes={'-size (bytes)':str(d['bytes']),'-block size (bytes)':str(d['width']//8),
        '-associativity':'1','-UCA bank count':'1','-technology (u)':'0.055',
        '-output/input bus width':str(d['width']),'-operating temperature (K)':'400',
        '-cache type':'"ram"','-Data array cell type -':'"itrs-lstp"',
        '-Data array peripheral type -':'"itrs-lstp"','-Add ECC -':'"false"',
        '-Print level (DETAILED, CONCISE) -':'"CONCISE"',
        '-Optimize ED or ED^2 (ED, ED^2, NONE):':'"NONE"',
        '-design objective (weight delay, dynamic power, leakage power, cycle time, area)':'0:25:25:0:50',
        '-deviate (delay, dynamic power, leakage power, cycle time, area)':'100000:100000:100000:100000:100000'}
    lines=[];seen=set()
    for line in template.splitlines():
        for key,value in changes.items():
            if line.startswith(key+' '):
                line=key+' '+value;seen.add(key);break
        lines.append(line)
    if set(changes)!=seen:raise ValueError('template keys missing: '+str(set(changes)-seen))
    return '\n'.join(lines)+'\n'


def parse(output):
    number=r'([0-9.eE+\-]+)'
    def get(label):
        match=re.search(re.escape(label)+r'\s*'+number,output)
        if not match:raise ValueError('missing '+label)
        value=float(match.group(1))
        if not math.isfinite(value) or value<0:raise ValueError('invalid '+label)
        return value
    dims=re.search(r'Cache height x width \(mm\):\s*'+number+r'\s*x\s*'+number,output)
    if not dims:raise ValueError('missing area dimensions')
    return dict(access_ns=get('Access time (ns):'),cycle_ns=get('Cycle time (ns):'),
        read_pJ=1000*get('Total dynamic read energy per access (nJ):'),
        write_pJ=1000*get('Total dynamic write energy per access (nJ):'),
        leakage_W=.001*(get('Total leakage power of a bank (mW):')+
            get('Total gate leakage power of a bank (mW):')),
        area_mm2=float(dims.group(1))*float(dims.group(2)))


def summarize(d,p):
    n=d['replicas'];word=d['width']/8
    # 100 MHz service, round up model cycle rather than assert it meets 10 ns.
    interval=max(1,math.ceil(p['cycle_ns']/10))*10
    return dict(**d,**p,status='analytical_not_foundry_SS',total_bytes=n*d['bytes'],
        total_area_mm2=n*p['area_mm2'],total_leakage_W=n*p['leakage_W'],
        all_banks_read_pJ=n*p['read_pJ'],all_banks_write_pJ=n*p['write_pJ'],
        issue_interval_ns=interval,parallel_peak_GBs=n*word/interval,
        read_pJ_per_byte=p['read_pJ']/word,write_pJ_per_byte=p['write_pJ']/word,
        output_hold_supported='UNCHARACTERIZED: CACTI does not prove Q hold',
        cross_bank_interconnect='not included')


def overrides(row):
    """Costs only: preserve existing bandwidth/latency until bank mapping exists."""
    if row['role'] not in ('weight_cache','scratchpad'):raise ValueError('local Q hold needs explicit implementation')
    mib=row['total_bytes']/2**20
    key='weight_macro' if row['role']=='weight_cache' else 'scratchpad'
    return {key:dict(read_pJ_per_byte=row['read_pJ_per_byte'],
        write_pJ_per_byte=row['write_pJ_per_byte'],
        leakage_W_per_MiB=row['total_leakage_W']/mib,
        area_mm2_per_MiB=row['total_area_mm2']/mib)}


def apply_cost_profile(cfg,profile):
    for key,values in profile['overrides'].items():
        if key not in ('weight_macro','scratchpad'):raise ValueError(key)
        expected=16 if key=='weight_macro' else 1
        actual=cfg[key]['cache_MiB' if key=='weight_macro' else 'capacity_MiB']
        if actual!=expected:raise ValueError('CACTI profile capacity mismatch')
        cfg[key].update(values)
    cfg['memory_cost_provenance']=profile['provenance']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--generate-only',action='store_true')
    ap.add_argument('--designs',type=Path,help='JSON list: name, role, bytes per bank, width bits, independent replicas')
    args=ap.parse_args();source=args.source.resolve();dest=args.output.resolve()
    dest.mkdir(parents=True,exist_ok=True)
    template=(source/'cache.cfg').read_text();rows=[]
    cases=json.loads(args.designs.read_text()) if args.designs else designs()
    for d in cases:
        if (d['bytes']<=0 or d['width']<=0 or d['width']%8 or d['replicas']<=0
                or d['bytes']%(d['width']//8)):
            raise ValueError('invalid capacity/word/replica specification')
        cfg=dest/(d['name']+'.cfg');cfg.write_text(config(template,d))
        if args.generate_only:continue
        try:
            p=subprocess.run([str(source/'cacti'),'-infile',str(cfg)],cwd=str(source),
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=180)
            (dest/(d['name']+'.log')).write_text(p.stdout)
            if p.returncode:raise ValueError('CACTI exit '+str(p.returncode))
            row=summarize(d,parse(p.stdout))
        except (ValueError,subprocess.TimeoutExpired) as e:
            row=dict(**d,status='FAILED',error=str(e))
        rows.append(row);print(json.dumps(row),flush=True)
    provenance=dict(tool='HewlettPackard/CACTI 7',technology_nm=55,temperature_K=400,
        device='ITRS LSTP, interpolated technology; NOT ZJCX SS/1.08V/125C',
        source_url='https://github.com/HewlettPackard/cacti',
        source_hashes={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(source.rglob('*')) if p.is_file() and p.suffix in ('.cc','.h','.dat')},
        scope='independent 1RW banks; no cross-bank wiring, no Q hold validation; no per-weight flags',
        integration='costs only; preserve TLM timing, local tile holds and ordinary control')
    if args.generate_only:return
    (dest/'results.json').write_text(json.dumps(dict(provenance=provenance,rows=rows),indent=2)+'\n')
    if rows:
        keys=list(dict.fromkeys(k for r in rows for k in r))
        with (dest/'summary.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    for n in (8,16):
        picked=[r for r in rows if r['name'] in ('weight_cache_b'+str(n),'scratchpad_b'+str(n))]
        if len(picked)==2 and all(r['status']!='FAILED' for r in picked):
            patch={}
            for r in picked:patch.update(overrides(r))
            (dest/('tlm_cost_b'+str(n)+'.json')).write_text(json.dumps(
                dict(provenance=provenance,overrides=patch),indent=2)+'\n')


if __name__=='__main__':main()
