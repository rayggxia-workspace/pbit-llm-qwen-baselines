"""Validate the actual delivered ZIP without using original source files."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import zipfile

W=Path(__file__).parent
ROOT=W.parents[2]
WS=ROOT.parents[1]
meta=json.loads((W/'CONTROL_PORTABLE.json').read_text())
packet=Path(meta['path'])
assert hashlib.sha256(packet.read_bytes()).hexdigest()==meta['sha256']
dest=W/'portable_check';dest.mkdir(exist_ok=False)
with zipfile.ZipFile(packet) as z:
    for name,m in meta['members'].items():
        b=z.read(name)
        assert hashlib.sha256(b).hexdigest()==m['sha256'] and len(b)==m['bytes']
        p=(dest/name).resolve();assert p.is_relative_to(dest.resolve())
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
module='architecture_tlm.attention_compare_20261027.control_v2'
r=subprocess.run([sys.executable,'-B','-m','unittest',module+'.test_math','-v'],cwd=dest,capture_output=True,text=True)
assert r.returncode==0,r.stderr
bundle=dest/'new_ppa'
p=subprocess.run([sys.executable,'-B','-m',module+'.make_ppa','--output',str(bundle)],cwd=dest,capture_output=True,text=True)
assert p.returncode==0,p.stderr
iverilog=WS/'sc_weight_storage_or4_20261014/tools/iverilog/bin/iverilog.exe'
lib=iverilog.parent.parent/'lib/ivl'
cases=json.loads((bundle/'CASES.json').read_text())['tops']
commands=[]
for case in cases:
    top=case['top']
    cmd=[str(iverilog),'-B',str(lib),'-g2012','-DSYNTHESIS','-s',top,'-o',str(bundle/(top+'.vvp'))]
    cmd += [str(bundle/'rtl'/n) for n in ['ac_scan.sv','ac_winner.sv','nr_singleton_tree.sv','ac_rejection.sv',top+'.sv']]
    check=subprocess.run(cmd,cwd=dest,capture_output=True,text=True)
    assert check.returncode==0,check.stderr
    commands.append(dict(top=top,status='elaboration_pass',command=cmd))
out=dict(packet_sha256=meta['sha256'],all_members_sha_verified=True,math_tests=3,unittest_output=r.stderr,
    regenerated_fixed_tops=8,elaborations=commands,
    note='standalone extracted public packet; elaboration only, no new RTL simulation or PPA run')
(W/'CONTROL_PORTABLE_CHECK.json').write_bytes((json.dumps(out,indent=2,ensure_ascii=False)+'\n').encode())
print(json.dumps({k:v for k,v in out.items() if k not in ['unittest_output','elaborations']}))
