"""Independent small head simulations; logs remain beside results."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess,sys

root=Path(__file__).resolve().parents[2]
base=root/'work/rayggxia/225/process28_whole_20261109'
workspace=root.parents[1]
common=['--execution',str(base/'execution_b90c17725f50'),'--snapshot',
 str(workspace/'tmp/cross-model245-20261106/work/rayggxia/245/mainline_20261108/revision2/snapshot'),
 '--runtime',str(workspace/'project_archives/ffn_sram_batch204_20261106/runtime'),
 '--dependencies',str(workspace/'project_archives/sram1216_225_20261106/dependencies')]
def run(case):
    mhz,rows=case;out=base/('head_%s_%s'%(mhz,rows))
    assert not out.exists(),out
    with (base/('head_%s_%s.log'%(mhz,rows))).open('xb') as log:
        p=subprocess.run([sys.executable,'-X','utf8','-B',str(Path(__file__).with_name('head_probe.py')),
            *common,'--mhz',str(mhz),'--rows',str(rows),'--out',str(out)],stdout=log,stderr=subprocess.STDOUT)
    return dict(mhz=mhz,rows=rows,exit_code=p.returncode)
with ThreadPoolExecutor(max_workers=4) as pool:
    for r in pool.map(run,[(mhz,rows) for mhz in (250,500) for rows in (1024,1152,2048)]):
        print(r,flush=True)
