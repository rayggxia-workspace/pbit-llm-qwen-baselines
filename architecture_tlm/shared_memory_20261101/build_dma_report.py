"""Derive small DMA result/identity tables from sealed byte-preserved originals."""
from pathlib import Path
import argparse,hashlib,json
def read(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(root):
 w=root/'work/rayggxia/227';archive=root.parents[1]/'project_archives/shared_memory227_20261101'
 out=root/'architecture_tlm/shared_memory_20261101/dma_expand';out.mkdir(parents=True,exist_ok=True)
 names=['dmaofficial_base','dmaofficial_gap0','dmaofficial_issue24','dmaofficial_wide16','dmaofficial_wide24','dmaofficial_packed24','lanesofficial_base','lanesofficial_wide16','lanesofficial_wide24','lanesofficial_packed24','lanesofficial_base_s503','lanesofficial_packed24_s503','lanesofficial_base_s1009','lanesofficial_packed24_s1009','whole_lanesofficial_packed24']
 rows=[];raw={};checks={}
 for name in names:
  receipt=w/(name+'_SUBMISSION.json')
  if not receipt.exists():continue
  d=read(receipt);p=archive/name/'results/RESULT.json'
  row=dict(phase=name,job=d['job'],remote_root=d['root'],source_archive_sha256=d['source_sha256'],source_files_sha256=d['manifest']['files_sha256'],binary_sha256=d['binary_sha256'],config_sha256=d['config_sha256'],input_sha256=d['input_identity']['sha256'],status='submitted_not_sealed')
  if p.exists():
   r=read(p);raw[name]=r;m=r['memory'];s=m['SRAM'];assert r['status']=='completed' and not m['final_pending'] and not m['final_response_occupied']
   total=m['counts'].get('dram_read_bytes',0)+m['counts'].get('dram_write_bytes',0)
   row.update(status='completed',result_sha256=sha(p),time_ms=r['simulated_ms'],chip_cycles=r['simulated_chip_cycles'],DDR_core_mJ=r['DRAM']['core_total_mJ'],DDR_command_mJ=r['DRAM']['command_component_mJ'],DDR_background_mJ=r['DRAM']['background_refresh_other_mJ'],SRAM_dynamic_mJ=s['dynamic_mJ'],SRAM_leakage_mJ=s['leakage_mJ'],SRAM_total_mJ=s['dynamic_mJ']+s['leakage_mJ'],SRAM_area55eq_mm2=s['area55eq_mm2'],effective_total_GBs=total/m['elapsed_ns'],external_bytes=total,by_kind=m['by_kind'],dma=r['dma_contract'],bridge=r['bridge_contract'],peak_outstanding=m['counts']['peak_outstanding'],peak_response_bytes=m['counts']['peak_response_bytes'],phase_ms={v['stage']:v['duration_ns']*1e-6 for v in r['phases']})
   if name!='whole_lanesofficial_packed24':
    suffix=next((v for v in ['_s503','_s1009'] if name.endswith(v)),'')
    a=raw['lanesofficial_base'+suffix] if suffix else raw['dmaofficial_base'];am=a['memory'];sa=am['SRAM'];assert r['actions']==a['actions'] and r['kernel_active']==a['kernel_active'] and r['work_spec_sha256']==a['work_spec_sha256']
    assert s['capacity_bytes']==sa['capacity_bytes']==8388608
    assert s['counts']['read_words']==sa['counts']['read_words'] and s['counts']['write_words']==sa['counts']['write_words']
    for k,v in am['by_kind'].items():
     for f in ['issued_bytes','read_bytes','write_bytes']:assert m['by_kind'][k].get(f,0)==v.get(f,0)
     if r['arguments']['weight_layout']=='row_major':assert m['by_kind'][k]==v
    assert row['peak_outstanding']<=row['dma']['credit'] and row['peak_response_bytes']<=row['dma']['response_bytes']
    row.update(time_reduction_percent=100*(1-r['simulated_ms']/a['simulated_ms']),DDR_energy_reduction_percent=100*(1-r['DRAM']['core_total_mJ']/a['DRAM']['core_total_mJ']))
  rows.append(row)
 streams=[]
 for name in ['dmaofficial_stream','lanesofficial_stream1','lanesofficial_stream8']:
  p=archive/name/'results/STREAM_SUMMARY.json'
  if p.exists():streams.append(dict(phase=name,result_sha256=sha(p),**read(p)))
 if raw:checks.update(completed_single_layer_matched_seed_same_work_and_samples=True,completed_single_layer_matched_seed_same_external_bytes=True,completed_single_layer_matched_seed_same_SRAM_events_capacity=True,row_major_matched_seed_same_address_fingerprints=True,packed_layout_independent_bijection_test=True)
 result=dict(status='single_layer_ablation_complete_full_pending',scope='Qwen3-4B post-trained shapes/B1/2K/k128/S64; representative address events, no numerical inference/PPL',runs=rows,stream_probes=streams,checks=checks,DDR_peak_GBs=119.424,SRAM_MiB=8,unpriced=['additional DMA descriptors/arbitration/control/interconnect/clock power and area','DDR PHY/VDDQ','full-chip computation/RNG energy not recomputed in this memory-only comparison'])
 (out/'RESULTS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(dict(checks=checks,rows=[{k:r.get(k) for k in ['phase','job','status','time_ms','DDR_core_mJ','effective_total_GBs','time_reduction_percent']} for r in rows]),ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root.resolve())
