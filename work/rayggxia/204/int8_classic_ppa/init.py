# Historical v1 bootstrap; final v4 constraints/reset edits are frozen separately. Do not rerun in an execution snapshot.
"""Bind exact BF16 subset operands and copy the already-validated PPA flow."""
from pathlib import Path
from fractions import Fraction
import hashlib,json,shutil,struct
R=Path(__file__).resolve().parents[4];P=R/'architecture_tlm/int8_classic_ppa_20261028';B=R/'architecture_tlm/bf16_ppa_20261028'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def value(b):
 s=-1 if b&32768 else 1;e=(b>>7)&255;m=b&127;assert e!=255
 return s*((128+m) if e else m)*(Fraction(2)**((e-134) if e else -133))
matched={};bindings=[]
for seed in [17,503,1009]:
 d=B/'fixtures/dot64_4'/str(seed);stim=[int(s,16) for s in (d/'stim.hex').read_text().splitlines()];out=[int(s,16) for s in (d/'expect.hex').read_text().splitlines()];frames=[]
 for f in range(20,36):
  aa=[];bb=[]
  for packed in stim[f*16:(f+1)*16]:
   a,b=packed>>64,packed&((1<<64)-1)
   for i in range(4):
    x=value((a>>(16*i))&65535)*128;w=value((b>>(16*i))&65535)
    assert x.denominator==w.denominator==1 and -128<=x<=127 and -127<=w<=127
    aa.append(int(x));bb.append(int(w))
  total=sum(x*w for x,w in zip(aa,bb));assert struct.unpack('>I',struct.pack('>f',total/128))[0]==out[f]
  frames.append(dict(a=aa,b=bb))
 matched[str(seed)]=frames
 bindings.append(dict(seed=seed,stim_sha256=sha(d/'stim.hex'),expect_sha256=sha(d/'expect.hex'),frame_indices=list(range(20,36)),scale='Integer result /128 equals exact BF16/FP32 reference output'))
(P/'matched_inputs.json').write_bytes((json.dumps(matched,indent=2)+'\n').encode())
F=P/'flow';F.mkdir(exist_ok=True);files=[]
for n in ['upstream.py','common.tcl','library_conditions.tcl','dc.tcl','power_bulk.tcl','power_vcd.py','power_parse.py','vcd_alias_v2.py','constant_ports.py']:
 src=B/'flow'/n;shutil.copyfile(src,F/n);files.append(dict(path=src.relative_to(R).as_posix(),sha256=sha(src)))
dc=F/'dc.tcl';dc.write_bytes(dc.read_bytes().replace(b'    compile_ultra -retime',b'    set_fix_hold [get_clocks core]\n    compile_ultra -retime'))
(P/'INPUT_REFERENCE.json').write_bytes((json.dumps(dict(source_base='6435de8854d8ddb93375e03085ed1eea9c3f9002',BF16_snapshot='bf16_204_v7_20261028',BF16_source_zip_sha256='5b43f1cf79a4cca541c0ae2921613808fca2478a42b44159c946a3d9e61d2e17',matched=bindings,copied_flow_inputs=files,DC_change='Set fix_hold on core before compile_ultra -retime; data/reset timing constraints unmodified'),indent=2)+'\n').encode())
print('MATCHED_BF16_FRAMES',sum(map(len,matched.values())))
