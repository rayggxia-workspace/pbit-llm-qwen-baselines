"""Auditable locality tables: sealed TLM, structural bits, no fabricated chip PPA."""
import csv,hashlib,json,math,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[3]
OUT=ROOT/'architecture_tlm/unified_v6/results/locality_20261025'
W=ROOT/'work/jieruiz/186'
stage1='--stage1' in sys.argv
source=json.loads((W/('LOCALITY_SOURCE_b1df81d2.json' if stage1 else 'LOCALITY_SOURCE_829559dc.json')).read_text())
matrix=json.loads((W/'LOCALITY_MATRIX.json').read_text())['cases']
rows=[];checks=[]
for i,case in enumerate(matrix):
 p=(OUT if stage1 or i<2 else OUT/'window_prefetch')/f'case_{i}';mf=p/'MANIFEST.json'
 if not mf.exists():continue
 manifest=json.loads(mf.read_text());assert manifest['status']=='completed'
 for name in ('RESULT_SUMMARY.json','EXECUTION.json'):
  assert hashlib.sha256((p/name).read_bytes()).hexdigest()==manifest['files'][name]['sha256']
 r=json.loads((p/'RESULT_SUMMARY.json').read_text());e=json.loads((p/'EXECUTION.json').read_text())
 expected_commit='b1df81d216894edfcb155ffec1416183d3cf2761' if i<2 else source['commit']
 assert r['case']==case and e['case']==case and e['source']['commit']==expected_commit
 assert r['raw_result_sha256']==manifest['files']['RESULT.json']['sha256']
 assert r['DRAM']['details']['status']=='finished'
 assert r['metrics']['full_physical_energy_J'] is None and r['metrics']['full_physical_area_mm2'] is None
 c=case.get('locality',{});tile=c.get('tile',64);E=c.get('engines',case.get('engines',8));R=c.get('retain',1)
 h,F,L=2560,9728,36
 gu_w=math.ceil(40/R);d_w=math.ceil(152/R)
 read=2*F*8*(gu_w-1)+h*8*(d_w-1);write=2*F*8*gu_w+h*8*d_w
 ffn_ms=sum(v/1e6 for k,v in r['phase_ns'].items() if k.startswith('FFN_') or k in ('ffn_output_conversion','ffn_residual'))
 row=dict(index=i,name=case['name'],tile=tile,engines=E,retain=R,source_groups=c.get('source_groups',1),
     TPOT_ms=r['metrics']['TPOT_ms'],FFN_ms=ffn_ms,
     phase_rest_ms=r['metrics']['TPOT_ms']-ffn_ms,
     SC_partial_MiB_per_layer=(read+write)/2**20 if case['ffn']=='sc' else None,
     SRAM_read_MiB=r['SRAM']['traffic']['read_physical_bytes']/2**20,
     SRAM_write_MiB=r['SRAM']['traffic']['write_physical_bytes']/2**20,
     SRAM_reserved_KiB=r['SRAM']['reserved_peak_bytes']/1024,
     shared_SRAM_area_mm2=r['SRAM']['area_mm2'],
     physical_total_area_mm2=None,physical_total_energy_J=None,
     raw_sha256=r['raw_result_sha256'],wall_seconds=r['wall_seconds'],source_commit=expected_commit,
     total_core_cycles=r['metrics']['elapsed_ns']/10)
 if case['ffn']=='sc':
  row.update(weight_cells_relative_to_8x64=E*tile*tile/(8*64*64),
      local_weight_KiB=E*tile*tile/1024,
      resident_partial_KiB=E*tile*64/8/1024 if c else 0,
      physical_waves_per_layer=math.ceil(40/(tile/64))*math.ceil(2*F/(E*tile))+math.ceil(152/(tile/64))*math.ceil(h/(E*tile)))
  busy=r['resource_busy_ns']
  row.update(array_busy_ms=busy['sc:0']/1e6,
      local_weight_program_busy_ms=(busy['sc_weight_local_port']-busy['sc:0'])/1e6,
      bucket_and_restore_busy_ms=sum(busy.get(k,0) for k in ('ffn_SC_bucket_shift_reduce','ffn_SC_coefficient16_restore'))/1e6,
      partial_accumulator_busy_ms=busy.get('locality_accumulator',busy.get('ffn_SC_cross_tile_add64',0))/1e6)
  spec=r['SRAM']['calibrated_macro'];word=r['SRAM']['word_bytes']
  row['partial_macro_internal_dynamic_mJ_per_token']=(read/word*spec['read_internal_pJ']+write/word*spec['write_internal_pJ'])*L*1e-9
  if c:
   st=r['FFN_contract']['local_state'];ct=r['FFN_contract']['locality_counts']
   assert ct['partial_write_bytes']==write*L and ct.get('partial_read_bytes',0)==read*L
   assert ct['weight_bytes']==3*h*F*L
   assert ct['physical_waves']==row['physical_waves_per_layer']*L
   assert ct['logical_64_tiles']==3*h*F//4096*L
   row.update(context_bank_KiB=(st['input_context_bank_bits']+st['nonlinear_context_bank_bits'])/8192,
       code_window_KiB=st['local_input_code_window_bits']/8192,
       temporal_counters_KiB=st['temporal_counter_bits']/8192,
       reduction_pipeline_KiB=st['reduction_pipeline_bits']/8192,
       RNG_context_cycles=r['resource_busy_ns'].get('locality_context_port',0)/10,
       sample_cycles=ct['sample_cycles'],
       local_bits_scope='register/RF capacity proxy; not synthesized area; interfaces and extra parallel latches pending')
  assert r['FFN_activity']['SC_64x64_tiles']==3*h*F//4096*L
 rows.append(row)
 checks.append(dict(index=i,case=case['name'],manifest_sha256=hashlib.sha256(mf.read_bytes()).hexdigest(),raw_sha256=r['raw_result_sha256']))
assert len(rows)==len(matrix)==13,'collect all cases before making final comparison'
by={r['name']:r for r in rows};base=by['old8_exact'];macro=by['t64_e8_r1_s1']
for r in rows:
 r['TPOT_reduction_vs_native_old_percent']=100*(1-r['TPOT_ms']/base['TPOT_ms'])
 r['FFN_reduction_vs_native_old_percent']=100*(1-r['FFN_ms']/base['FFN_ms'])
 r['TPOT_reduction_vs_macro_R1_percent']=100*(1-r['TPOT_ms']/macro['TPOT_ms'])
 if r['SC_partial_MiB_per_layer'] is not None:
  r['partial_traffic_reduction_percent']=100*(1-r['SC_partial_MiB_per_layer']/base['SC_partial_MiB_per_layer'])
for i in range(2,13):
 basepath=OUT if stage1 else OUT/'window_prefetch'
 a=json.loads((basepath/'case_2/RESULT_SUMMARY.json').read_text());b=json.loads((basepath/f'case_{i}/RESULT_SUMMARY.json').read_text())
 assert a['attention_activity']==b['attention_activity']
 for k in ('SC_W8_magnitude_AND','SC_product_sign_XOR','SC_bucket_shift_reduce','SC_coefficient16_restore'):
  assert a['actions'][k]==b['actions'][k],(i,k)
fields=list(dict.fromkeys(k for r in rows for k in r));prefix='STAGE1_' if stage1 else ''
with (OUT/(prefix+'COMPARISON.csv')).open('w',encoding='utf-8',newline='') as f:
 writer=csv.DictWriter(f,fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
(OUT/(prefix+'AGGREGATE.json')).write_text(json.dumps(dict(source_commit=source['commit'],scope='full synthetic decode conditional TLM; not PPL or physical PPA; controls from unchanged b1df81d2 path',rows=rows),indent=2)+'\n',encoding='utf-8',newline='\n')
(OUT/(prefix+'VERIFIED.json')).write_text(json.dumps(dict(status='13 completed and SHA verified',checks=checks,numerical_scope='15 signed per-block reduction order checks plus unit contracts; full stochastic FFN compiler/PPL pending'),indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps([{k:r[k] for k in ('name','TPOT_ms','FFN_ms','SC_partial_MiB_per_layer')} for r in rows],indent=2))
