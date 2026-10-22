"""Run from the extracted delivery, not from an unchecked full repository."""
import argparse
import ast
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tkinter
from package import KINDS, sha, verify


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iverilog', required=True)
    ap.add_argument('--vvp', required=True)
    ap.add_argument('--ivl-lib', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    root = Path(__file__).resolve().parent
    verify()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    results, commands = [], []
    def call(cmd, cwd):
        p = subprocess.run([str(x) for x in cmd], cwd=str(cwd), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True, timeout=300)
        commands.append(dict(command=[str(x) for x in cmd], rc=p.returncode, output=p.stdout))
        if p.returncode:
            raise RuntimeError(p.stdout)
        return p.stdout
    tcl = tkinter.Tcl()
    for p in root.glob('*.tcl'):
        assert int(tcl.call('info', 'complete', p.read_text())) == 1, p
    for p in root.glob('*.py'):
        ast.parse(p.read_text(), feature_version=(3, 6))
    source = sorted((root/'rtl').glob('*.sv'))+sorted((root/'conversion').glob('*.sv'))
    cases = json.loads((root/'vectors/cases.json').read_text())
    try:
        for kind in KINDS:
            binary = out/('k{}.vvp'.format(kind))
            call([a.iverilog, '-B', a.ivl_lib, '-g2012', '-s', 'tb_ppa',
                  '-I', root/'rtl', '-DKIND='+str(kind), '-o', binary]+source+[root/'tb.sv'], out)
            for m in [x for x in cases if x['kind'] == kind]:
                case = out/m['name']
                case.mkdir()
                with gzip.open(str(root/'vectors'/(m['name']+'.hex.gz')), 'rb') as f:
                    (case/'vectors.hex').write_bytes(f.read())
                text = call([a.vvp, '-M', a.ivl_lib, binary, '+VECTORS='+str(case/'vectors.hex'),
                    '+GOLD='+str(root/'vectors'/(m['name']+'.gold')), '+ROWS='+str(m['rows']),
                    '+OUTPUTS='+str(m['outputs'])], case)
                assert 'DIGITAL_PPA_PASS inputs={} outputs={}'.format(m['inputs'], m['outputs']) in text
                results.append(dict(name=m['name'], outputs=m['outputs'], inputs=m['inputs'], pass_bittrue=True))
                print('PASS '+m['name'], flush=True)
        record = dict(status='PASS', scope='LOCAL_RTL_ONLY_NOT_DC_VCS_PT', cases=results,
            package_manifest_sha256=sha(root/'package_manifest.json'),
            python=sys.version, tool_sha256={x: sha(Path(x)) for x in (a.iverilog, a.vvp)})
        (out/'VALIDATION.json').write_text(json.dumps(record, indent=2)+'\n')
    finally:
        (out/'COMMANDS.json').write_text(json.dumps(commands, indent=2)+'\n')


if __name__ == '__main__':
    main()
