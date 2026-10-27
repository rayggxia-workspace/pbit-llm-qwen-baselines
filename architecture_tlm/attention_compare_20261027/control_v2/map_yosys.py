"""Local Liberty mapping/aggregate cell area only; no STA or power claim.

Input library and mapped netlists remain private. Core source is frozen into a
PPA bundle first. The caller supplies an independently documented area scale.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from .validate import sha,write


def main():
    p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--library',type=Path,required=True);p.add_argument('--yowasp-dir',type=Path,required=True)
    p.add_argument('--cache',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--area-scale-um2',type=float);p.add_argument('--area-unit-source')
    p.add_argument('--top',nargs='+');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    if a.area_scale_um2 is not None and not a.area_unit_source:p.error('documented area units required')
    # WASI uses explicit narrow mounts. Private library directory is readable;
    # its contents are never copied into a public package.
    env=os.environ.copy();env['YOWASP_CACHE_DIR']=str(a.cache.resolve())
    env['YOWASP_MOUNT']='/bundle='+str(a.bundle.resolve()).replace('\\','/')+':/out='+str(a.output.resolve()).replace('\\','/')+':/private='+str(a.library.resolve().parent).replace('\\','/')
    # Windows drive colons conflict with YoWASP's mount-list delimiter. Use
    # host-relative paths under a common cwd rather than drive-letter paths.
    env['YOWASP_MOUNT']='/bundle='+os.path.relpath(a.bundle).replace('\\','/')+':/out='+os.path.relpath(a.output).replace('\\','/')+':/private='+os.path.relpath(a.library.parent).replace('\\','/')
    launcher='import sys;sys.path.insert(0,sys.argv[1]);from yowasp_yosys import run_yosys;sys.exit(run_yosys(sys.argv[2:]))'
    version=subprocess.run([sys.executable,'-c',launcher,str(a.yowasp_dir.resolve()),'-V'],env=env,capture_output=True,text=True,check=True).stdout.strip()
    text=a.library.read_text(encoding='utf-8',errors='strict')
    matches=list(re.finditer(r'\bcell\s*\(\s*([^\)]+)\s*\)\s*\{',text));prices={}
    for i,m in enumerate(matches):
        block=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)]
        area=re.search(r'\barea\s*:\s*([0-9.eE+-]+)',block)
        if area:prices[m.group(1).strip('" ')]=float(area.group(1))
    metadata={k:(m.group(1) if (m:=re.search(r'\b'+k+r'\s*:\s*([^;]+);',text)) else None)
              for k in ('nom_voltage','nom_temperature','time_unit','leakage_power_unit')}
    spec=json.loads((a.bundle/'CASES.json').read_text());cases=[]
    for case in spec['tops']:
        top=case['top']
        if a.top and top not in a.top:continue
        script=f'''read_liberty -lib /private/{a.library.name}
read_verilog -sv -DSYNTHESIS /bundle/rtl/ac_scan.sv /bundle/rtl/ac_winner.sv /bundle/rtl/ac_rejection.sv /bundle/rtl/nr_singleton_tree.sv /bundle/rtl/{top}.sv
hierarchy -check -top {top}
synth -top {top} -flatten -noabc
dfflibmap -liberty /private/{a.library.name}
abc -liberty /private/{a.library.name}
clean
check
stat -liberty /private/{a.library.name}
write_json /out/{top}.json
write_verilog -noattr -noexpr /out/{top}.v
'''
        path=a.output/(top+'.ys');path.write_bytes(script.encode())
        cmd=[sys.executable,'-c',launcher,str(a.yowasp_dir.resolve()),'-s','/out/'+path.name]
        r=subprocess.run(cmd,env=env,capture_output=True,text=True)
        (a.output/(top+'.log')).write_bytes((r.stdout+r.stderr).encode())
        if r.returncode:write(a.output/'FAILED.json',dict(top=top,rc=r.returncode));raise RuntimeError('mapping failed: '+top)
        cells=json.loads((a.output/(top+'.json')).read_text())['modules'][top]['cells']
        counts=Counter(c['type'] for c in cells.values())
        missing=[kind for kind in counts if kind not in prices]
        area=sum(prices[k]*n for k,n in counts.items() if k in prices)
        row=dict(**case,status='mapped' if not missing else 'partial_unmapped',cells=sum(counts.values()),
                 library_area_units=area,area_um2=area*a.area_scale_um2 if a.area_scale_um2 is not None and not missing else None,
                 unmapped_types=missing,netlist_sha256=sha(a.output/(top+'.v')),log_sha256=sha(a.output/(top+'.log')),
                 sta='not_run',power='not_run',gate_functional='not_run')
        cases.append(row);write(a.output/'SUMMARY.json',dict(tool=version,library_sha256=sha(a.library),
                 library_metadata=metadata,area_unit_source=a.area_unit_source,cases=cases,
                 scope='Yosys/ABC Liberty-mapped area only, not DC/PT/STA/postlayout; mapped files private'))
        print(json.dumps(row),flush=True)


if __name__=='__main__':main()
