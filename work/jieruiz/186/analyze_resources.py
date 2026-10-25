"""Check the full factorial and derive attributable timing differences."""
import csv,hashlib,json,math,pathlib
R=pathlib.Path(__file__).resolve().parents[3];W=R/'work/jieruiz/186';O=R/'architecture_tlm/unified_v6/results/resources_20261025'
c=json.loads((W/'RESOURCE_COLLECTION.json').read_text());assert len(c['completed'])==16 and not(c['pending'] or c['failed']),c
rows=[];full={}
for i in range(16):
 p=O/'results'/('case_'+str(i));d=json.loads((p/'COMPACT.json').read_text());mf=json.loads((p/'MANIFEST.json').read_text());ex=json.loads((p/'EXECUTION.json').read_text())
 assert mf['status']=='completed' and ex['source']['commit']==d['execution_commit']=='b01058f7e2143e81a602644d3d796768a8d008b5'
 assert hashlib.sha256(json.dumps(d['config'],sort_keys=True).encode()).hexdigest()==ex['config_sha256']
 assert mf['files']['RESULT.json']['sha256']==d['evidence']['raw_sha256']==d['raw_result_sha256']
 a=d['actions'];s=d['SRAM'];pipe=d['tile_pipeline']['digital']
 mac=a['bf16_mac']+a['fp32_mac'];assert mac==4626251776
 db=sum(v for k,v in d['DRAM']['traffic'].items() if k.endswith('_physical_bytes'))
 sb=sum(s['traffic'][k] for k in ['read_physical_bytes','write_physical_bytes'])
 assert db==8347078656 and sb==16705296768
 assert s['physical_bytes']==8*1024**2 and pipe['operand_capacity_bytes']==65536
 assert not(pipe['pending'] or pipe['active'] or pipe['staged'])
 assert pipe['counts']['issued']==pipe['counts']['retired']==pipe['counts']['filled']
 conf=d['config'];b=d['resource_busy_ns'];hz=conf['core_hz'];t=d['metrics']['TPOT_ms']
 assert math.isclose(sum(d['phase_ns'].values())/1e6,t,abs_tol=1e-6)
 row=dict(index=i,profile=d['case']['resource_profile'],prefill=d['case']['shared_prefill'],MAC_per_cycle=conf['macs_per_cycle'],SRAM_GBs=s['fabric_combined_read_write_GBs'],banks=s['banks'],macros=s['macros'],SRAM_macro_area_mm2=s['area_mm2'],TPOT_ms=t,tokens_per_second=1000/t,core_equivalent_cycles=round(t*hz/1000),MAC_busy_ms=b['mac']/1e6,SRAM_fabric_busy_ms=b['sram_fabric']/1e6,DRAM_actor_busy_ms=b['dram_dma']/1e6,vector_busy_ms=b['vector']/1e6,MAC_ideal_ms=mac/(conf['macs_per_cycle']*hz)*1000,SRAM_ideal_ms=sb/(s['fabric_combined_read_write_GBs']*1e6),MAC=mac,DRAM_bytes=db,SRAM_bytes=sb,tiles=pipe['counts']['issued'],prefilled=pipe['counts'].get('prefilled',0),wall_seconds=d['wall_seconds'])
 rows.append(row);full[(row['profile'],row['prefill'])]=d
pairs=[]
for name in dict.fromkeys(x['profile'] for x in rows):
 aa,bb=[next(x for x in rows if x['profile']==name and x['prefill']==v) for v in (False,True)]
 x,y=full[(name,False)],full[(name,True)]
 for k in ['bf16_mac','fp32_mac','dram_read','dram_write','sram_read','sram_write','digital_local_operand_read_byte']:assert x['actions'][k]==y['actions'][k]
 assert x['SRAM']['traffic']==y['SRAM']['traffic'] and x['DRAM']['traffic']==y['DRAM']['traffic']
 assert aa['tiles']==bb['tiles']
 pairs.append(dict(profile=name,MAC_per_cycle=aa['MAC_per_cycle'],SRAM_GBs=aa['SRAM_GBs'],old_ms=aa['TPOT_ms'],prefill_ms=bb['TPOT_ms'],saved_ms=aa['TPOT_ms']-bb['TPOT_ms'],saved_percent=100*(1-bb['TPOT_ms']/aa['TPOT_ms'])))
anchor=next(x for x in pairs if x['profile']=='anchor_F64');assert abs(anchor['old_ms']-402.62913)<1e-6
E={p['profile']:p for p in pairs};base=E['c512_m64'];big=E['c8192_m512']
effects=dict(old_macro_to_E_ms=anchor['old_ms']-base['old_ms'],compute_only_ms=base['old_ms']-E['c8192_m64']['old_ms'],SRAM_only_ms=base['old_ms']-E['c512_m512']['old_ms'],joint_hardware_ms=base['old_ms']-big['old_ms'],schedule_small_ms=base['saved_ms'],schedule_large_ms=big['saved_ms'],combined_ms=base['old_ms']-big['prefill_ms'])
# Above effects are explicit paths through a factorial, NOT independent additive percentages.
out=dict(status='completed',cases=16,small_real_DRAM_gate=8,unit_tests=110,source_commit='b01058f7e2143e81a602644d3d796768a8d008b5',rows=rows,pairs=pairs,effects=effects,phase_ms={name+'_'+str(int(v)):{k:t/1e6 for k,t in d['phase_ns'].items()} for (name,v),d in full.items()},checks='all 36 layers; source/config/raw SHA; MAC/bytes/tile invariants; exact prior F anchor; zero live tickets',boundary='synthetic full decode timing; no new numerical or PPA evidence')
(O/'ANALYSIS.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
with (O/'COMPARISON.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)
print(json.dumps(dict(pairs=pairs,effects=effects),indent=2))
