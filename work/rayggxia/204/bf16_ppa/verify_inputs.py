"""Independent exact dot verification for the INT8-derived BF16 fixture subset."""
from pathlib import Path
from fractions import Fraction
import struct,json
R=Path(__file__).resolve().parents[4]/'architecture_tlm/bf16_ppa_20261028'

def value(b):
 s=-1 if b&32768 else 1;e=(b>>7)&255;m=b&127
 assert e!=255
 n=s*((128+m) if e else m);p=(e-134) if e else -133
 return Fraction(n)*(Fraction(2)**p)

def main():
 count=0
 for seed in [17,503,1009]:
  d=R/'fixtures/dot64_4'/str(seed);stim=[int(s,16) for s in (d/'stim.hex').read_text().splitlines()];out=[int(s,16) for s in (d/'expect.hex').read_text().splitlines()]
  for frame in range(20,36):
   total=Fraction(0)
   for packed in stim[frame*16:(frame+1)*16]:
    a,b=packed>>64,packed&((1<<64)-1)
    for i in range(4):
     x=value((a>>(i*16))&65535);w=value((b>>(i*16))&65535)
     assert (x*128).denominator==1 and -128<=x*128<=127
     assert w.denominator==1 and -127<=w<=127
     total+=x*w
   bits=struct.unpack('>I',struct.pack('>f',float(total)))[0]
   assert bits==out[frame],(seed,frame)
   assert Fraction(struct.unpack('>f',struct.pack('>I',bits))[0])==total
   count+=1
 print(json.dumps(dict(independent_exact_int8_derived_dot_frames=count,status='pass',inference='Synthetic fixture subset only; no model quality claim')))
if __name__=='__main__':main()
