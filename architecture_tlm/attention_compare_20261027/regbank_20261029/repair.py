"""Resume two ungated controls after empty ICG selection diagnostic; retain proof."""
from runner import *

def repair():
 c=json.loads((S/'CASES.json').read_text())[int(os.environ['SLURM_ARRAY_TASK_ID'])]
 assert c['gated']==0
 m=json.loads((S/'SOURCE.json').read_text())
 for n,h in m['files'].items():assert sha(S/n)==h
 oldroot=Path(os.environ['RB_PREVIOUS_ROOT']);old=oldroot/'results'/c['top']
 oldsrc=json.loads((oldroot/'source/SOURCE.json').read_text())
 for n in ['bank.sv','tb.sv',c['top']+'.sv','dc.tcl','pt.tcl']:
  assert m['files'][n]==oldsrc['files'][n],n
 before=(oldroot/'source/common.tcl').read_text()
 assert (S/'common.tcl').read_text()==before.replace('set gates [get_cells -hierarchical','set gates [get_cells -quiet -hierarchical')
 d=R/'results'/c['top'];d.mkdir();shutil.copytree(str(old/'dc'),str(d/'dc'))
 save(d/'EXECUTION.json',dict(previous=json.loads((old/'EXECUTION.json').read_text()),repair_job=os.environ['SLURM_JOB_ID'],source_sha256=sha(S/'SOURCE.json'),reason='Quiet empty ICG selection for ungated bank; no RTL/DC/constraint changes'))
 checks=[];powers=[]
 os.environ.update(RB_TOP=c['top'],RB_GATED='0',RB_LOAD='.002',RB_NETLIST=str(d/'dc/mapped.v'),RB_SDC=str(d/'dc/mapped.sdc'))
 for phase in ['rtl','gate']:
  for seed in [17,503,1009]:
   run=d/(phase+'_'+str(seed));run.mkdir();vec=S/'vectors'/c['top']/str(seed)
   meta=json.loads((vec/'META.json').read_text());assert sha(vec/'vectors.txt')==meta['vectors_sha256']
   assert oldsrc['files']['vectors/'+c['top']+'/'+str(seed)+'/vectors.txt']==meta['vectors_sha256']
   prev=old/(phase+'_'+str(seed));reused=(prev/'sim.log').exists() and 'PASS cycles=212' in (prev/'sim.log').read_text()
   if reused:
    shutil.copyfile(str(prev/'sim.log'),str(run/'sim.log'))
    if phase=='gate':shutil.copyfile(str(prev/'activity.vcd'),str(run/'activity.vcd'))
   else:
    assert phase=='gate'
    call([str(old/'gate_build/simv'),'+VECTORS='+str(vec/'vectors.txt'),'+VCD='+str(run/'activity.vcd')],run,'sim.log')
   assert 'PASS cycles=212' in (run/'sim.log').read_text()
   checks.append(dict(phase=phase,seed=seed,cycles=212,checked=meta['counts']['checked'],compared_bits=meta['counts']['compared_bits'],log_sha256=sha(run/'sim.log'),reused=reused))
   if phase=='gate':
    for win in meta['windows']:
     p=run/win['name'];p.mkdir()
     os.environ.update(RB_VCD=str(run/'activity.vcd'),RB_START=str(win['start']),RB_END=str(win['end']))
     call(['pt_shell','-f',str(S/'pt.tcl')],p,'pt.log');assert (p/'PT_COMPLETE').exists()
     powers.append(dict(seed=seed,window=win,directory=str(p.relative_to(d))))
 save(d/'COMPLETE.json',dict(case=c,checks=checks,power=powers,netlist_sha256=sha(d/'dc/mapped.v'),sdc_sha256=sha(d/'dc/mapped.sdc')))
 print('REPAIR_COMPLETE',c['top'])
if __name__=='__main__':repair()
