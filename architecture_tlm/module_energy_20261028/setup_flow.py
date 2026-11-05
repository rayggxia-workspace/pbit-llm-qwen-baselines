from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parent;OLD=ROOT.parent/'matrix_single_scale_20261028/flow';FLOW=ROOT/'flow';FLOW.mkdir(exist_ok=True)
names=['common.tcl','library_conditions.tcl','dc.tcl','power_bulk.tcl','power_vcd.py','power_parse.py','constant_ports.py','vcd_alias_v2.py']
hashes={}
for n in names:
 shutil.copyfile(OLD/n,FLOW/n);hashes[n]=hashlib.sha256((FLOW/n).read_bytes()).hexdigest()
# Reuse hardened utility functions without rewriting immutable upstream code.
shutil.copyfile(OLD/'run_isolated.py',FLOW/'upstream.py');hashes['upstream.py']=hashlib.sha256((FLOW/'upstream.py').read_bytes()).hexdigest()
(ROOT/'FLOW_UPSTREAM.json').write_text(json.dumps({'commit':'5dcef4fd99200418f804cbd51f3bf325d1cbea60','files':hashes},indent=2)+'\n',encoding='utf-8',newline='\n')
print('FLOW_COPIED',len(hashes))
