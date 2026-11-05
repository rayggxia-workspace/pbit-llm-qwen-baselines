"""Actual closed-loop DRAM microbench and unchanged DDR regression."""
import argparse,collections,hashlib,json,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from architecture_tlm.dramsys_backend import DRAMSysExternal
from architecture_tlm.unified_v6.config import load
from architecture_tlm.unified_v6.memory_profiles import apply
from architecture_tlm.unified_v6.run import write
class Layout:
 total_bytes=16*1024**3
 regions={}
def one(out,profile,bridge,pattern):
 c,_=load('qwen3_4b');cfg=apply(c,profile,bridge,out/'trace')['dram']
 energy=collections.Counter();traffic=collections.Counter()
 d=DRAMSysExternal(cfg,energy,traffic,Layout());t=0.;logical=0;times=[]
 n=4*1024**2
 try:
  for i in range(4):
   start=t
   if pattern=='scatter':
    spans=[(i*2**22+64+j*256,64) for j in range(256)]
    t=d.access_sg(t,spans,'probe',False);logical+=256*64
   else:
    w=pattern=='write' or (pattern=='mixed' and i%2==1)
    t=d.access(t,n,'probe',w,i*n);logical+=n
   times.append(t-start)
  detail=d.finish(t)
 finally:d.close()
 assert detail['burst_count']==logical//64
 assert detail['capacity_bytes']==16*1024**3
 if profile.startswith('mature_hbm2'):
  assert not energy and not detail['energy_valid'] and not detail['power_at_system_end']
 else:assert detail['energy_valid']
 return dict(profile=profile,bridge_sha256=hashlib.sha256(pathlib.Path(bridge).read_bytes()).hexdigest(),pattern=pattern,physical_bytes=logical,elapsed_ns=t,interval_ns=times,effective_GBs=logical/t,energy=dict(energy),details=detail)
def main():
 p=argparse.ArgumentParser();p.add_argument('--bridge',required=True);p.add_argument('--old-bridge',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);rows=[]
 for pattern in ('read','write','mixed','scatter'):
  old=one(a.output/('old_'+pattern),'mature_ddr4',a.old_bridge,pattern)
  new=one(a.output/('new_'+pattern),'mature_ddr4',a.bridge,pattern)
  assert old['interval_ns']==new['interval_ns'],('DDR changed',pattern)
  assert old['energy']==new['energy'],('DDR energy changed',pattern)
  rows.extend([old,new])
  for profile in ('mature_hbm2_narrow','mature_hbm2_wide','mature_hbm2_pipelined'):
   rows.append(one(a.output/(profile+'_'+pattern),profile,a.bridge,pattern))
 write(a.output/'RESULTS.json',dict(status='completed',rows=rows,ddr_exact_regression=True,scope='actual DRAMSys timing; HBM energy not calibrated'))
 print(json.dumps([dict(profile=r['profile'],pattern=r['pattern'],GBs=r['effective_GBs']) for r in rows]),flush=True)
if __name__=='__main__':main()
