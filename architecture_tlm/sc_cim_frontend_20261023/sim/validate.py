import argparse,hashlib,json,subprocess,time
from pathlib import Path
from vectors import make


def main():
    a=argparse.ArgumentParser();a.add_argument('--iverilog',required=True);a.add_argument('--vvp',required=True)
    a.add_argument('--ivl-lib');a.add_argument('--out',type=Path,required=True)
    a.add_argument('--profile',choices=['compact','full'],default='compact')
    x=a.parse_args()
    x.iverilog=str(Path(x.iverilog).resolve());x.vvp=str(Path(x.vvp).resolve())
    if x.ivl_lib:x.ivl_lib=str(Path(x.ivl_lib).resolve())
    root=Path(__file__).resolve().parents[1];out=x.out.resolve();out.mkdir(parents=True,exist_ok=False)
    records=[];logs=[]
    configs=[(4,3,32,32,0,0),(64,1,32,1,0,0),(64,8,64,32,0,0),
             (64,64,32,32,0,0),(64,64,32,32,1,0),(64,1,32,32,0,1),
             (64,64,32,32,0,2),(64,64,32,32,0,3),(8,4,256,256,0,0)]
    if x.profile=='compact':
        configs=[(n,(1 if kind==3 else 8) if m==64 else m,t,k,ext,kind) for n,m,t,k,ext,kind in configs]
    def call(cmd,cwd):
        started=time.time();p=subprocess.run([str(v) for v in cmd],cwd=str(cwd),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=180)
        logs.append(dict(command=[str(v) for v in cmd],exit_code=p.returncode,seconds=time.time()-started,output=p.stdout))
        if p.returncode:raise RuntimeError(p.stdout)
        return p.stdout
    try:
        for n,m,t,k,ext,kind in configs:
            case=out/('n%d_m%d_t%d_k%d_e%d_kind%d'%(n,m,t,k,ext,kind));case.mkdir()
            binary=case/'sim.vvp'
            cmd=[x.iverilog]+(['-B',x.ivl_lib] if x.ivl_lib else [])+['-g2012','-s','tb','-o',binary]
            cmd+=['-D%s=%d'%v for v in [('N',n),('M',m),('T',t),('K',k),('EXT',ext),('KIND',kind)]]
            call(cmd+sorted((root/'rtl').glob('*.sv'))+[root/'sim/tb.sv'],case)
            for seed in [1,17,0x12345]:
                vdir=case/('seed%d'%seed);r=make(vdir,n,m,t,k,ext,kind,seed)
                text=call([x.vvp]+(['-M',x.ivl_lib] if x.ivl_lib else [])+[binary,'+DIR='+str(vdir),'+CYCLES='+str(r['cycles'])],case)
                if 'CIM_PASS' not in text:raise RuntimeError('no PASS marker')
                records.append(dict(n=n,m=m,t=t,k=k,ext=ext,kind=kind,seed=seed,cycles=r['cycles'],accepted=r['accepted'],passed=True))
            print('PASS',case.name,flush=True)
    finally:
        with (out/'COMMANDS.json').open('w',encoding='utf-8',newline='\n') as f:json.dump(logs,f,indent=2);f.write('\n')
    result=dict(status='PASS',profile=x.profile,scope='RTL functional only; no DC/STA/PT/physical SRAM/PPL',cases=records,
                source_sha256={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'rtl').glob('*.sv'))},
                total_cycles=sum(c['cycles'] for c in records),
                tools={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [x.iverilog,x.vvp]})
    with (out/'VALIDATION.json').open('w',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(dict(cases=len(records),cycles=result['total_cycles'])))


if __name__=='__main__':main()
