"""Small actual-DRAMSys arbitration/streaming checks, no EDA or model run."""
from pathlib import Path
import argparse,json
from .shared_memory import SharedMemory,DRAMSysAsync,dram_energy

def trial(binary,config,out,serial,quantum=1):
    b=DRAMSysAsync(binary,config,64,out.with_suffix('.stderr.log'))
    h=SharedMemory(b,descriptor_serial=serial,owner_quantum=quantum)
    target=[h.mem.region('target'+str(j),16384,range(32*j+32,32*j+64)) for j in range(4)]
    def worker(j):
        for k in range(4):
            yield from h.fetch('requester'+str(j),65536+j*1048576+k*16384,16384,target[j],0,'weights')
            yield from h.delay(660)
    try:
        h.execute([worker(j) for j in range(4)]);r=h.report();r['DRAM']=dram_energy(b.finish(h.now))
        assert r['counts']['dram_read_bytes']==4*4*16384
        assert r['counts']['descriptors_completed']==16
        assert r['counts']['peak_outstanding']<=64
        out.write_text(json.dumps(r,indent=2)+'\n');return r
    finally:b.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--config',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    s=trial(a.binary,a.config,a.out/'serial.json',True)
    n=trial(a.binary,a.config,a.out/'async.json',False)
    q=trial(a.binary,a.config,a.out/'quantum16.json',False,16)
    q32=trial(a.binary,a.config,a.out/'quantum32.json',False,32)
    assert s['by_kind']==n['by_kind']==q['by_kind']==q32['by_kind']
    print(json.dumps(dict(status='PASS',serial_ns=s['elapsed_ns'],async_RR1_ns=n['elapsed_ns'],quantum16_ns=q['elapsed_ns'],quantum32_ns=q32['elapsed_ns'],same_bytes=True,
        DRAM_core_mJ=[v['DRAM']['core_total_mJ'] for v in [s,n,q,q32]])))
if __name__=='__main__':main()
