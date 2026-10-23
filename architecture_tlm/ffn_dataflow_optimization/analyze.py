"""Summarize saved paired traces; never reruns or modifies simulation outputs."""
import argparse, csv, gzip, hashlib, json, statistics, struct
from pathlib import Path

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def fp(w):return struct.unpack('<f',struct.pack('<I',w))[0]
def main():
 p=argparse.ArgumentParser();p.add_argument('--runs',type=Path,nargs='+',required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('fresh analysis directory required')
 a.output.mkdir(parents=True);rows=[];details={}
 for folder in a.runs:
  for receipt in sorted(folder.glob('*.receipt.json')):
   r=read(receipt);v=json.loads(gzip.decompress((folder/r['file']).read_bytes()));c=v['case'];s=v['storage'];native=v['native_result']
   state=(s['weight_hold_bytes']+s['counter_allocated_bytes']+s['staging_allocated_bytes']+s['output_slots']*s['output_slot_bytes']+s['pending_partial_write_bytes']+s['w8_accumulator_allocated_bytes']+s['feed_response_bytes']+(s['sample_hold_bits']+7)//8)
   rows.append(dict(candidate=c['candidate'],method=c['method'],seed=c['seed'],latency_us=native['finish_ps']/1e6,
    local_budget_bytes=state,weight_hold_bytes=s['weight_hold_bytes'],counter_allocated_bytes=s['counter_allocated_bytes'],
    staging_bytes=s['staging_allocated_bytes'],output_slots=s['output_slots'],sram_reserved_bytes=s['sram_layout']['reserved_bytes'],
    counter_read_physical_bytes=native['actions']['local_packet_physical_bytes'],
    partial_read_physical_bytes=native['actions']['partial_read_physical_bytes'],partial_write_physical_bytes=native['actions']['partial_write_physical_bytes'],
    weight_preload_bytes=native['actions']['weight_preload_bytes'],cycle_event_equal=v['cycle_event_equal']))
   if c['seed']==0:details[c['candidate']+'_'+c['method']]=dict(resource_stats=native['resource_stats'],resource_peak=native['resource_peak'],storage=s,actions=native['actions'],partial_io_contract=v['partial_io_contract'],config=v['config'])
 table=[]
 for name in dict.fromkeys(r['candidate'] for r in rows):
  sc=[r['latency_us'] for r in rows if r['candidate']==name and r['method']=='sc'];w8=[r['latency_us'] for r in rows if r['candidate']==name and r['method']=='w8']
  table.append(dict(candidate=name,sc_us=statistics.mean(sc),w8_us=statistics.mean(w8),sc_stdev_us=statistics.stdev(sc),w8_stdev_us=statistics.stdev(w8),
   sc_over_w8=statistics.mean(sc)/statistics.mean(w8),local_budget_bytes=next(r['local_budget_bytes'] for r in rows if r['candidate']==name),paired_seeds=len(sc)))
 base=next(x for x in table if x['candidate']=='baseline')
 for t in table:t.update(sc_reduction_vs_baseline_pct=100*(1-t['sc_us']/base['sc_us']),w8_reduction_vs_baseline_pct=100*(1-t['w8_us']/base['w8_us']))
 quality=[]
 for item in read(a.fixtures/'FIXTURES.json')['files']:
  f=read(a.fixtures/item['path']);sc=list(map(fp,f['expected_sc']));w8=list(map(fp,f['expected_w8']));mse=sum((x-y)**2 for x,y in zip(sc,w8))/len(sc);den=sum(x*x for x in w8)/len(w8)
  quality.append(dict(seed=f['seed'],output_count=len(sc),nmse_vs_w8=mse/den,max_absolute_error=max(abs(x-y) for x,y in zip(sc,w8)),scope='synthetic local projection diagnostic, not model quality or PPL'))
 result=dict(cases=len(rows),paired_cases=len(rows)//2,table=table,numeric_diagnostics=quality,seed0_details=details,
  area_mm2=None,energy_J=None,quality_ppl=None,
  scope='conditional four-group eight-tile projection; same configurable storage/bandwidth, not same total physical area',
  local_budget_scope='weight hold + allocated counters + staging + output slots + pending writes + W8 accumulator + feed responses + sample hold; excludes datapath/pipeline/control/RNG bits, not total storage or area',
  seed_scope='three operand/sample seeds; fixed-rate schedule may have identical latency; this is not measured timing variability',
  analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 write(a.output/'SUMMARY.json',result)
 with (a.output/'CASES.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 lines=['| 配置 | SC (µs) | W8 (µs) | SC降幅 | W8降幅 | SC/W8 | 已列局部状态 (KiB) |','|---|---:|---:|---:|---:|---:|---:|']
 for t in table:lines.append(f"| {t['candidate']} | {t['sc_us']:.3f} | {t['w8_us']:.3f} | {t['sc_reduction_vs_baseline_pct']:.2f}% | {t['w8_reduction_vs_baseline_pct']:.2f}% | {t['sc_over_w8']:.4f} | {t['local_budget_bytes']/1024:.3f} |")
 (a.output/'TABLE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({'cases':len(rows),'table':table,'numeric_diagnostics':quality},ensure_ascii=False))

if __name__=='__main__':main()
