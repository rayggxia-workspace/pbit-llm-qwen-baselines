"""Extract the already-reviewed XOR DAG; never rerun mapping/seed search."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    old = ROOT.parents[1] / 'rng32x64_design_20261015'
    raw = (old/'rng32x64.sv').read_bytes()
    lines = raw.decode('utf-8').splitlines()
    body = []
    for line in lines:
        if line.strip().startswith('wire ') or (line.strip().startswith('assign ') and 'stochastic_bit' not in line):
            line = re.sub(r'random_word\[(\d+)\]', lambda m: 'random_word[%d +: 8]' % (int(m[1])*8), line)
            body.append(line)
    out = ('// Extracted XOR DAG from rng32x64_design_20261015/rng32x64.sv.\n'
           '// Source SHA256: '+hashlib.sha256(raw).hexdigest()+'\n'
           'module rng_shared64_map(input wire [31:0] state,\n'
           ' output wire [511:0] random_word, output wire [31:0] next_state);\n'
           +'\n'.join(body)+'\nendmodule\n')
    (ROOT/'rtl').mkdir(exist_ok=True)
    (ROOT/'rtl/rng_shared64_map.sv').write_text(out, encoding='utf-8', newline='\n')
    mapping = json.loads((old/'manifest.json').read_text(encoding='utf-8'))
    (ROOT/'shared64_mapping.json').write_text(json.dumps(mapping,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__ == '__main__':
    main()

