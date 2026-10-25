"""Verify sealed run summaries before analysis or publication."""
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
BASE=ROOT/'architecture_tlm/unified_v6/results/scheduling_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 rows=[]
 for p in sorted(BASE.glob('*/*/MANIFEST.json')):
  m=json.loads(p.read_text(encoding='utf-8'));folder=p.parent
  if m.get('status')!='completed':raise ValueError('not completed '+str(p))
  for name in ['RESULT_SUMMARY.json','EXECUTION.json']:
   if sha(folder/name)!=m['files'][name]['sha256']:raise ValueError('SHA mismatch '+str(folder/name))
  r=json.loads((folder/'RESULT_SUMMARY.json').read_text(encoding='utf-8'));ex=json.loads((folder/'EXECUTION.json').read_text(encoding='utf-8'))
  if r['raw_result_sha256']!=m['files']['RESULT.json']['sha256']:raise ValueError('raw SHA mismatch')
  if r['case']!=ex['case'] or r['case']!=m['case'] or r['execution_commit']!=ex['source']['commit']:raise ValueError('identity mismatch')
  if hashlib.sha256(json.dumps(r['config'],sort_keys=True).encode()).hexdigest()!=ex['config_sha256']:raise ValueError('config mismatch')
  traffic=r['DRAM']['traffic'];c=r['config'];busy=r['resource_busy_ns'];energy=r['energy_J'];F=r['FFN_contract']
  row=dict(case=r['case'],TPOT_ms=r['metrics']['TPOT_ms'],cycles=r['metrics']['elapsed_ns']*c['core_hz']/1e9,
   FFN_ms=sum(v for k,v in r['phase_ns'].items() if k.startswith('FFN_'))/1e6,
   attention_core_ms=sum(v for k,v in r['phase_ns'].items() if k=='attention_core')/1e6,
   phases_ms={k:v/1e6 for k,v in r['phase_ns'].items()},resource_busy_ms={k:v/1e6 for k,v in busy.items()},
   DRAM_bytes=sum(v for k,v in traffic.items() if k.endswith('_physical_bytes')),
   SRAM_bytes=sum(v for k,v in r['SRAM']['traffic'].items() if k.endswith('_physical_bytes')),
   DRAM_core_J=energy.get('external_DRAMPower_core'),SRAM_internal_J=energy.get('SRAM_internal'),SRAM_leakage_J=energy.get('SRAM_leakage'),
   full_physical_energy_J=None,full_physical_area_mm2=None,
   DRAM_macro_requests=r['DRAM']['details']['macro_requests'],traffic=traffic,attention_activity=r['attention_activity'],unpriced_actions=r['unpriced_actions'],
   FFN_activity=r['FFN_activity'],tile_pipeline={k:({a:b for a,b in v.items() if a!='records'} if isinstance(v,dict) else v) for k,v in r.get('tile_pipeline',{}).items()},
   digital_operand_contract=r.get('digital_operand_contract',{}),FFN_weight_pipeline={k:v for k,v in F.get('weight_pipeline',{}).items() if k!='records'},
   SRAM_reserved=r['SRAM']['reserved_peak_bytes'],SRAM_capacity=r['SRAM']['configured_bytes'],
   execution_commit=r['execution_commit'],result_sha256=r['raw_result_sha256'],summary_sha256=sha(folder/'RESULT_SUMMARY.json'),manifest_sha256=sha(p),wall_seconds=r['wall_seconds'])
  rows.append(row)
  names=[r['case']['name'] for r in rows]
 if len(set(names))!=len(names):raise ValueError('duplicate case')
 expected=[]
 for name in ('RUN_MATRIX.json','W8_CORRECTED_MATRIX.json','BF16_8K_MATRIX.json','ATTENTION_ABLATION_MATRIX.json'):
  expected.extend(x['name'] for x in json.loads((ROOT/'work/jieruiz/186'/name).read_text())['cases'])
 missing=sorted(set(expected)-set(names))
 if set(names)-set(expected):raise ValueError('unexpected case')
 if '--require-complete' in sys.argv and missing:raise ValueError('incomplete '+str(missing))
 out={'expected_cases':len(expected),'verified_cases':len(rows),'missing':missing,'scope':'verified synthetic full-model timing; conditional macro operators, no quality or chip PPA','rows':rows}
 (BASE/'COMPARISON.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({'verified_completed':len(rows),'cases':[dict(case=x['case']['name'],ms=x['TPOT_ms']) for x in rows]}))
if __name__=='__main__':main()
