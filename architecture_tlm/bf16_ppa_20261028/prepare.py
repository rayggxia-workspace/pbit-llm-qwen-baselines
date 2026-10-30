"""Exact-integer FP32 oracle and deterministic synthetic characterization inputs."""
from pathlib import Path
import json,random,struct,hashlib,re
R=Path(__file__).resolve().parent
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2)+'\n').encode())
def decode(x,p):
 e=(x>>p)&255;m=x&((1<<p)-1);sg=-1 if x>>(p+8) else 1
 return (sg*((1<<p)|m) if e else sg*m),(e-127-p if e else 1-127-p)
def rn(n,k):
 if k<=0:return n<<(-k)
 q,r=divmod(n,1<<k);return q+(r>(1<<(k-1)) or (r==(1<<(k-1)) and q&1))
def encode(n,e,zero_sign=0):
 sg=int(n<0);n=abs(n)
 if not n:return zero_sign<<31
 lead=n.bit_length()-1+e
 if lead < -126:
  m=rn(n,-149-e)
  return (sg<<31)|m
 m=rn(n,n.bit_length()-24)
 if m>=1<<24:m>>=1;lead+=1
 if lead>127:return (sg<<31)|0x7f800000
 return (sg<<31)|((lead+127)<<23)|(m&0x7fffff)
def oracle(a,b,c,kind=0):
 if kind==2:a=0x3f80;b32=b;c32=c;pa=7;pb=23
 else:b32=b;c32=c;pa=pb=7
 if kind==1:c32=0
 aa=(a>>(pa+8), (a>>pa)&255,a&((1<<pa)-1));bb=(b32>>(pb+8),(b32>>pb)&255,b32&((1<<pb)-1));cc=(c32>>31,(c32>>23)&255,c32&0x7fffff)
 if any(e==255 and m for s,e,m in (aa,bb,cc)):return 0x7fc00000
 zi=lambda q:q[1]==0 and q[2]==0
 if (aa[1]==255 and zi(bb)) or (bb[1]==255 and zi(aa)):return 0x7fc00000
 if aa[1]==255 or bb[1]==255:
  s=aa[0]^bb[0]
  return 0x7fc00000 if cc[1]==255 and cc[0]!=s else (s<<31)|0x7f800000
 if cc[1]==255:return c32
 x,ex=decode(a,pa);y,ey=decode(b32,pb);z,ez=decode(c32,23);ep=ex+ey;emin=min(ep,ez)
 n=((x*y)<<(ep-emin))+(z<<(ez-emin))
 s=(aa[0]^bb[0]) if not x*y and not z and (aa[0]^bb[0])==cc[0] else 0
 if kind==1:s=aa[0]^bb[0]
 return encode(n,emin,s)
def fp(x):return struct.unpack('>I',struct.pack('>f',x))[0]
def bf(x):
 z=fp(x);return ((z+0x7fff+((z>>16)&1))>>16)&65535
def main():
 (R/'rtl').mkdir(exist_ok=True);(R/'benches').mkdir(exist_ok=True)
 rtl='''`timescale 1ns/1ps
module bf_unit #(parameter integer KIND=0,PIPES=3)(input wire clk,rst_n,en,input wire [31:0] a,b,c,output wire valid,output wire [31:0] dout);
 wire ready;wire [2:0][31:0] operands;
 assign operands[0]=a;assign operands[1]=b;assign operands[2]=c;
 fpnew_fma_multi #(.FpFmtConfig(5'b10001),.NumPipeRegs(PIPES),.PipeConfig(fpnew_pkg::DISTRIBUTED),.TagType(logic),.AuxType(logic)) core(
 .clk_i(clk),.rst_ni(rst_n),.operands_i(operands),.is_boxed_i('1),.rnd_mode_i(fpnew_pkg::RNE),
 .op_i(KIND==2?fpnew_pkg::ADD:(KIND==1?fpnew_pkg::MUL:fpnew_pkg::FMADD)),.op_mod_i(1'b0),
 .src_fmt_i(KIND==2?fpnew_pkg::FP32:fpnew_pkg::FP16ALT),.src2_fmt_i(fpnew_pkg::FP32),.dst_fmt_i(fpnew_pkg::FP32),
 .tag_i(1'b0),.mask_i(1'b1),.aux_i(1'b0),.in_valid_i(en),.in_ready_o(ready),.flush_i(1'b0),
 .result_o(dout),.status_o(),.extension_bit_o(),.tag_o(),.mask_o(),.aux_o(),.out_valid_o(valid),.out_ready_i(1'b1),.busy_o(),.reg_ena_i('0),.early_out_valid_o());
endmodule
'''
 cases=[dict(name='fma2',kind=0,pipes=2),dict(name='fma3',kind=0,pipes=3),dict(name='mul1',kind=1,pipes=1),dict(name='add2',kind=2,pipes=2)]
 for case in cases:
  name=case['name'];rtl+=f"module bf_{name}(input wire clk,rst_n,en,input wire [31:0] a,b,c,output wire valid,output wire [31:0] dout);bf_unit #(.KIND({case['kind']}),.PIPES({case['pipes']})) u(.*);endmodule\n"
  for seed in (17,503,1009):
   rng=random.Random(seed);rows=[];expect=[];wins=[];cycle=0
   def put(en=0,a=0,b=0,c=0):
    nonlocal cycle
    rows.append((en<<96)|(a<<64)|(b<<32)|c)
    if en:expect.append(oracle(a,b,c,case['kind']))
    cycle+=1
   special=[0,0x8000,1,0x7f,0x80,0x3f80,0xbf80,0x7f7f,0xff7f,0x7f80,0xff80,0x7fc0,0x7f81]
   for _ in range(20):put()
   for i in range(260):
    a=rng.choice(special);b=rng.choice(special);c=fp(rng.uniform(-10,10)) if i%2 else rng.choice(special)<<16
    if case['kind']==2:b=rng.getrandbits(32)
    put(1,a,b,c)
    if i%7==0:put()
   for _ in range(20):put()
   for mode in ('normal','int8','idle'):
    start=cycle
    count=0 if mode=='idle' else 1024
    for i in range(1024 if mode!='idle' else 256):
     if mode=='idle':put();continue
     a=bf(rng.gauss(0,.6)) if mode=='normal' else bf(rng.randrange(-128,128)/128)
     b=bf(rng.gauss(0,.6)) if mode=='normal' else bf(rng.randrange(-128,128))
     c=fp(rng.uniform(-32,32))
     if case['kind']==2:b=fp(rng.gauss(0,32))
     put(1,a,b,c)
    for _ in range(12):put()
    wins.append(dict(mode=mode,start_ns=20+start*10,end_ns=20+cycle*10,operations=count,accepted_samples=count,measurement_cycles=cycle-start))
   dest=R/'fixtures'/name/str(seed);dest.mkdir(parents=True,exist_ok=True)
   (dest/'stim.hex').write_bytes(('\n'.join(f'{v:025x}' for v in rows)+'\n').encode());(dest/'expect.hex').write_bytes(('\n'.join(f'{v:08x}' for v in expect)+'\n').encode())
   save(dest/'WINDOWS.json',dict(transactions=len(expect),cycles=len(rows),windows=wins,stimulus='synthetic independent normal/int8; no model traces'))
   case['cycles']=len(rows);case['transactions']=len(expect)
  tb='''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,en=0;reg [31:0] a=0,b=0,c=0;wire valid;wire [31:0] dout;
TOP dut(.*);reg [96:0] stim[0:NC-1];reg [31:0] expect_mem[0:NE-1];integer i,got=0,sent=0;
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expect_mem);$dumpfile("activity.vcd");$dumpvars(0,tb);
 repeat(2) @(negedge clk);rst_n=1;
 for(i=0;i<NC;i=i+1)begin {en,a,b,c}=stim[i];if(en)sent=sent+1;@(negedge clk);end
 en=0;a=0;b=0;c=0;repeat(12)@(negedge clk);
 if(got!=NE ||sent!=NE)$fatal(1,"count got=%0d sent=%0d",got,sent);
 $display("FUNCTION_PASS transactions=%0d",got);$finish;
end
always @(posedge clk)begin #1;if(rst_n&&valid)begin
 if(got>=NE)$fatal(1,"excess result");
 if(dout!==expect_mem[got] && !((&dout[30:23])&&(|dout[22:0])&&(&expect_mem[got][30:23])&&(|expect_mem[got][22:0])))$fatal(1,"mismatch idx=%0d actual=%h expected=%h",got,dout,expect_mem[got]);
 got=got+1;end end
endmodule
'''.replace('TOP','bf_'+name)
  tb=re.sub(r'\bNC\b',str(case['cycles']),tb);tb=re.sub(r'\bNE\b',str(case['transactions']),tb)
  (R/'benches'/(name+'.sv')).write_bytes(tb.encode())
 (R/'rtl/units.sv').write_bytes(rtl.encode());save(R/'CASES.json',cases)
 # Independent checks on exact arithmetic encoding, including a tie and a
 # cancellation. Random RTL validation is performed by VCS on the server.
 assert oracle(0x3fc0,0x4000,fp(-1))==fp(2)
 assert oracle(0xbf80,0x3f80,fp(1))==0
 assert encode(1,-150)==0 and encode(3,-150)==2
 print(json.dumps({'cases':cases,'oracle_checks':'pass'}))
if __name__=='__main__':main()
