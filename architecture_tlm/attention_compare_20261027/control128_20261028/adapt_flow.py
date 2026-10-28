"""Derive the reviewed driver without changing prior executed snapshots."""
from pathlib import Path
H=Path(__file__).resolve().parent;OLD=H.parent/'control_v2/eda_20261028'
def write(p,s):p.write_bytes(s.encode())
def main():
    r=(OLD/'runner.py').read_text()
    r=r.replace("original=json.loads((ROOT/'snapshots/v2/SOURCE.json').read_text())","original=json.loads((SNAP/'SOURCE.json').read_text())")
    r=r.replace("defs=['+define+AC_TOP='+top]","defs=['+define+AC_TOP='+top,'+define+AC_COUNT_W='+str(case['count_width'])]")
    r=r.replace("['ac_scan.sv','ac_winner.sv','ac_rejection.sv','nr_singleton_tree.sv',top+'.sv']","['ac_scan.sv','ac_winner128.sv',top+'.sv']")
    r=r.replace("if phase=='gate':command+=","if phase=='gate' and trace['windows']:command+=")
    r=r.replace("if stage=='dc':","if stage=='collect':\n            raise ValueError('collection uses separate script')\n        if stage=='dc':")
    write(H/'runner.py',r)
    c=(OLD/'collect.py').read_text().replace('snapshots/v3','snapshots/v1')
    c=c.replace("==66","==56").replace("==116","==336")
    c=c.replace("for v in ['v1','v2','v3']","for v in ['v1']")
    c=c.replace("directory=ROOT/'snapshots/v1/vectors'/top/item['trace']","directory=ROOT/'snapshots/v1/vectors'/top/item['trace']\n            trace_meta=next(t for t in traces[top] if t['trace']==item['trace'])")
    c=c.replace("warnings={code:","assert outputs==window['outputs'],(top,item['trace'],outputs,window)\n            warnings={code:")
    c=c.replace("rows.append(dict(trace=item['trace'],window=window,power=powers,duration_ns=duration,","rows.append(dict(trace=item['trace'],window=window,metrics=trace_meta.get('metrics'),power=powers,duration_ns=duration,")
    c=c.replace("sdc_sha256=sha(dc/'mapped.sdc'),functional_cycles=", "sdc_sha256=sha(dc/'mapped.sdc'),functional_trace_metrics=[dict(trace=t['trace'],metrics=t.get('metrics'),coverage=t.get('coverage')) for t in traces[top]],functional_cycles=")
    write(H/'collect.py',c)
if __name__=='__main__':main()
