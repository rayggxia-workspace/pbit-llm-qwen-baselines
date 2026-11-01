"""Contiguous4MiB memory-service ceiling, same100MHz front, no LLM compute."""
import argparse,json
from pathlib import Path
from .shared_memory import SharedMemory,DRAMSysAsync,dram_energy
from .shared_dma import dma_config

def trial(binary,config,profile,gap,out,lanes):
    c=dma_config(profile,bridge_gap_ps=gap);b=DRAMSysAsync(binary,config,c['credit'],out.with_suffix('.stderr.log'),request_gap_ps=gap,request_lanes=lanes)
    h=SharedMemory(b,credit=c['credit'],issue_per_cycle=c['issue'],response_bytes=c['response_bytes'],return_banks=c['return_banks'])
    h.common_period_ns=10;dst=h.mem.region('stream_target',4194304,range(512))
    try:
        def flow():yield from h.fetch('stream',65536,4194304,dst,0,'weights')
        h.execute([flow()]);r=h.report();final=b.finish(h.now);r['DRAM']=dram_energy(final)
        r.update(profile=profile,gap_ps=gap,lanes=lanes,GBs=4194304/h.now,status='completed')
        assert final['read_bursts']==65536 and final['burst_count']==65536
        out.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n');return r
    finally:b.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--bridge-lanes',type=int,choices=[1,8],default=1);p.add_argument('--binary',required=True);p.add_argument('--config',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    rows=[trial(a.binary,a.config,profile,gap,a.out/(profile+'.json'),a.bridge_lanes) for profile,gap in [('legacy',1000),('wide16',0),('wide24',0)]]
    assert all(r['by_kind']==rows[0]['by_kind'] for r in rows)
    result=dict(status='completed',rows=[dict(profile=r['profile'],lanes=r['lanes'],GBs=r['GBs'],time_ns=r['elapsed_ns'],DRAM_mJ=r['DRAM']['core_total_mJ']) for r in rows])
    (a.out/'STREAM_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result))
if __name__=='__main__':main()
