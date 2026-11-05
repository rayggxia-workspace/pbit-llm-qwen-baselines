"""Real persistent DRAMSys SG/serialized comparison, deterministic addresses."""
import argparse,hashlib,json,pathlib,platform,sys,time
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from dramsys_backend import DRAMSysExternal
from collections import defaultdict

def write(path,value):
 with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2);f.write('\n')

def main():
 p=argparse.ArgumentParser();p.add_argument('--bridge',required=True);p.add_argument('--config',required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--commit',required=True);a=p.parse_args()
 if a.output.exists():raise ValueError('sealed output exists')
 a.output.mkdir(parents=True)
 cases={'contiguous':[(0,65536)],'strided64':[(i*2048,256) for i in range(64)],'many1024':[(i*2048,256) for i in range(1024)],'write_append':[(i*4096,64) for i in range(128)]}
 rows=[]
 for name,ranges in cases.items():
  for sg in (False,True):
   energy,traffic=defaultdict(float),defaultdict(int)
   cfg=dict(bridge_executable=a.bridge,configuration=a.config,output_prefix=str(a.output/(name+('_sg' if sg else '_serialized'))),max_pending=32,sg_max_spans=256,strict_time_order=True)
   space=SimpleNamespace(total_bytes=4*1024**2,regions={})
   b=DRAMSysExternal(cfg,energy,traffic,space);t=0.;wall=time.monotonic();write_mode=name=='write_append'
   if sg:
    for i in range(0,len(ranges),256):t=b.access_sg(t,ranges[i:i+256],name,write_mode)
   else:
    for address,size in ranges:t=b.access(t,size,name,write_mode,address)
   final=b.finish(t)
   expected=sum(size for _,size in ranges)//64
   assert final['status']=='finished' and final['burst_count']==expected
   rows.append(dict(case=name,sg=sg,done_ns=t,macro_requests=b.counter,bursts=expected,bytes=expected*64,range_sha256=hashlib.sha256(json.dumps(ranges).encode()).hexdigest(),wall_seconds=time.monotonic()-wall,raw_DRAMPower_core_J=energy['external_DRAMPower_core'],config_sha256=b.config_hash,bridge_features=sorted(b.features),details=final))
 for name in cases:
  pair=[r for r in rows if r['case']==name]
  assert len({r['range_sha256'] for r in pair})==1 and len({r['bursts'] for r in pair})==1
 write(a.output/'RESULT.json',dict(status='completed',scope='real DRAMSys mechanism probe; not full model or calibrated energy',execution_commit=a.commit,python=platform.python_version(),command=sys.argv,bridge_sha256=hashlib.sha256(pathlib.Path(a.bridge).read_bytes()).hexdigest(),rows=rows))
 files={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in a.output.iterdir() if p.is_file()}
 write(a.output/'MANIFEST.json',dict(status='completed',files=files))
 print(json.dumps([dict(case=r['case'],sg=r['sg'],done_ns=r['done_ns'],requests=r['macro_requests']) for r in rows]),flush=True)
if __name__=='__main__':main()
