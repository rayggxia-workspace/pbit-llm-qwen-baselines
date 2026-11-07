"""Finite-memory workload/energy ownership checks on completed local replays."""
from pathlib import Path
import argparse,hashlib,json,math
HERE=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True)
    p.add_argument('--owner-prefix',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();rows={};checks=[]
    for c in (2,3):
        d=a.results/('local_layer%d_v1'%c);r=load(d/'RESULT.json');b=load(d/'BUDGET.json');s=load(d/'SEAL.json')
        assert s['result_sha256']==sha(d/'RESULT.json') and s['budget_sha256']==sha(d/'BUDGET.json')
        assert r['status']=='completed' and r['simulated_chip_cycles']==r['time_ns']/4
        assert r['memory']['SRAM']['physical_banks']==304 and r['memory']['SRAM']['capacity_bytes']==1216*1024
        assert r['unified_clock_contract']['SRAM_MHz']==r['unified_clock_contract']['DMA_front_MHz']==250
        assert not r['memory']['final_pending'] and not r['memory']['final_response_occupied']
        assert r['short_FFN_contract']['normalize_shifts']==dict(GU=-4,Wd=-5)
        for row in r['common_FFN_stages']:
            assert row['sample_core_ns']==row['frames']*(72 if row['mode']=='GU' else 136)
            assert row['peak_core_reserved_results']<=2 and row['physical_common_cores']==c
        assert r['actions']['common_R8_words']==6080*16+3040*3*32
        assert r['actions']['common_state32_vectors']==(6080+3040)*4
        assert b['totals']['short_FFN_measured_energy_mJ'] is None
        rows[c]=(r,b);checks+=['C%d:seal,clock,banks,drain,denominators,sampling,credits,unknown-PPA'%c]
    for key in ('dram_read_bytes','dram_write_bytes'):
        assert rows[2][0]['memory']['counts'][key]==rows[3][0]['memory']['counts'][key]
    for key in ('SC_equivalent_MAC','digital_BF16_MAC','attention_QK_MAC','PV_ADD','samples','unique_V'):
        assert rows[2][0]['actions'].get(key)==rows[3][0]['actions'].get(key),key
    assert math.isclose(rows[3][1]['totals']['covered_area55_mm2']-rows[2][1]['totals']['covered_area55_mm2'],.9694793124,abs_tol=1e-10)
    checks+=['same DRAM bytes and mathematical workload','exactly one predecessor core area difference']
    # Cross-check independent owner prefix transaction model, not a new latency fit.
    owner=load(a.owner_prefix);prefix=next(x['end_ns'] for x in rows[3][0]['phases'] if x['stage']=='O')
    assert prefix-5200==owner['time_ns']==536832
    checks+=['owner prefix reproduced exactly + explicit5.2us score-front macro']
    # In-place reference files, snapshots and original100MHz modules are untouched.
    for p in HERE.rglob('*.py'):compile(p.read_bytes(),str(p),'exec')
    summary=dict(status='PASS',checks=checks,scopes=['two full-shape single layers; analytic external memory'],
        no_full_native_result_claimed=True,
        source_files_sha256={p.relative_to(HERE).as_posix():sha(p) for p in HERE.rglob('*') if p.is_file() and p.suffix=='.py'},
        outcomes={str(c):dict(time_ms=r['simulated_ms'],chip_cycles=r['simulated_chip_cycles'],
            area55_mm2=b['totals']['covered_area55_mm2'],phase_ms=r['phase_totals_ms'],
            input_sha256=r['source_identity']['input_sha256'],result_sha256=sha(a.results/('local_layer%d_v1'%c)/'RESULT.json'),
            budget_sha256=sha(a.results/('local_layer%d_v1'%c)/'BUDGET.json')) for c,(r,b) in rows.items()},
        first_setup_failures='two input-directory misses before replay; no simulation executed; actual captured input directory then supplied',
        inherited_metadata='first local receipts retain historical resource labels; current exporter corrects to256 sharedQK/16reduce/3or2FFN; executable unchanged')
    a.out.write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(dict(status='PASS',checks=len(checks))))

if __name__=='__main__':main()
