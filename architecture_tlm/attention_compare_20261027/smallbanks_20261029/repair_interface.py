"""Re-evaluate unchanged mapped array with explicit falling-edge request contract.
Original setup/hold violations and power reports remain immutable.
"""
import json,os,subprocess
from pathlib import Path
S=Path(os.environ['SB_SOURCE']);R=Path(os.environ['SB_ARRAY_RESULTS'])
original=json.loads((R/'COMPLETE.json').read_text())
dest=R.parent/'interface_results';dest.mkdir(exist_ok=False)
os.environ['SB_FALLING_INTERFACE']='1'
out=[]
for w in original['windows']:
    d=dest/w['directory'];d.mkdir(parents=True)
    vcd=R/Path(w['directory']).parent/'activity.vcd'
    os.environ.update(SB_VCD=str(vcd),SB_START=str(w['start_ns']),SB_END=str(w['end_ns']))
    with (d/'pt.log').open('w') as f:
        p=subprocess.run(['pt_shell','-f',str(S/'pt.tcl')],cwd=str(d),stdout=f,stderr=subprocess.STDOUT)
    assert p.returncode==0 and (d/'COMPLETE').exists()
    out.append(w)
    (dest/'PROGRESS.json').write_text(json.dumps(out,indent=2)+'\n')
(dest/'COMPLETE.json').write_text(json.dumps(dict(windows=out,source_checks=original['checks'],contract='falling-edge input launch [0,1] ns; rising-edge SRAM capture; 100 MHz'),indent=2)+'\n')
