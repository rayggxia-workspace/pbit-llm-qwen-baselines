"""Capacity feasibility only: no timing run or numeric/model quality claim."""
import json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.model import FullDecode

def main():
 rows=[]
 for context in (2048,8192):
  for mode in ('w8','sc'):
   for chunk in (32768,65536,131072,262144):
    for mb,banks in ((1,16),(2,32),(4,64),(8,64)):
     c,m=load('qwen3_4b');c.update(context_tokens=context,schedule_policy='shared_tiles',weight_chunk_bytes=chunk,digital_weight_chunk_bytes=chunk)
     c['ffn'].update(mode=mode,weight_schedule='dma_prefetch',prefetch_across_input_groups=True,local_weight_load_bytes_per_cycle=1024)
     c['sram'].update(capacity_bytes=mb*1024**2,banks=banks,fabric_GBs=64.)
     base=dict(context=context,ffn=mode,digital_chunk_bytes=chunk,configured_MiB=mb,banks=banks)
     try:
      d=FullDecode(c,m);mem=d.mem.report(0)
      rows.append(dict(base,legal=True,SRAM_reserved_bytes=d.arena.peak,physical_bytes=mem['physical_bytes'],macros=mem['macros'],bank_peak_GBs=mem['bank_peak_GBs'],fabric_GBs=c['sram']['fabric_GBs'],macro_area_mm2=mem['area_mm2'],core_latency_run=False))
     except ValueError as e:rows.append(dict(base,legal=False,reason=str(e),core_latency_run=False))
 print(json.dumps(dict(scope='static capacity and measured-macro count audit; no timing or quality result; local operator storage separate',rows=rows),indent=2))
if __name__=='__main__':main()
