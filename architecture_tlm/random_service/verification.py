"""Generate exact integrated Python/RTL traces, then run Icarus (or use TB in VCS).

RTL outputs/handshakes/internal state are checked EVERY edge including stalls.
No EDA power results are generated. Test PRNG seeds are explicitly deterministic.
"""
import argparse
import hashlib
import json
import random
import shutil
import subprocess
from pathlib import Path
from .model import Endpoint, SeedIngress

ROOT=Path(__file__).resolve().parent
KINDS=['lfsr32','lfsr32_shared64','bivium']
RTL=['rng_lfsr32_map.sv','rng_shared64_map.sv','rng_bivium_map.sv',
     'rng_endpoint.sv','rng_seed_ingress.sv','rng_seeded_top.sv','rng_ffn_shared64.sv']

def pack(values,width):
    return sum(int(x)<<(width*i) for i,x in enumerate(values))

def traces(kind,seed,cycles=900,reseed_cycles=37,scenario='stress'):
    r=random.Random(seed);p=Endpoint(kind,reseed_cycles);g=SeedIngress(p.profile['state_bits'])
    inputs=[];expected=[]
    for i in range(cycles):
        rst=int(i not in (0,251,601))
        req=int(i%80<65)
        ready=int(i%53<35)
        command=0
        if p.seeded and not p.warm and not p.valid:
            if not p.locked and not p.due and i%7==0:command=1
            elif p.locked and i%11==0:command=2
            elif p.locked and i%17==0:command=3
        # First packet is zero, forcing rejection; no hidden fixed fallback.
        word=0 if p.counts['zero_seeds_rejected']==0 else r.getrandbits(32)
        valid=int(i%4!=0)
        qualified=int(not (i>700 and i%19==0))
        q=[r.choice([0,256,r.randrange(257)]) for _ in range(p.profile['lanes'])]
        if scenario!='stress':
            rst=int(i!=0);command=0;qualified=1;valid=int(i%4!=0);word=r.getrandbits(32)
            ready=int(scenario!='stall' or i%64<16)
            req=int(scenario!='idle' and (scenario!='burst32' or i%128<32))
            # Stable probabilities per 32-sample tile, no fictional per-cycle table load.
            q=[(j*37+(i//32)*13)%257 for j in range(p.profile['lanes'])]
        pre=p.signals(ready,g.valid,command)
        wr=g.ready(pre['seed_req'])
        data=p.tick(req,q,ready,g.valid,g.packet,command,rst)
        gi=g.tick(pre['seed_req'],pre['seed_ready'],valid,word,qualified,rst)
        inputs.append([rst,req,ready,command,valid,word,qualified,pack(q,9)])
        expected.append([int(pre['req_ready']),int(pre['cmd_ready']),int(wr),int(pre['seed_req']),
            int(p.valid),pack(p.words,8),pack(p.bits,1),int(g.fault),int(p.error),
            p.epoch,p.state,p.warm,int(p.locked),p.age,int(p.seeded)])
    return inputs,expected,dict(endpoint=p.report(),ingress=dict(g.counts))

def write_vectors(directory,kind,seed,cycles,reseed_cycles=37,scenario='stress'):
    directory.mkdir(parents=True,exist_ok=False)
    inp,exp,report=traces(kind,seed,cycles,reseed_cycles,scenario)
    report.update(scenario=scenario,reseed_cycles=reseed_cycles,
                  clock_ns=10,analysis_window_ns=[1000,cycles*10],
                  activity_source='synthetic fixture; not real LLM activations')
    for name,rows in [('stim.hex',inp),('expected.hex',exp)]:
        (directory/name).write_text(''.join(' '.join(format(x,'x') for x in row)+'\n' for row in rows),
                                    encoding='ascii',newline='\n')
    (directory/'operations.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--iverilog');ap.add_argument('--vvp')
    ap.add_argument('--cycles',type=int,default=900)
    ap.add_argument('--vcd',action='store_true')
    ap.add_argument('--scenario',choices=['stress','stream','idle','burst32','stall'],default='stress')
    ap.add_argument('--reseed-cycles',type=int,default=37)
    ap.add_argument('--seeds',type=int,nargs='+',default=[17,503,1009])
    args=ap.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    iv=args.iverilog or shutil.which('iverilog');vvp=args.vvp or shutil.which('vvp')
    results=[]
    for k,kind in enumerate(KINDS):
        for seed in args.seeds:
            d=out/('%s_%d'%(kind,seed))
            rep=write_vectors(d,kind,seed,args.cycles,args.reseed_cycles,args.scenario)
            row=dict(kind=kind,seed=seed,cycles=args.cycles,status='VECTORS_ONLY',operations=rep)
            if iv and vvp:
                exe=d/'sim.vvp'
                cmd=[iv,'-g2012','-s','tb_rng_service','-Ptb_rng_service.KIND=%d'%k,
                     '-Ptb_rng_service.RESEED_CYCLES=%d'%args.reseed_cycles,
                     '-o',str(exe)]+[str(ROOT/'rtl'/f) for f in RTL]+[str(ROOT/'tb/tb_rng_service.sv')]
                c=subprocess.run(cmd,text=True,capture_output=True)
                (d/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
                if c.returncode:raise RuntimeError('compile failed: '+str(d))
                cmd2=[vvp,str(exe),'+STIM='+str(d/'stim.hex'),'+EXPECTED='+str(d/'expected.hex')]
                if args.vcd:cmd2.append('+VCD='+str(d/'activity.vcd'))
                s=subprocess.run(cmd2,text=True,capture_output=True)
                (d/'simulation.log').write_text(s.stdout+s.stderr,encoding='utf-8')
                if s.returncode or 'PASS edges=%d'%args.cycles not in s.stdout:
                    raise RuntimeError('RTL mismatch: '+str(d)+'\n'+s.stdout+s.stderr)
                row['status']='RTL_MATCH_EVERY_EDGE';row['commands']=[cmd,cmd2]
            row['vector_sha256']={n:hashlib.sha256((d/n).read_bytes()).hexdigest() for n in ('stim.hex','expected.hex')}
            results.append(row)
    frontend='NOT_RUN'
    if iv and vvp:
        exe=out/'ffn.vvp'
        cmd=[iv,'-g2012','-s','tb_rng_ffn','-o',str(exe)]+[str(ROOT/'rtl'/f) for f in RTL]+[str(ROOT/'tb/tb_rng_ffn.sv')]
        c=subprocess.run(cmd,text=True,capture_output=True)
        (out/'ffn_compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
        if c.returncode:raise RuntimeError('FFN compile failed')
        s=subprocess.run([vvp,str(exe)]+(['+VCD='+str(out/'ffn.vcd')] if args.vcd else []),text=True,capture_output=True)
        (out/'ffn_simulation.log').write_text(s.stdout+s.stderr,encoding='utf-8')
        if s.returncode or 'PASS FFN' not in s.stdout:raise RuntimeError('FFN simulation failed: '+s.stdout+s.stderr)
        frontend=s.stdout.strip()
    (out/'RESULTS.json').write_text(json.dumps(dict(cases=results,frontend=frontend,physical_ppa=None),indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(cases=len(results),edges=sum(x['cycles'] for x in results),
                         status=[x['status'] for x in results]),indent=2))

if __name__=='__main__':main()

