"""Real-DRAM small full decode gate before the resource factorial."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from architecture_tlm.unified_v6.test_memory_pipeline_contracts import case
from architecture_tlm.unified_v6.memory_profiles import apply as mem_profile
from architecture_tlm.unified_v6.resource_sweep import apply as resources
from architecture_tlm.unified_v6.model import FullDecode
from architecture_tlm.unified_v6.run import write


def main():
 p=argparse.ArgumentParser();p.add_argument('--bridge',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 a.output.mkdir(exist_ok=False);rows=[]
 for profile in ['anchor_F64','c512_m64','c8192_m512','c32768_m512']:
  pair=[]
  for prefill in [False,True]:
   tag=profile+'_'+str(int(prefill));folder=a.output/tag;folder.mkdir()
   c,m=case();c.update(context_tokens=129,trace_event_limit=50000)
   c['ffn']['mode']='bf16';c['attention']['mode']='exact'
   c=mem_profile(c,'mature_hbm2_pipelined',a.bridge,folder/'dram');c=resources(c,profile,prefill)
   d=FullDecode(c,m);r=d.run();write(folder/'RESULT.json',r)
   active=r['tile_pipeline']['digital'];assert not(active['pending'] or active['active'] or active['staged'])
   assert active['counts']['issued']==active['counts']['retired']
   pair.append(r);rows.append(dict(profile=profile,prefill=prefill,ms=r['metrics']['TPOT_ms'],sha256=hashlib.sha256((folder/'RESULT.json').read_bytes()).hexdigest()))
  # Scheduling changes the timing only, not the operation/transfer ledger.
  for key in ['bf16_mac','fp32_mac','dram_read','dram_write','sram_read','sram_write','digital_local_operand_read_byte']:
   assert pair[0]['actions'][key]==pair[1]['actions'][key],(profile,key)
  assert pair[0]['SRAM']['traffic']==pair[1]['SRAM']['traffic']
  assert pair[0]['DRAM']['traffic']==pair[1]['DRAM']['traffic']
 write(a.output/'GATE.json',dict(status='completed',rows=rows,checks='same MAC, DRAM/SRAM bytes and no live tickets; actual DRAMSys, small shape only'))
 print(json.dumps(rows),flush=True)


if __name__=='__main__':main()
