"""Slurm-side numeric audit and private, recoverable original-byte archives."""
import hashlib
import json
import os
from pathlib import Path
import re
import tarfile

ROOT=Path(os.environ['AC_RUN_ROOT'])

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode())
def value(pattern,text):
    m=re.search(pattern,text,re.M);assert m,pattern
    return float(m.group(1))
def archive(path,files):
    assert not path.exists(),path
    with tarfile.open(str(path),'w:gz') as t:
        for p in files:t.add(str(p),arcname=str(p.relative_to(ROOT)),recursive=False)
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha(path))

def main():
    dest=ROOT/'collection_v1';dest.mkdir(exist_ok=False)
    specs=read(ROOT/'snapshots/v1/CASES.json')['tops']
    traces=read(ROOT/'snapshots/v1/vectors/TRACES.json')
    results=[];files=[]
    for spec in specs:
        top=spec['top']
        dc=[p.parent for p in (ROOT/'results').glob('*_dc_'+top+'/SYNTHESIS_COMPLETE.txt')]
        replay=[p.parent for p in (ROOT/'results').glob('*_replay_'+top+'/STATUS.json')]
        assert len(dc)==len(replay)==1,(top,dc,replay)
        dc,replay=dc[0],replay[0];v=read(replay/'VALIDATION.json')
        assert v['status']=='pass'
        assert sha(dc/'mapped.v')==v['dc_netlist_sha256'] and sha(dc/'mapped.sdc')==v['dc_sdc_sha256']
        q=(dc/'qor.rpt').read_text();area=value(r'^\s*Cell Area:\s+([0-9.]+)',q)
        checks=v['checks'];assert all(x['status']=='pass' for x in checks)
        rows=[]
        for item in v['power_windows']:
            p=replay/item['directory'];report=(p/'power.rpt').read_text();log=(p/'pt.log').read_text()
            assert (p/'POWER_COMPLETE.txt').exists()
            assert re.search(r'Dynamic Power Units\s*=\s*1 W',report)
            assert re.search(r'Leakage Power Units\s*=\s*1 W',report)
            powers={key:value(pattern,report) for key,pattern in dict(total_W=r'^Total Power\s*=\s*([0-9.eE+-]+)',
                 switching_W=r'Net Switching Power\s*=\s*([0-9.eE+-]+)',internal_W=r'Cell Internal Power\s*=\s*([0-9.eE+-]+)',
                 leakage_W=r'Cell Leakage Power\s*=\s*([0-9.eE+-]+)').items()}
            assert abs(powers['total_W']-sum(powers[k] for k in ['switching_W','internal_W','leakage_W']))<max(1e-8,powers['total_W']*.005)
            net_pct=value(r'Number of annotated nets\s*=.*?\(([0-9.]+)%\)',log)
            cell_pct=value(r'Number of fully annotated leaf cells\s*=.*?\(([0-9.]+)%\)',log)
            assert net_pct==cell_pct==100.0,(top,item['trace'],net_pct,cell_pct)
            window=item['window'];duration=window['end_ns']-window['start_ns'];assert duration>0
            directory=ROOT/'snapshots/v1/vectors'/top/item['trace']
            trace_meta=next(t for t in traces[top] if t['trace']==item['trace'])
            stim=[[int(z,16) for z in line.split()] for line in (directory/'vectors.txt').read_text().splitlines()]
            golden=[line.split() for line in (directory/'golden.log').read_text().splitlines() if line.startswith('P ')]
            outputs=sum(int(row[7]) and bool(x[-1]) for i,(row,x) in enumerate(zip(golden,stim))
                        if window['start_ns']<=15+10*i<window['end_ns'])
            assert outputs==window['outputs'],(top,item['trace'],outputs,window)
            warnings={code:len(re.findall(re.escape(code),log)) for code in sorted(set(re.findall(r'\((PWR-[0-9]+|PTE-[0-9]+)\)',log)))}
            rows.append(dict(trace=item['trace'],window=window,metrics=trace_meta.get('metrics'),power=powers,duration_ns=duration,
                observed_output_handshakes=outputs,window_energy_J=powers['total_W']*duration*1e-9,
                energy_per_output_J=powers['total_W']*duration*1e-9/outputs if outputs else None,
                slack=item['slack'],annotated_nets_pct=net_pct,fully_annotated_cells_pct=cell_pct,
                warnings=warnings,power_report_sha256=sha(p/'power.rpt'),activity_report_sha256=sha(p/'activity.rpt'),
                note='zero-delay gate VCD, averaged prelayout; clock-pin internal included once; hold violations retained'))
        results.append(dict(spec=spec,raw_cell_area_um2=area,area_scale=.81,area_55nm_equivalent_um2=area*.81,
            leaf_cells=int(value(r'Leaf Cell Count:\s+([0-9.]+)',q)),functional_checks=checks,power_windows=rows,
            dc_job=dc.name.split('_')[0],replay_job=replay.name.split('_')[0],netlist_sha256=sha(dc/'mapped.v'),
            sdc_sha256=sha(dc/'mapped.sdc'),functional_trace_metrics=[dict(trace=t['trace'],metrics=t.get('metrics'),coverage=t.get('coverage')) for t in traces[top]],functional_cycles=sum(x['cycles'] for x in checks),
            setup_ns=min(x['slack']['setup_ns'] for x in rows),hold_ns=min(x['slack']['hold_ns'] for x in rows)))
    assert len(results)==8 and sum(len(x['power_windows']) for x in results)==56
    assert sum(len(x['functional_checks']) for x in results)==336
    write(dest/'RESULTS.json',dict(status='calculated_with_timing_violations_and_annotation_warnings',
        conditions=dict(corner='SS',voltage_V=1.08,temperature_C=125,frequency_MHz=100,
           raw_geometry='user-specified SHARK unshrunk geometry',target_area_nm=55,area_only_scale=.81,
           setup_uncertainty_ns=2,hold_uncertainty_ns=.1,input_transition_ns=.1,output_load_pF=.02,
           io_delay_ns=0,sdf=False,spef=False,cts=False,glitch_activity='zero-delay, not full delayed glitch power'),
        results=results,source_manifest_sha256={v:sha(ROOT/('snapshots/'+v+'/SOURCE.json')) for v in ['v1']},
        private_models_sha256=read(list((ROOT/'results').glob('*_replay_*/VALIDATION.json'))[0])['models_sha256'],
        limitations=['all baseline hold violations preserved; not timing signoff',
          'PWR-981 partial vector mapping warnings retained despite 100% net/cell coverage',
          'no RNG/comparator/config-reencoding/QK/V/SRAM/output-accumulator power',
          'partial-query stress output handshake energy is diagnostic, not successful-query quality energy']))
    # Do not archive simulator executables, tool installations or private libraries.
    for p in (ROOT/'results').rglob('*'):
        if p.is_file() and p.suffix in ('.rpt','.log','.json','.txt','.v','.vg','.sdc','.ddc','.svf','.vcd'):
            if any(x.startswith('build_') for x in p.relative_to(ROOT/'results').parts) and p.name!='compile.log':continue
            files.append(p)
    files += [p for p in (ROOT/'snapshots').rglob('*') if p.is_file()]
    files += list(ROOT.glob('SUBMIT*.json'))+[dest/'RESULTS.json']
    files=sorted(set(files))
    index={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in files}
    write(dest/'RAW_INDEX.json',dict(root=str(ROOT),files=index))
    files.append(dest/'RAW_INDEX.json')
    raw=archive(dest/'EDA_RAW.tar.gz',files)
    reports=archive(dest/'EDA_REPORTS.tar.gz',[p for p in files if p.suffix not in ('.vcd','.v','.vg','.ddc','.svf')])
    write(dest/'COLLECTION.json',dict(raw=raw,reports=reports,original_files=len(index),source_sha256=sha(Path(__file__)),
         results_sha256=sha(dest/'RESULTS.json'),raw_index_sha256=sha(dest/'RAW_INDEX.json')))
    print(json.dumps(read(dest/'COLLECTION.json')))

if __name__=='__main__':main()
