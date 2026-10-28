`timescale 1ns/1ps
module tb;
localparam IW=576,OW=16,L=1748;
reg clk=0;always #5 clk=~clk;reg rst_n=0,clear=0,en=0;reg [IW-1:0] din=0;wire [OW-1:0] dout;
me_bank50 dut(.*);
reg [IW+1:0] stim[0:L-1];reg [OW-1:0] expected[0:L-1];integer i;
initial begin $dumpfile("activity.vcd");$dumpvars(0,tb);$readmemh("stim.hex",stim);$readmemh("expect.hex",expected);
 repeat(4) @(negedge clk);rst_n=1;
 for(i=0;i<L;i=i+1) begin @(negedge clk);{clear,en,din}=stim[i];@(posedge clk);#1;if(dout!==expected[i]) $fatal(1,"Mismatch index=%0d got=%h expected=%h",i,dout,expected[i]);end
 @(negedge clk);$display("FUNCTION_PASS transactions=%0d",L);$finish;end
initial begin #1000000;$fatal(1,"Timeout");end
endmodule
