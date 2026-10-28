"""Generate a wrapper around a USER-SUPPLIED integrated clock-gating cell.
No library discovery, inference, or physical validation is performed here.
"""
import argparse, json, re
from pathlib import Path

def generate(config):
    keys=('cell','clock_pin','enable_pin','test_enable_pin','output_pin')
    for k in keys:
        v=config.get(k)
        if not isinstance(v,str) or not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_$]*',v):
            raise ValueError('Use an explicit simple Verilog identifier for '+k)
        if v.startswith('FILL_'):
            raise ValueError('Placeholder remains: '+k)
    if len({config[k] for k in keys[1:]})!=4:
        raise ValueError('ICG pins must be distinct')
    return ('// User-bound ICG; compile with PB_ICG_TECH_MAPPED and the real library.\n'
      'module pbit_icg_tech(input wire clk,en,test_en,output wire gclk);\n'
      f" {config['cell']} u_library_icg(.{config['clock_pin']}(clk),"
      f".{config['enable_pin']}(en),.{config['test_enable_pin']}(test_en),"
      f".{config['output_pin']}(gclk));\nendmodule\n")

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('config',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists(): raise SystemExit('Refusing to overwrite existing mapping')
    code=generate(json.loads(a.config.read_text(encoding='utf-8')))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(code.encode('utf-8'))
