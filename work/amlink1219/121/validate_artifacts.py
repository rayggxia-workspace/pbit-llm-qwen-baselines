"""Validate published source/result bindings without running a simulator."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[3]
PACKAGE=ROOT/'architecture_tlm/encoding_restore_contract'
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
manifest=read(PACKAGE/'MANIFEST.json')
for name,entry in manifest.items():
    path=(ROOT/name).resolve()
    assert path.is_relative_to(ROOT.resolve())
    assert sha(path)==entry['sha256'] and path.stat().st_size==entry['bytes'],name
validation=read(Path(__file__).parent/'VALIDATION.json')
for name,expected in validation['source_sha256'].items():assert sha(ROOT/name)==expected,name
cycle=read(PACKAGE/'results/cycle_20261023/SUMMARY.json')
backend=read(Path(__file__).parent/'BACKEND_SOURCE.json')
assert cycle['backend_source_sha256']=={Path(name).name:value for name,value in backend['files'].items()}
for row in cycle['cases']:
    case=read(PACKAGE/'results/cycle_20261023'/(row['id']+'.json'))
    assert case['cycle_event_equal'] and case['direct_dot_equal']
    assert case['actions']=={'complete_encode_group64':2,'encoded_values':128,
                             'complete_restore_output_b4':128,'cross_k_fp32_add':128}
for stage in ('rtl','cycle'):
    record=read(ROOT/'digital_circuit_simulation_registry/records'/('encoding-restore-121-'+stage+'.json'))
    for item in record['artifacts']:
        assert sha(ROOT/item['path'])==item['sha256']
    assert all(record['stages'][x]=='not_run' for x in ('synthesis','sta','power','postlayout'))
assert cycle['area_um2'] is None and cycle['energy_pj'] is None and cycle['sta_frequency_hz'] is None
print(json.dumps({'passed':True,'manifest_files':len(manifest),'source_files':len(validation['source_sha256']),
                  'cycle_cases':len(cycle['cases']),'physical_ppa':'unknown'}))
