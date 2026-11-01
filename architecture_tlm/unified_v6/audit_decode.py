"""Small real-DRAMSys audit cases; frozen baseline path remains unchanged."""
import argparse,json,time,hashlib,math
from pathlib import Path
from .shared_memory import SharedMemory,DRAMSysAsync,dram_energy
from .shared_decode import SharedDecode
from .shared_audit import SharedAudit

CASES=('baseline','credit512','credit1024','mac512','mac4096','nl160','fabric2x','vector128','return_bypass','lm_prefix')
def setup(a):
    credit=512 if a.case=='credit512' else 1024 if a.case=='credit1024' else 256
    b=DRAMSysAsync(a.binary,a.config,credit,a.out/'dramsys.stderr.log',request_gap_ps=0,request_lanes=8)
    h=SharedMemory(b,credit=credit,response_bytes=credit*128,issue_per_cycle=24,return_banks=512,response_buffered=a.case!='return_bypass')
    m=SharedDecode(h,layers=36 if a.case=='lm_prefix' else a.layers,include_lm=False,attention_input=json.loads(a.input.read_bytes()),weight_layout='tile_packed',nl=160 if a.case=='nl160' else 256,
        progress=lambda r:print('PHASE '+json.dumps(r),flush=True))
    if a.case.startswith('mac'):m.mac_lanes=int(a.case[3:])
    if a.case=='fabric2x':h.mem.fabric_words*=2
    if a.case=='vector128':
        m.vector.banks=tuple(range(128));h.mem.bank_allocated=[0]*h.mem.nbank
        for region in h.mem.regions.values():
            words=math.ceil(region.size/h.mem.word)
            for j,bank in enumerate(region.banks):h.mem.bank_allocated[bank]+=(words//len(region.banks)+(j<words%len(region.banks)))*h.mem.word
        assert max(h.mem.bank_allocated)<=h.mem.capacity//h.mem.nbank
    audit=SharedAudit(m).install()
    return b,h,m,audit
def main():
    p=argparse.ArgumentParser();p.add_argument('--case',choices=CASES,required=True);p.add_argument('--layers',type=int,default=1);p.add_argument('--binary',required=True);p.add_argument('--config',required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);start=time.time()
    b,h,m,audit=setup(a)
    try:
        if a.case=='lm_prefix':m.phase('lm_head_prefix4096',[m.digital_matrix(0,'lm_head',4096,m.model['hidden'])],-1);r=dict(scope='isolated cold first4096 vocabulary outputs at full36-layer addresses, not whole lm_head')
        else:r=m.run()
        memory=h.report();final=b.finish(h.now)
        r.update(status='completed',case=a.case,simulated_ms=h.now*1e-6,memory=memory,DRAM=dram_energy(final),audit=audit.report(),wall_seconds=time.time()-start,
            actual_resources=dict(mac_lanes=m.mac_lanes,gu=m.gu,nl=m.nl,credit=h.credit,response_bytes=h.response_bytes,vector_banks=len(m.vector.banks),fabric_words_per_cycle=h.mem.fabric_words),
            input_sha256=hashlib.sha256(a.input.read_bytes()).hexdigest(),not_claimed=['PPL','new_RTL_PPA','500MHz','256GBs_external'],configuration='chip100 / official8chDDR4 / tile_packed / representative event stream')
        (a.out/'RESULT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(dict(case=a.case,ms=r['simulated_ms'],wall_seconds=r['wall_seconds'],status='completed')))
    finally:b.close()
if __name__=='__main__':main()
