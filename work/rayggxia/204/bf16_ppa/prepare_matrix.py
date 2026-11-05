"""Prepare a conventional non-fused DOT4 tree with interleaved FP32 sums."""
from pathlib import Path
import json,sys,random
R=Path(__file__).resolve().parents[4]/'architecture_tlm/bf16_ppa_20261028';sys.path.insert(0,str(R));from prepare import oracle,bf,save
rtl='''
// 4 parallel BF16 products -> balanced FP32 tree -> four FP32 contexts.
// Every add rounds to FP32 RNE. This is NOT a single-round fused DOT4.
module bf_dot64_4(input wire clk,rst_n,start,en,input wire [63:0] a,b,output wire ready,output reg valid,output reg [31:0] dout);
 localparam IDLE=0,FEED=1,DRAIN=2,REDUCE=3;
 reg [1:0] state;reg [4:0] beats,issued,returned;reg reduce_sent;
 reg [31:0] sums[0:3];wire [31:0] products[0:3];wire [3:0] pv;
 assign ready=(state==FEED);
 genvar i;generate for(i=0;i<4;i=i+1)begin:mp
  bf_unit #(.KIND(1),.PIPES(1)) m(clk,rst_n,en&&ready,{16'b0,a[i*16+:16]},{16'b0,b[i*16+:16]},32'b0,pv[i],products[i]);
 end endgenerate
 wire reducing=(state==REDUCE);wire tree_en=pv[0]||(reducing&&!reduce_sent);
 wire [31:0] x0=reducing?sums[0]:products[0],x1=reducing?sums[1]:products[1],x2=reducing?sums[2]:products[2],x3=reducing?sums[3]:products[3];
 wire [31:0] t0,t1,tree_sum,acc_sum;wire v0,v1,vt,va;
 bf_unit #(.KIND(2),.PIPES(2)) tadd0(clk,rst_n,tree_en,32'b0,x0,x1,v0,t0);
 bf_unit #(.KIND(2),.PIPES(2)) tadd1(clk,rst_n,tree_en,32'b0,x2,x3,v1,t1);
 bf_unit #(.KIND(2),.PIPES(2)) tadd2(clk,rst_n,v0,32'b0,t0,t1,vt,tree_sum);
 wire acc_en=vt&&!reducing;reg [1:0] tag0,tag1;
 bf_unit #(.KIND(2),.PIPES(2)) acc(clk,rst_n,acc_en,32'b0,sums[issued[1:0]],tree_sum,va,acc_sum);
 integer j;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin state<=IDLE;beats<=0;issued<=0;returned<=0;reduce_sent<=0;valid<=0;dout<=0;tag0<=0;tag1<=0;for(j=0;j<4;j=j+1)sums[j]<=0;end
  else begin
   valid<=0;tag0<=issued[1:0];tag1<=tag0;
   if(state==IDLE&&start)begin state<=FEED;beats<=0;issued<=0;returned<=0;reduce_sent<=0;for(j=0;j<4;j=j+1)sums[j]<=0;end
   if(en&&ready)begin beats<=beats+1;if(beats==15)state<=DRAIN;end
   if(acc_en)issued<=issued+1;
   if(va)begin sums[tag1]<=acc_sum;returned<=returned+1;if(returned==15)state<=REDUCE;end
   if(reducing&&!reduce_sent)reduce_sent<=1;
   if(reducing&&reduce_sent&&vt)begin dout<=tree_sum;valid<=1;state<=IDLE;end
  end
 end
endmodule
'''
(R/'rtl/matrix.sv').write_bytes(('`timescale 1ns/1ps\n'+rtl).encode())
case=dict(name='dot64_4',kind='matrix',N=64,lanes=4,contexts=4,frames=36,definition='BF16 product -> pairwise FP32 RNE DOT4 -> 4 interleaved FP32 sums -> balanced final tree')
for seed in (17,503,1009):
 rng=random.Random(seed);stim=[];expect=[]
 for frame in range(36):
  vals=[]
  for g in range(16):
   aa=[];bb=[]
   for lane in range(4):
    if frame<4:
     x=1.0 if frame%2==0 else (-1.0 if (g*4+lane)%2 else 1.0);w=1.0 if frame<2 else 2**(-lane*8)
    elif frame<20:x=rng.gauss(0,.6);w=rng.gauss(0,.5)
    else:x=rng.randrange(-128,128)/128;w=rng.randrange(-127,128)
    aa.append(bf(x));bb.append(bf(w))
   stim.append((sum(v<<(16*i) for i,v in enumerate(aa))<<64)|sum(v<<(16*i) for i,v in enumerate(bb)))
   prod=[oracle(x,y,0,1) for x,y in zip(aa,bb)]
   add=lambda x,y:oracle(0,x,y,2)
   vals.append(add(add(prod[0],prod[1]),add(prod[2],prod[3])))
  sums=[0]*4
  for g,v in enumerate(vals):sums[g%4]=add(sums[g%4],v)
  expect.append(add(add(sums[0],sums[1]),add(sums[2],sums[3])))
 d=R/'fixtures/dot64_4'/str(seed);d.mkdir(parents=True,exist_ok=True)
 (d/'stim.hex').write_bytes(('\n'.join(f'{v:032x}' for v in stim)+'\n').encode());(d/'expect.hex').write_bytes(('\n'.join(f'{v:08x}' for v in expect)+'\n').encode())
 save(d/'WINDOWS.json',dict(transactions=36,cycles='dynamic; printed by bench',windows=[],stimulus='4 directed + 16 normal + 16 matched INT8 synthetic frames; no model trace'))
tb='''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,start=0,en=0;reg[63:0]a=0,b=0;wire ready,valid;wire[31:0]dout;
bf_dot64_4 dut(.*);reg[127:0]stim[0:575];reg[31:0]expect_mem[0:35];integer frame,g,watch,got=0;time begin_window,begin_frame;
task tick;begin @(negedge clk);end endtask
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expect_mem);$dumpfile("activity.vcd");$dumpvars(0,tb);
 repeat(2)tick;rst_n=1;repeat(12)tick;
 for(frame=0;frame<36;frame=frame+1)begin
  if(frame==4||frame==20)begin_window=$time;
  begin_frame=$time;start=1;tick;start=0;
  if(!ready)$fatal(1,"not ready after start");
  for(g=0;g<16;g=g+1)begin
   if(frame<4 && g%3==0)begin en=0;tick;end
   en=1;{a,b}=stim[frame*16+g];tick;
  end
  en=0;watch=0;
  while(!valid)begin tick;watch=watch+1;if(watch>100)$fatal(1,"timeout frame=%0d",frame);end
  if(dout!==expect_mem[frame])$fatal(1,"frame=%0d actual=%h expected=%h",frame,dout,expect_mem[frame]);
  got=got+1;$display("FRAME_CYCLES %0d %0d",frame,($time-begin_frame)/10);tick;
  if(frame==19)$display("WINDOW normal %0d %0d 16",begin_window,$time);
  if(frame==35)$display("WINDOW int8 %0d %0d 16",begin_window,$time);
 end
 begin_window=$time;repeat(256)tick;$display("WINDOW idle %0d %0d 0",begin_window,$time);
 if(got!=36)$fatal(1,"wrong frame count");$display("FUNCTION_PASS transactions=%0d",got);$finish;
end
endmodule
'''
(R/'benches/dot64_4.sv').write_bytes(tb.encode());cases=json.loads((R/'CASES.json').read_text());cases=[c for c in cases if c['name']!='dot64_4'];save(R/'CASES.json',cases+[case])
print(json.dumps(case))
