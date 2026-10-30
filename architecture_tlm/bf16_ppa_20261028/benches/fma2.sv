`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,en=0;reg [31:0] a=0,b=0,c=0;wire valid;wire [31:0] dout;
bf_fma2 dut(.*);reg [96:0] stim[0:2678-1];reg [31:0] expect_mem[0:2308-1];integer i,got=0,sent=0;
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expect_mem);$dumpfile("activity.vcd");$dumpvars(0,tb);
 repeat(2) @(negedge clk);rst_n=1;
 for(i=0;i<2678;i=i+1)begin {en,a,b,c}=stim[i];if(en)sent=sent+1;@(negedge clk);end
 en=0;a=0;b=0;c=0;repeat(12)@(negedge clk);
 if(got!=2308 ||sent!=2308)$fatal(1,"count got=%0d sent=%0d",got,sent);
 $display("FUNCTION_PASS transactions=%0d",got);$finish;
end
always @(posedge clk)begin #1;if(rst_n&&valid)begin
 if(got>=2308)$fatal(1,"excess result");
 if(dout!==expect_mem[got] && !((&dout[30:23])&&(|dout[22:0])&&(&expect_mem[got][30:23])&&(|expect_mem[got][22:0])))$fatal(1,"mismatch idx=%0d actual=%h expected=%h",got,dout,expect_mem[got]);
 got=got+1;end end
endmodule
