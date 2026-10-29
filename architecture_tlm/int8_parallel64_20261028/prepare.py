"""64 simultaneous signed INT8 multipliers and a balanced exact sum tree."""
from pathlib import Path
import json,random
R=Path(__file__).resolve().parent
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((json.dumps(d,indent=2)+'\n').encode())
RTL='''`timescale 1ns/1ps
module p64_sum #(parameter N=64,LW=16,TW=LW+$clog2(N))(
 input wire [N*LW-1:0] leaves,output wire signed[TW-1:0] total);
 genvar l,k;generate for(l=0;l<$clog2(N);l=l+1)begin:level
  wire signed[LW+l:0] v[0:(N>>(l+1))-1];
  for(k=0;k<(N>>(l+1));k=k+1)begin:node
   wire signed[LW+l-1:0] a,b;
   if(l==0)begin assign a=leaves[2*k*LW+:LW];assign b=leaves[(2*k+1)*LW+:LW];end
   else begin assign a=level[l-1].v[2*k];assign b=level[l-1].v[2*k+1];end
   assign v[k]=$signed({a[LW+l-1],a})+$signed({b[LW+l-1],b});
  end
 end endgenerate
 assign total=level[$clog2(N)-1].v[0];
endmodule
// One N64 dot per valid input; no temporal multiplier sharing or weight bank.
module p64_dot #(parameter AW=32)(input wire clk,rst_n,en,input wire[511:0]a,b,
 output reg valid,output wire[31:0]dout);
 wire[1023:0] products;wire signed[21:0] dot;reg signed[AW-1:0] result;
 genvar i;generate for(i=0;i<64;i=i+1)begin:lane
  wire signed[7:0]x=a[i*8+:8],w=b[i*8+:8];assign products[i*16+:16]=x*w;
 end endgenerate
 p64_sum tree(products,dot);
 always @(posedge clk)begin if(!rst_n)result<=0;else if(en)result<=$signed(dot);end
 always @(posedge clk or negedge rst_n)begin if(!rst_n)valid<=0;else valid<=en;end
 assign dout={{(32-AW){result[AW-1]}},result};
endmodule
module i8_par64_a32(input wire clk,rst_n,en,input wire[511:0]a,b,output wire valid,output wire[31:0]dout);p64_dot #(.AW(32))u(.*);endmodule
module i8_par64_a22(input wire clk,rst_n,en,input wire[511:0]a,b,output wire valid,output wire[31:0]dout);p64_dot #(.AW(22))u(.*);endmodule
'''
TB='''`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,en=0;reg[511:0]a=0,b=0;wire valid;wire[31:0]dout;
TOP dut(.*);reg[1023:0]stim[0:163];reg[31:0]expect_mem[0:163];integer i,got=0,sent=0;time begin_window;
task tick;begin @(negedge clk);end endtask
task send;input integer idx;begin en=1;{a,b}=stim[idx];sent=sent+1;tick;end endtask
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expect_mem);$dumpfile("activity.vcd");$dumpvars(0,tb);
 repeat(2)tick;rst_n=1;repeat(2)tick;
 for(i=0;i<4;i=i+1)begin send(i);en=0;repeat(2)tick;end
 // Assert actual reset with input-enable high; this input is not a transaction.
 rst_n=0;en=1;tick;en=0;tick;rst_n=1;repeat(2)tick;
 begin_window=$time;
 for(i=4;i<132;i=i+1)send(i);
 en=0;$display("WINDOW peak %0d %0d 128",begin_window,$time);repeat(2)tick;
 begin_window=$time;
 for(i=132;i<148;i=i+1)begin send(i);en=0;repeat(34)tick;end
 $display("WINDOW paced %0d %0d 16",begin_window,$time);
 begin_window=$time;
 for(i=148;i<164;i=i+1)send(i);
 en=0;$display("WINDOW fullrange %0d %0d 16",begin_window,$time);repeat(2)tick;
 begin_window=$time;repeat(256)tick;$display("WINDOW idle %0d %0d 0",begin_window,$time);
 if(got!=164||sent!=164)$fatal(1,"count got=%0d sent=%0d",got,sent);
 $display("FUNCTION_PASS transactions=%0d",got);$finish;
end
always @(posedge clk)begin #1;
 if(rst_n)begin
  if(valid!==en)$fatal(1,"valid/X mismatch");
  if(valid)begin
   if(got>=164||dout!==expect_mem[got])$fatal(1,"result idx=%0d actual=%h expected=%h",got,dout,expect_mem[got]);
   got=got+1;
  end
 end else if(valid!==1'b0)$fatal(1,"reset valid");
end
initial begin #1000000;$fatal(1,"Timeout");end
endmodule
'''
def main():
 matched=json.loads((R/'matched_inputs.json').read_text());cases=[dict(name='par64_a32',AW=32,lanes=64),dict(name='par64_a22',AW=22,lanes=64)]
 (R/'rtl').mkdir(exist_ok=True);(R/'benches').mkdir(exist_ok=True);(R/'rtl/par64.sv').write_bytes(RTL.encode())
 for c in cases:
  (R/'benches'/(c['name']+'.sv')).write_bytes(TB.replace('TOP','i8_'+c['name']).encode())
  for seed in [17,503,1009]:
   rng=random.Random(seed);frames=[dict(a=[x]*64,b=[w]*64) for x,w in [(-128,-128),(-128,127),(127,127),(0,0)]]
   frames+=matched[str(seed)]*8+matched[str(seed)]
   for f in range(16):
    a=[rng.randrange(-128,128) for _ in range(64)];b=[rng.randrange(-128,128) for _ in range(64)];a[f]=b[f]=-128;frames.append(dict(a=a,b=b))
   rows=[];expected=[]
   for f in frames:
    val=sum(x*w for x,w in zip(f['a'],f['b']));assert -(1<<21)<=val<(1<<21)
    expected.append(val&0xffffffff);a=sum((x&255)<<(8*i) for i,x in enumerate(f['a']));b=sum((x&255)<<(8*i) for i,x in enumerate(f['b']));rows.append((a<<512)|b)
   d=R/'fixtures'/c['name']/str(seed);d.mkdir(parents=True,exist_ok=True)
   (d/'stim.hex').write_bytes(('\n'.join('%0256x'%v for v in rows)+'\n').encode());(d/'expect.hex').write_bytes(('\n'.join('%08x'%v for v in expected)+'\n').encode())
   save(d/'WINDOWS.json',dict(transactions=164,windows=[],profiles='peak128=16 SC vectors repeated8, paced16=one/35cycles, fullrange16, idle; no model trace',logical_latency_cycles=1,initiation_interval_cycles=1))
 save(R/'CASES.json',cases);print(json.dumps(dict(cases=cases,frames_per_case=492,SC_unique_vectors=48)))
if __name__=='__main__':main()
