"""Verify immutable source/output bindings and independent schedule arithmetic."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
WORK=Path(__file__).resolve().parent
RESULT=ROOT/'architecture_tlm/ffn_storage_contract/results/run_20261023'
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    output_records=read(RESULT/'MANIFEST.json')['files']
    for item in output_records:
        path=RESULT/item['path']
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],path
    execution=read(RESULT/'EXECUTION.json')
    for item in execution['sources']:
        path=ROOT/item['path']
        assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256'],path
    summary=read(RESULT/'SUMMARY.json')
    assert len(summary['cases'])==6 and len(summary['rejected'])==4
    for case in summary['cases']:
        s=case['summary'];t=s['samples_completed']
        assert s['source_advancements']==t and s['weight_bytes_consumed']==32768*t
        if s['mode']=='reread':
            # Independent one-response, full-word recurrence at the default clocks.
            assert s['end_ps']==2048*t*50000
            assert s['sram_read_bytes']==32768*t
        else:
            assert s['first_sample_ps']==6600000
            assert s['end_ps']==6600000+t*10000
            assert s['sram_read_bytes']==32768
        assert s['area_um2'] is None and s['energy_pJ'] is None
        assert s['weight_transfer_resource_lower_bound_ps_per_wave']==2080500
    numeric=read(RESULT/'COUNTER_DIAGNOSTIC.json')
    assert numeric['passed'] and numeric['case_count']==66 and numeric['bin_outputs_checked']==888
    for t,count_bits,sum_bits in [('16',11,19),('32',12,20),('64',13,21)]:
        row=numeric['widths'][t]
        assert row['count_bits']==count_bits and row['sum_bits']==sum_bits
    report=dict(status='PASS',source_files_checked=len(execution['sources']),
                result_files_checked=len(output_records),schedule_cases=6,
                independent_default_arithmetic_cases=6,invalid_contracts_rejected=4,
                integer_synthetic_cases=66,integer_bin_outputs=888,
                unit_tests=dict(command='python -B -m unittest architecture_tlm.ffn_storage_contract.test_model architecture_tlm.ffn_storage_contract.test_counter -v',
                                passed=30,failed=0,execution='separate observed invocation; this script does not rerun tests'),
                registry_unit_tests=dict(passed=8,failed=0,execution='separate observed invocation'),
                review='INDEPENDENT_REVIEW.json',source_manifest_sha256=sha(RESULT/'EXECUTION.json'),
                result_manifest_sha256=sha(RESULT/'MANIFEST.json'),
                evidence_level='DESIGN_PROOF',RTL_STA_PPA_PPL='not_run')
    (WORK/'VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
