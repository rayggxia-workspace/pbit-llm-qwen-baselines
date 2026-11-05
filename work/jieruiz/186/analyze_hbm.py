"""Audit all sealed HBM results and generate a compact timing comparison."""
import csv,hashlib,json,math,pathlib,statistics,sys
R=pathlib.Path(__file__).resolve().parents[3];W=R/'work/jieruiz/186';O=R/'architecture_tlm/unified_v6/results/hbm_20261025'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];audits=[]
for stage,manifest,matrix in [('', 'HBM_COLLECTION.json','HBM_MATRIX.json'),('pipelined','HBM_PIPELINE_COLLECTION.json','HBM_PIPELINE_MATRIX.json')]:
 collection=json.loads((W/manifest).read_text(encoding='utf-8'));cases=json.loads((W/matrix).read_text(encoding='utf-8'))['cases']
 if '--require-complete' in sys.argv:assert not collection['pending'] and not collection['failed']
 for item in collection['completed']:
  folder=O/stage/'results'/('case_'+str(item['index']));m=json.loads((folder/'MANIFEST.json').read_text(encoding='utf-8'))
  assert sha(folder/'MANIFEST.json')==item['manifest_sha256']
  for name in ('RESULT_SUMMARY.json','EXECUTION.json'):assert sha(folder/name)==m['files'][name]['sha256']
  s=json.loads((folder/'RESULT_SUMMARY.json').read_text(encoding='utf-8'));x=json.loads((folder/'EXECUTION.json').read_text(encoding='utf-8'));case=cases[item['index']]
  assert s['case']==x['case']==m['case']==case
  assert sha(W/matrix)==x['matrix_sha256']
  assert s['raw_result_sha256']==m['files']['RESULT.json']['sha256']
  assert s['model']['num_hidden_layers']==36 and s['config']['core_hz']==100000000
  assert x['config_sha256']==hashlib.sha256(json.dumps(s['config'],sort_keys=True).encode()).hexdigest()
  assert s['metrics']['full_physical_energy_J'] is None and s['metrics']['full_physical_area_mm2'] is None
  d=s['DRAM']['details'];t=s['DRAM']['traffic'];byte=sum(v for k,v in t.items() if k.endswith('_physical_bytes'))
  # traffic contains physical tensor reads, not a host unit count guess.
  assert byte==d['burst_count']*64,(case['name'],byte,d['burst_count'])
  controllers=[v for k,v in d['stats']['dram'].items() if k.startswith('controller')]
  served=sum(v['AverageBandwidth'] for v in controllers)*s['metrics']['elapsed_ns']*1e-9
  assert math.isclose(served,byte,rel_tol=1e-8,abs_tol=64),(case['name'],served,byte)
  assert sum(v['NumberOfRequests'] for v in controllers)==d['host_transactions']
  if 'hbm2' in case['memory_profile']:
   assert d['energy_valid'] is False and not d['power_at_system_end']
   assert not any(k.startswith('external_DRAMPower') for k in s['energy_J'])
   assert 'uncalibrated_HBM_system_ns' in s['unpriced_actions']
   assert len(controllers)==8
  else:assert len(controllers)==2
  busy=s['resource_busy_ns']
  row=dict(name=case['name'],profile=case['memory_profile'],ffn=case['ffn'],attention=case['attention'],seed=case['seed'],context=case['context'],TPOT_ms=s['metrics']['TPOT_ms'],tokens_s=s['metrics']['tokens_per_second'],dram_GB=byte/1e9,dram_service_ms=d['service_ms'],dram_service_GBs=byte/(d['service_ms']*1e6),sram_busy_ms=busy.get('sram_fabric',0)/1e6,mac_busy_ms=busy.get('mac',0)/1e6,wall_seconds=s['wall_seconds'],source=x['source']['commit'],result_sha256=s['raw_result_sha256'])
  rows.append(row);audits.append(dict(name=case['name'],summary_sha256=sha(folder/'RESULT_SUMMARY.json'),controller_served_bytes=served,host_transactions=d['host_transactions'],layers=36))
  row['_raw']=s
# Matched input seeds must keep the workload, capacity, arrays, arithmetic fixed.
groups={}
for r in rows:groups.setdefault((r['ffn'],r['attention'],r['seed']),[]).append(r)
for group in groups.values():
 a=group[0]['_raw']
 for row in group[1:]:
  b=row['_raw']
  for key in ('FFN_activity','attention_activity'):
   assert a[key]==b[key],(row['name'],key)
  # Existing sampled_attention batches V by configured max_pending. Wider
  # ingress changes descriptor grouping (32 -> 128 tokens), not sampled IDs/bytes.
  ta=a['DRAM']['traffic'];tb=b['DRAM']['traffic']
  diffs={k:(ta.get(k),tb.get(k)) for k in set(ta)|set(tb) if ta.get(k)!=tb.get(k)}
  assert set(diffs)<= {'DMA_descriptors','DRAMSys_scatter_requests'},(row['name'],diffs)
  for key in ('sram','ffn','attention','macs_per_cycle','vector_lanes','nonlinear_lanes'):
   assert a['config'].get(key)==b['config'].get(key),(row['name'],key)
for r in rows:r.pop('_raw')
summary=dict(status='completed' if len(rows)==25 else 'partial',cases=len(rows),rows=rows,audits=audits,scope='same arithmetic/SRAM, actual DRAMSys closed loop; no PPL or measured PPA')
(O/'AGGREGATE.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
if rows:
 with (O/'COMPARISON.csv').open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(dict(status=summary['status'],cases=len(rows),results=[{k:r[k] for k in ('name','TPOT_ms','dram_service_ms','sram_busy_ms')} for r in rows]),indent=2))
