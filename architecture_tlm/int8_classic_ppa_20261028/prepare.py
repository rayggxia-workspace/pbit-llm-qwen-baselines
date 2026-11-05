"""Self-contained signed INT8 DOT4 fixtures and exact Python-integer oracle."""
from pathlib import Path
import json,random
R=Path(__file__).resolve().parent
SEEDS=[17,503,1009]
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2)+'\n').encode())

RTL='''`timescale 1ns/1ps
// Conventional product pipeline -> balanced reduction -> output-stationary sum.
// Asynchronous control reset; synchronous accumulator reset. Product flops need no reset: valid masks
// their startup contents. No SRAM, hidden resident-weight array or inferred ICG.
module i8_dot64 #(parameter integer AW=32)(
 input wire clk,rst_n,start,en,input wire [31:0] a,b,
 output wire ready,output reg valid,output wire [31:0] dout);
 reg busy,product_valid;reg [4:0] accepted,returned;
 reg signed [15:0] products[0:3];reg signed [AW-1:0] acc;
 assign ready=busy&&(accepted<16);
 wire push=en&&ready;
 assign dout={{(32-AW){acc[AW-1]}},acc};
 wire signed [16:0] pair0=$signed({products[0][15],products[0]})+$signed({products[1][15],products[1]});
 wire signed [16:0] pair1=$signed({products[2][15],products[2]})+$signed({products[3][15],products[3]});
 wire signed [17:0] group_sum=$signed({pair0[16],pair0})+$signed({pair1[16],pair1});
 wire signed [AW-1:0] next_acc=acc+$signed({{(AW-18){group_sum[17]}},group_sum});
 genvar i;generate for(i=0;i<4;i=i+1)begin:lane
  always @(posedge clk)if(rst_n&&push)products[i]<=$signed(a[i*8+:8])*$signed(b[i*8+:8]);
 end endgenerate
 always @(posedge clk)begin
  if(!rst_n || (start&&!busy))acc<=0;
  else if(busy&&product_valid)acc<=next_acc;
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin busy<=0;product_valid<=0;accepted<=0;returned<=0;valid<=0;end
  else begin
   valid<=0;
   if(start&&!busy)begin busy<=1;accepted<=0;returned<=0;product_valid<=0;end
   else begin
    product_valid<=push;
    if(push)accepted<=accepted+1;
    if(busy&&product_valid)begin
     returned<=returned+1;
     if(returned==15)begin valid<=1;busy<=0;end
    end
   end
  end
 end
endmodule
module i8_dot4_a32(input wire clk,rst_n,start,en,input wire [31:0]a,b,output wire ready,valid,output wire[31:0]dout);i8_dot64 #(.AW(32))u(.*);endmodule
module i8_dot4_a22(input wire clk,rst_n,start,en,input wire [31:0]a,b,output wire ready,valid,output wire[31:0]dout);i8_dot64 #(.AW(22))u(.*);endmodule
'''

TB='''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,start=0,en=0;reg[31:0]a=0,b=0;wire ready,valid;wire[31:0]dout;
TOP dut(.*);reg[63:0]stim[0:575];reg[31:0]expect_mem[0:35];integer frame,g,watch,got=0;time begin_window,begin_frame;
task tick;begin @(negedge clk);end endtask
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expect_mem);$dumpfile("activity.vcd");$dumpvars(0,tb);
 repeat(2)tick;rst_n=1;repeat(4)tick;
 // Abort one partial frame by reset. Stale products must never leak a result.
 start=1;en=1;a=32'h80808080;b=a;tick;start=0;
 repeat(4)begin en=1;tick;end
 rst_n=0;en=0;repeat(2)tick;rst_n=1;repeat(4)begin tick;if(valid!==1'b0)$fatal(1,"aborted frame produced result");end
 for(frame=0;frame<36;frame=frame+1)begin
  if(frame==4||frame==20)begin_window=$time;
  begin_frame=$time;start=1;en=1;tick;start=0;en=0;
  if(ready!==1'b1)$fatal(1,"not ready after start");
  for(g=0;g<16;g=g+1)begin
   if(frame<4 && g%3==0)begin en=0;tick;end
   if(frame<4 && g==7)start=1;else start=0;
   if(ready!==1'b1)$fatal(1,"input not ready");en=1;{a,b}=stim[frame*16+g];tick;
  end
  start=0;en=1;watch=0;
  while(valid!==1'b1)begin tick;watch=watch+1;if(watch>100)$fatal(1,"timeout");end
  if(ready!==1'b0)$fatal(1,"unexpected readiness at final result");
  if(dout!==expect_mem[frame])$fatal(1,"frame=%0d actual=%h expected=%h",frame,dout,expect_mem[frame]);
  got=got+1;$display("FRAME_CYCLES %0d %0d",frame,($time-begin_frame)/10);en=0;tick;
  if(valid!==1'b0)$fatal(1,"duplicate valid");
  if(frame==19)$display("WINDOW matched %0d %0d 16",begin_window,$time);
  if(frame==35)$display("WINDOW fullrange %0d %0d 16",begin_window,$time);
 end
 begin_window=$time;repeat(256)begin tick;if(valid!==1'b0)$fatal(1,"idle result");end
 $display("WINDOW idle %0d %0d 0",begin_window,$time);
 if(got!=36)$fatal(1,"wrong frame count");$display("FUNCTION_PASS transactions=%0d",got);$finish;
end
initial begin #1000000;$fatal(1,"Timeout");end
endmodule
'''

def main():
 matched=json.loads((R/'matched_inputs.json').read_text())
 cases=[dict(name='dot4_a32',AW=32),dict(name='dot4_a22',AW=22)]
 (R/'rtl').mkdir(exist_ok=True);(R/'benches').mkdir(exist_ok=True)
 (R/'rtl/dot4.sv').write_bytes(RTL.encode())
 for c in cases:
  (R/'benches'/(c['name']+'.sv')).write_bytes(TB.replace('TOP','i8_'+c['name']).encode())
  for seed in SEEDS:
   rng=random.Random(seed);frames=[]
   for x,w in [(-128,-128),(-128,127),(127,127),(0,0)]:
    frames.append(dict(a=[x]*64,b=[w]*64))
   frames+=matched[str(seed)]
   for f in range(16):
    a=[rng.randrange(-128,128) for _ in range(64)];b=[rng.randrange(-128,128) for _ in range(64)]
    # Include full signed endpoints in active windows as well as directed tests.
    a[f]=-128;b[f]=-128;frames.append(dict(a=a,b=b))
   rows=[];expected=[]
   for f in frames:
    assert len(f['a'])==len(f['b'])==64
    value=sum(x*w for x,w in zip(f['a'],f['b']))
    assert -(1<<(c['AW']-1))<=value<(1<<(c['AW']-1))
    expected.append(value&0xffffffff)
    for g in range(16):
     a=sum((x&255)<<(8*i) for i,x in enumerate(f['a'][g*4:g*4+4]));b=sum((x&255)<<(8*i) for i,x in enumerate(f['b'][g*4:g*4+4]));rows.append((a<<32)|b)
   d=R/'fixtures'/c['name']/str(seed);d.mkdir(parents=True,exist_ok=True)
   (d/'stim.hex').write_bytes(('\n'.join('%016x'%v for v in rows)+'\n').encode())
   (d/'expect.hex').write_bytes(('\n'.join('%08x'%v for v in expected)+'\n').encode())
   save(d/'WINDOWS.json',dict(transactions=36,windows=[],stimulus='4 extrema directed +16 BF16-exact matched +16 fullrange signedINT8; independent wide-int oracle; one aborted frame and gaps/start/excess-en checks'))
 save(R/'CASES.json',cases)
 assert 64*(-128)*(-128)==1048576 and 64*(-128)*127==-1040384
 print(json.dumps(dict(cases=cases,seeds=SEEDS,frames_per_case=108,extrema_checks='pass')))
if __name__=='__main__':main()
