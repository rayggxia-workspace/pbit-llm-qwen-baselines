import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
from generate import make
def main():
    a=argparse.ArgumentParser();a.add_argument('--iverilog',required=True);a.add_argument('--vvp',required=True)
    a.add_argument('--ivl-lib');a.add_argument('--out',type=Path,required=True);a.add_argument('--full',action='store_true')
    x=a.parse_args();root=Path(__file__).resolve().parents[1];out=x.out.resolve();out.mkdir(parents=True,exist_ok=False)
    records=[];commands=[]
    configs=[(4,2,1),(64,1,16),(64,1,32),(64,1,64),(64,8,32)]
    if x.full:configs=[(64,64,32)]
    def call(cmd,cwd):
        start=time.time();p=subprocess.run([str(i) for i in cmd],cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=600)
        commands.append(dict(cmd=[str(i) for i in cmd],rc=p.returncode,seconds=time.time()-start,log=p.stdout))
        if p.returncode:raise RuntimeError(p.stdout)
        return p.stdout
    try:
        for n,m,t in configs:
            c=out/('n%d_m%d_t%d'%(n,m,t));c.mkdir()
            v=make(c/'vectors',n,m,t,17,2 if x.full else 8)
            for pipe in ([1] if x.full else [0,1]):
                for arch in [0,1]:
                    tag='a%d_p%d'%(arch,pipe);binary=c/(tag+'.vvp')
                    cmd=[x.iverilog]+(['-B',x.ivl_lib] if x.ivl_lib else [])+['-g2012','-s','tb_counter','-o',binary,
                      '-DARCH=%d'%arch,'-DN=%d'%n,'-DM=%d'%m,'-DT=%d'%t,'-DPIPE=%d'%pipe]+sorted((root/'rtl').glob('*.sv'))+[root/'sim/tb.sv']
                    call(cmd,c)
                    for mode in ([0] if x.full else [0,1]):
                        cmd=[x.vvp]+(['-M',x.ivl_lib] if x.ivl_lib else [])+[binary,'+DIR='+str(c/'vectors'),'+FRAMES='+str(v['frames']),'+MODE='+str(mode),'+RESET_TEST='+str(mode)]
                        log=call(cmd,c);assert 'COUNTER_PASS' in log
                        (c/(tag+'_mode%d.log'%mode)).write_text(log,encoding='utf-8')
                        records.append(dict(n=n,m=m,t=t,pipe=pipe,arch=arch,mode=mode,frames=v['frames'],outputs=v['bin_outputs'],passed=True))
                        print('PASS',records[-1],flush=True)
    finally:(out/'COMMANDS.json').write_text(json.dumps(commands,indent=2)+'\n',encoding='utf-8')
    result=dict(status='PASS',scope='RTL functional only; no synthesis/STA/PT/PPL',cases=records,
      total_outputs=sum(v['outputs'] for v in records),
      source_sha256={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'rtl').glob('*.sv'))},
      tools={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [x.iverilog,x.vvp]})
    (out/'VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(cases=len(records),outputs=result['total_outputs'])))
if __name__=='__main__':main()
