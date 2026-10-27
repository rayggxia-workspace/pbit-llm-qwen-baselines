"""Mapped-netlist replay using private zero-delay Liberty-derived cell models."""
import argparse
import json
from pathlib import Path
import subprocess
from .validate import HERE,sha,write,generate


def main():
    p=argparse.ArgumentParser();p.add_argument('--netlist',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True);p.add_argument('--top',required=True)
    p.add_argument('--vectors',type=Path);p.add_argument('--golden-log',type=Path)
    p.add_argument('--fresh',action='store_true');p.add_argument('--prep',type=int,default=2)
    p.add_argument('--early',type=int,default=0);p.add_argument('--cycles',type=int,default=640)
    p.add_argument('--mode',choices=['stress','cap','three','all'],default='stress');p.add_argument('--vcd',action='store_true')
    p.add_argument('--iverilog',type=Path,required=True);p.add_argument('--vvp',type=Path,required=True)
    p.add_argument('--ivl-lib',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);binary=(a.output/'gate.vvp').resolve()
    if a.fresh:
        stim,pre,post,coverage,timing=generate(512,a.prep,1,17,a.mode,cycles=a.cycles,early=a.early,rankcap=64)
        a.vectors=a.output/'vectors.txt';a.golden_log=a.output/'oracle.log'
        a.vectors.write_bytes(('\n'.join(' '.join(format(v,'x') for v in x) for x in stim)+'\n').encode())
        lines=[]
        for i,(before,after) in enumerate(zip(pre,post)):
            lines+=['P '+str(i)+' '+' '.join(map(str,before)),'C '+str(i)+' '+' '.join(map(str,after))]
        a.golden_log.write_bytes(('\n'.join(lines)+'\n').encode())
    if a.vectors is None or a.golden_log is None:p.error('provide vectors/golden or --fresh')
    cmd=[str(a.iverilog),'-B',str(a.ivl_lib),'-g2012','-s','tb_gate_winner','-DAC_TOP='+a.top,
          '-o',str(binary),str(a.models),str(a.netlist),str(HERE/'rtl/tb_gate_winner.sv')]
    c=subprocess.run(cmd,capture_output=True,text=True);(a.output/'compile.log').write_bytes((c.stdout+c.stderr).encode())
    if c.returncode:raise RuntimeError(c.stderr)
    command=[str(a.vvp),'-M',str(a.ivl_lib),str(binary),'+VECTORS='+str(a.vectors.resolve())]
    if a.vcd:command+=['+VCD='+str((a.output/'gate.vcd').resolve())]
    r=subprocess.run(command,capture_output=True,text=True)
    (a.output/'gate.log').write_bytes((r.stdout+r.stderr).encode())
    def parse(s,trim):
        rows=[]
        for line in s.splitlines():
            if line.startswith('P ') or line.startswith('C '):
                values=line.split();count=11 if values[0]=='P' else 7
                if trim:values=values[:count]
                if any(v in ('x','z') for v in values):raise RuntimeError('unknown signal')
                rows.append(values)
        return rows
    expected=parse(a.golden_log.read_text(),True);actual=parse(r.stdout,False)
    if r.returncode or expected!=actual:
        diffs=[dict(i=i,expected=x,actual=y) for i,(x,y) in enumerate(zip(expected,actual)) if x!=y]
        write(a.output/'FAIL.json',dict(expected=len(expected),actual=len(actual),diffs=diffs[:10]));raise RuntimeError('gate mismatch')
    write(a.output/'VALIDATION.json',dict(status='pass',top=a.top,compared_edges=len(actual),cycles=len(actual)//2,
         source_sha256=sha(HERE/'rtl/tb_gate_winner.sv'),models_sha256=sha(a.models),netlist_sha256=sha(a.netlist),
         vectors_sha256=sha(a.vectors),golden_sha256=sha(a.golden_log),log_sha256=sha(a.output/'gate.log'),
         sdf=False,sta='not_run',power='not_run',boundary='private Liberty-derived zero-delay functional model; no vendor timing checks'))
    print(dict(status='pass',top=a.top,cycles=len(actual)//2))


if __name__=='__main__':main()
