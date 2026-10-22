"""Generate constant ROM cases; Python math is preparation, never DUT hardware."""
import math
from pathlib import Path
import struct

HERE=Path(__file__).resolve().parents[1]/'rtl'


def bits(x):
    return struct.unpack('>I',struct.pack('>f',x))[0]


def main():
    tables={
        'sigmoid': [1/(1+math.exp(-s*i/32)) for s in (1,-1) for i in range(513)],
        'expneg': [math.exp(-i/32) for i in range(513)],
        'recip': [1/(1+i/256) for i in range(257)],
        'rsqrt': [1/math.sqrt(1+i/256) for i in range(257)],
    }
    for name,values in tables.items():
        lines=[f'function automatic [31:0] nr_{name}_rom(input [10:0] index);',
               ' begin case(index)']
        lines += [f"  11'd{i}:nr_{name}_rom=32'h{bits(v):08x};" for i,v in enumerate(values)]
        lines += [f"  default:nr_{name}_rom=32'h7fc00000;", ' endcase end','endfunction','']
        (HERE/f'nr_{name}_rom.svh').write_text('\n'.join(lines),encoding='utf-8',newline='\n')


if __name__=='__main__':main()
