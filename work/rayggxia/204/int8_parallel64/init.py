"""Recover exact SC replay operands from immutable source archives."""
from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile
R=Path(__file__).resolve().parents[4];W=R.parents[1];P=R/'architecture_tlm/int8_parallel64_20261028';P.mkdir(exist_ok=True)
old=json.loads((R/'architecture_tlm/module_energy_20261028/INPUT_REFERENCE.json').read_text());arcs=list((W/'project_archives/matrix204_single_scale_20261028/execution_packages').glob('*.zip'))
def sha(b):return hashlib.sha256(b).hexdigest()
def signed(v,n):return [((v>>(8*i))&255)-256 if ((v>>(8*i))&255)>=128 else (v>>(8*i))&255 for i in range(n)]
matched={};proof=[]
for seed in [17,503,1009]:
 inputs={}
 for fn in ['x8.hex','w8.hex']:
  suffix='power_fixtures/m8_s%d/'%seed+fn;key='architecture_tlm/matrix_single_scale_20261028/'+suffix;expected=old['files'][key]
  found=False
  for arc in arcs:
   with zipfile.ZipFile(arc) as z:
    names=[n for n in z.namelist() if n.endswith('/'+suffix)]
    if not names:continue
    raw=z.read(names[0])
    if sha(raw)!=expected:continue
    inputs[fn]=[signed(int(s,16),64 if fn=='x8.hex' else 512) for s in raw.decode().splitlines()]
    proof.append(dict(seed=seed,source=key,member=names[0],member_sha256=expected,archive=str(arc),archive_sha256=sha(arc.read_bytes())));found=True;break
  assert found,key
 assert len(inputs['x8.hex'])==len(inputs['w8.hex'])==16
 frames=[]
 for f in range(16):
  ws=inputs['w8.hex'][f][(f%8)*64:(f%8+1)*64]
  ws=[max(-127,min(127,w)) for w in ws]
  frames.append(dict(a=inputs['x8.hex'][f],b=ws))
 matched[str(seed)]=frames
(P/'matched_inputs.json').write_bytes((json.dumps(matched,indent=2)+'\n').encode())
base=R/'architecture_tlm/int8_classic_ppa_20261028/flow';flow=P/'flow';flow.mkdir(exist_ok=True);copied=[]
for n in ['upstream.py','common.tcl','library_conditions.tcl','dc.tcl','power_bulk.tcl','power_vcd.py','power_parse.py','vcd_alias_v2.py','constant_ports.py']:
 shutil.copyfile(base/n,flow/n);copied.append(dict(path=(base/n).relative_to(R).as_posix(),sha256=sha((base/n).read_bytes())))
balanced=subprocess.check_output(['git','show','HEAD:architecture_tlm/matrix_single_scale_20261028/rtl/ss_matrix_isolated.sv'],cwd=R)
(P/'INPUT_REFERENCE.json').write_bytes((json.dumps(dict(source_base='158e489816bde1547d07cd3f9e377b809055f63f',SC_input_reference_sha256=sha((R/'architecture_tlm/module_energy_20261028/INPUT_REFERENCE.json').read_bytes()),SC_operands=proof,mapping='same16 original SC replay frames/seed, select weight row f%8, cap absW to127 exactly as bank54; X signedINT8 unchanged',copied_flow_inputs=copied,balanced_tree_reference=dict(path='architecture_tlm/matrix_single_scale_20261028/rtl/ss_matrix_isolated.sv',sha256=sha(balanced)),pipeline='Try existing balanced64 combinational tree with registered output at100MHz; introduce a tree cut only if actual STA requires it'),indent=2)+'\n').encode())
print('MATCHED_SC_FRAMES',sum(map(len,matched.values())))
