"""Independent per-case processes; no shared native DRAM output directory."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,subprocess,sys,time
H=Path(__file__).resolve().parent;ROOT=H.parents[3]
old=json.loads((H.parent/'update250_20261109/EXTRA_PLAN.json').read_bytes())['command']
py=old[0];common=old[old.index('--snapshot'):old.index('--cores')]
common[common.index('--bindings')+1]=str(ROOT/'architecture_tlm/process_28nm/250MHz/BINDINGS.json')
common+=['--macros',str(ROOT/'architecture_tlm/process_28nm/250MHz/WHOLE_CONFIG.json')]
script=ROOT/'architecture_tlm/process_28nm/cross_models_20261110/run.py'
cases=[(m,s) for m in ('llama32_3b','deepseek_7b') for s in ('SC_ising','BF16_dense','W8_dense','W8_screen')]
def run(case):
    model,scheme=case;name=model+'_'+scheme
    cmd=[py,'-X','utf8','-B',str(script)]+common+['--model',model,'--scheme',scheme,
        '--layers','1','--head','--head-probe-rows','384','--out',str(H/('gate_'+name))]
    rec=dict(model=model,scheme=scheme,command=cmd,started=time.time())
    with (H/(name+'_gate.log')).open('wb') as log:p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    rec.update(exit_code=p.returncode,wall_seconds=time.time()-rec['started'])
    (H/(name+'_gate_exit.json')).write_text(json.dumps(rec,indent=2)+'\n')
    print(json.dumps(rec),flush=True);return rec
with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,cases))
(H/'LOCAL_GATES.json').write_text(json.dumps(results,indent=2)+'\n')
raise SystemExit(0 if all(x['exit_code']==0 for x in results) else 1)
