"""Small real RTL wave checks; no licensed EDA or full64 rerun."""
import hashlib,json,re,subprocess,sys,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[3]
ROOT=REPO/'architecture_tlm/counter_rtl_compare'
BASE=REPO.parents[1]
sys.path[:0]=[str(ROOT/'flow'),str(ROOT/'sim')]
from generate import make
from wave import clip
from scalar_vcd import scalarize

def main():
    dest=Path(sys.argv[1]).resolve();dest.mkdir(parents=True,exist_ok=False)
    tool=BASE/'sc_weight_storage_or4_20261014/tools/iverilog'
    ivl=tool/'lib/ivl';records=[]
    src=list(sorted((ROOT/'rtl').glob('*.sv')))+[ROOT/'sim/tb.sv']
    with zipfile.ZipFile(BASE/'sc_counter_compare_20261023.zip') as z:
        for p in src:
            assert p.read_bytes()==z.read('counter_rtl_compare/'+p.relative_to(ROOT).as_posix())
    for arch in (0,1):
        folder=dest/('a'+str(arch));folder.mkdir()
        v=make(folder/'vectors',4,2,1,17,4,'mixed')
        exe=folder/'sim.vvp'
        cmds=[[tool/'bin/iverilog.exe','-B',ivl,'-g2012','-s','tb_counter','-o',exe,'-DARCH='+str(arch),'-DN=4','-DM=2','-DT=1','-DPIPE=1']+src,
            [tool/'bin/vvp.exe','-M',ivl,exe,'+DIR='+str(folder/'vectors'),'+FRAMES='+str(v['frames']),'+MODE=0','+VCD='+str(folder/'raw.vcd')]]
        for i,cmd in enumerate(cmds):
            result=subprocess.run([str(c) for c in cmd],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True,timeout=90)
            (folder/('command%d.log'%i)).write_text(result.stdout,encoding='utf-8')
            assert result.returncode==0,result.stdout
        log=result.stdout;assert 'COUNTER_PASS' in log
        start=float(re.search(r'WINDOW_BEGIN time_ns=([\d.]+)',log)[1])
        end=float(re.search(r'WINDOW_END time_ns=([\d.]+)',log)[1])
        cycles=int(re.search(r'active_cycles=(\d+)',log)[1]);assert cycles==v['frames']*5
        for label,a,b in [('active',start,end),('idle',end,end+640)]:
            audit=clip(folder/'raw.vcd',folder/(label+'.vcd'),a,b);assert audit['xz_signals']==0
            stats=scalarize(folder/(label+'.vcd'),folder/(label+'_scalar.vcd'),88)
            assert len(stats['expected_activity'])==90
            records.append(dict(arch=arch,window=label,checked_output_clock_bits=90,frames=v['frames'],cycles=cycles,xz_signals=0))
    report=dict(status='PASS',scope='N4 M2 T1 PIPE1 RTL waves only; no DC/VCS/PT',records=records,
        rtl_tb_unchanged_from_original_zip=True,source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in src})
    (dest/'VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
if __name__=='__main__':main()
