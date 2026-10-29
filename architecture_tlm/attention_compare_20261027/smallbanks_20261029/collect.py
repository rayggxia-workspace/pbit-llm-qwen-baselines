"""Validate report archive bytes and summarize explicit units/boundaries.

Usage: python collect.py REPORTS.zip OUTPUT_DIRECTORY
"""
import hashlib,json,re,statistics,sys,zipfile
from pathlib import Path

def save(p,x):p.write_bytes((json.dumps(x,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
def sha(b):return hashlib.sha256(b).hexdigest()
def main(archive,out):
    archive=Path(archive);out=Path(out);out.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        def text(n):return z.read(n).decode('utf-8',errors='replace')
        def read(n):return json.loads(text(n))
        manifest=read('REPORTS_MANIFEST.json')
        for name,m in manifest.items():
            b=z.read(name)
            assert len(b)==m['bytes'] and sha(b)==m['sha256'],name
        raw=read('results/RESULTS.json');save(out/'MACROS.json',raw)
        assert sum(x['status']=='EXTRACTED_NOT_SIMULATED' for x in raw)==4
        cases=[]
        for stage in ['array_results','interface_results']:
            complete=read(stage+'/COMPLETE.json')
            for w in complete['windows']:
                prefix=stage+'/'+w['directory']+'/'
                power=text(prefix+'power.rpt')
                assert 'Dynamic Power Units = 1 W' in power
                def power_val(label):
                    return float(re.search(re.escape(label)+r'\s*=\s*([\d.eE+-]+)',power).group(1))
                watts=power_val('Total Power')
                dynamic=power_val('Net Switching Power')+power_val('Cell Internal Power')
                ns=w['end_ns']-w['start_ns']
                area=float(text(prefix+'area_um2.txt'))
                activity=text(prefix+'activity.rpt')
                assert re.search(r'^\s*Nets\s+\d+\(100\.00%\)',activity,re.M)
                check=text(prefix+'check_power.rpt')
                assert 'out_of_table_range' in check and 'missing_table' in check
                assert 'without function' in check # Expected vendor SRAM memory Q boundary.
                rows=text(prefix+'inventory.tsv').splitlines()[1:]
                refs=[r.split('\t')[1] for r in rows]
                assert refs.count('SB_D64_W2')==128
                pt=text(prefix+'pt.log')
                assert not re.search(r'^Error:',pt,re.M)
                cases.append(dict(stage=stage,**w,total_power_W=watts,dynamic_power_W=dynamic,
                    leakage_power_W=power_val('Cell Leakage Power'),energy_pJ=watts*ns*1000,
                    per_access_pJ=watts*10*1000,area_raw_um2=area,area_55eq_mm2=area*.81/1e6,
                    setup_ns=float(text(prefix+'setup_ns.txt')),hold_ns=float(text(prefix+'hold_ns.txt')),
                    annotated_nets_percent=100,macro_count=128,cell_count=len(refs),
                    power_report_sha256=sha(z.read(prefix+'power.rpt')),
                    warnings=[s for s in pt.splitlines() if 'Warning:' in s],
                    check_power=check.strip()))
        final=[c for c in cases if c['stage']=='interface_results']
        initial=[c for c in cases if c['stage']=='array_results']
        assert len(final)==18 and len(initial)==18
        assert all(c['setup_ns']>=0 and c['hold_ns']>=0 for c in final)
        checks=read('array_results/COMPLETE.json')['checks']
        assert len(checks)==12
        for c in checks:
            assert 'PASS frames=256 checked_bits=32768' in text('array_results/'+c['directory']+'/sim.log')
        summary=dict(area_raw_um2=final[0]['area_raw_um2'],area_scale=.81,
            area_55eq_mm2=final[0]['area_55eq_mm2'],
            functional_cases=len(checks),functional_frames=sum(c['frames'] for c in checks),
            functional_bits=sum(c['bits'] for c in checks),final_pt_windows=len(final),
            original_pt_windows=len(initial),original_hold_ns=min(c['hold_ns'] for c in initial),
            setup_ns=min(c['setup_ns'] for c in final),hold_ns=min(c['hold_ns'] for c in final),groups=[])
        for prob in [1,16]:
            for window in ['load','sequential','independent']:
                cc=[c for c in final if c['prob32']==prob and c['window']==window]
                assert len(cc)==3
                summary['groups'].append(dict(prob32=prob,window=window,seeds=[c['seed'] for c in cc],
                    mean_access_pJ=statistics.mean(c['per_access_pJ'] for c in cc),
                    min_access_pJ=min(c['per_access_pJ'] for c in cc),max_access_pJ=max(c['per_access_pJ'] for c in cc),
                    mean_window_pJ=statistics.mean(c['energy_pJ'] for c in cc),
                    mean_power_mW=statistics.mean(c['total_power_W']*1000 for c in cc)))
        summary['heads32_area_55eq_mm2']=summary['area_55eq_mm2']*32
        save(out/'ARRAY_RESULTS.json',dict(checks=checks,cases=cases))
        save(out/'SUMMARY.json',summary)
        save(out/'EVIDENCE.json',dict(archive=dict(path=str(archive.resolve()),bytes=archive.stat().st_size,
            sha256=sha(archive.read_bytes()),verified_members=len(manifest)),
            runtime_fingerprints=json.loads((out/'RUNTIME.json').read_text()) if (out/'RUNTIME.json').exists() else {},
            original_head='e5b12f5f68ac7d03630f51d517d46a008e695b61',
            sources={d:read(d+'/SOURCE.json') for d in ['source','array_source','repair_source']},
            submissions={d:read(d) for d in ['SUBMIT.json','ARRAY_SUBMIT.json','INTERFACE_SUBMIT.json']},
            mapped_netlist_sha256=read('array_results/COMPLETE.json')['netlist_sha256']))
        print(json.dumps(summary,indent=2))
if __name__=='__main__':main(*sys.argv[1:])
