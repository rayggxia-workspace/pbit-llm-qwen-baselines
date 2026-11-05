"""Supplemental STA only. Uses immutable v6 mapped netlists, never edits them.

Reset is released near falling clock edge, as in the executed benches.
All data constraints are unchanged; recovery/removal remain enabled.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,tarfile

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(root,out,index):
 roots={0:'ppa_38444776_0',1:'ppa_38444750_1',2:'ppa_38444776_2',3:'ppa_38444776_3',4:'ppa_38444776_4'}
 old=root/'results'/roots[index];original=json.loads((old/'RESULT.json').read_text())
 net=old/'synthesis/mapped.v';assert sha(net)==original['mapped_sha256']
 out.mkdir(parents=True,exist_ok=False)
 cfg=(old/'configuration.tcl').read_bytes();(out/'configuration.tcl').write_bytes(cfg)
 env=dict(os.environ,CV2_CONFIG=str(out/'configuration.tcl'),CV2_FLOW=str(root/'flow'))
 tcl='''source [file join $::env(CV2_FLOW) common.tcl]
proc main {} {
 library_setup pt
 read_verilog {NET}
 current_design TOP
 if {![link]} {error "PT link failed"}
 constraints
 # Same external data contract. Async assertion; release in [4.5,5.5]ns.
 # This is an explicit environment requirement, not a false path or waiver.
 set_input_delay -min 4.5 -clock core [get_ports rst_n]
 set_input_delay -max 5.5 -clock core [get_ports rst_n]
 timing_reports pt
 capture data_setup.rpt {report_timing -delay_type max -group core -max_paths 20 -slack_lesser_than 100}
 capture data_hold.rpt {report_timing -delay_type min -group core -max_paths 20 -slack_lesser_than 100}
 write_sdc reset_contract.sdc
 save_text STAGE_COMPLETE "reset contract STA only; mapped netlist unchanged"
}
if {[catch {main} message]} {save_text FAILURE.txt "$message\\n$::errorInfo";puts stderr $message;exit 2}
exit 0
'''.replace('NET',str(net)).replace('TOP','bf_'+original['case']['name'])
 (out/'run.tcl').write_text(tcl)
 with (out/'pt.log').open('wb') as f:
  p=subprocess.run(['pt_shell','-f','run.tcl'],cwd=str(out),env=env,stdout=f,stderr=subprocess.STDOUT)
 assert p.returncode==0 and (out/'STAGE_COMPLETE').is_file()
 assert sha(net)==original['mapped_sha256']
 r=dict(case=original['case']['name'],status='completed',mapped_sha256=sha(net),original_result_sha256=sha(old/'RESULT.json'),data_constraints='unchanged',reset_deassertion_min_ns=4.5,reset_deassertion_max_ns=5.5,no_false_paths=True,no_multicycle=True,setup_slack_ns=float((out/'setup_slack_ns.txt').read_text()),hold_slack_ns=float((out/'hold_slack_ns.txt').read_text()))
 (out/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n')
 files=[x for x in out.iterdir() if x.is_file() and x.name!='library_private.rpt']
 (out/'RETURN_MANIFEST.json').write_text(json.dumps({'files':{x.name:sha(x) for x in files}},indent=2)+'\n')
 with tarfile.open(str(out/'reports.tar.gz'),'w:gz') as t:
  for x in files+[out/'RETURN_MANIFEST.json']:t.add(str(x),arcname=x.name)
 print(json.dumps(r))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--case',type=int,required=True);a=p.parse_args();main(a.root,a.out.resolve(),a.case)
