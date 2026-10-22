`timescale 1ns/1ps
module tb_arrays;
 reg clk=0;always #5 clk=~clk;reg rst_n=0,iv=0,first=0,last=0;
 reg [127:0] a={4{32'h3f800000}},b={4{32'h40000000}};
 reg [63:0] ma={4{16'h3f80}},mb={4{16'h4000}};
 wire av,mv,cv;wire [127:0] add_y,mul_y,mac_y;
 nr_fp32_array #(.LANES(4)) ad(clk,rst_n,iv,a,b,av,add_y);
 nr_fp32_array #(.LANES(4),.MULTIPLY(1)) mu(clk,rst_n,iv,a,b,mv,mul_y);
 nr_bf16_mac_array #(.LANES(4)) mc(clk,rst_n,iv,first,last,ma,mb,cv,mac_y);
 integer i,adds=0,macs=0;
 always @(posedge clk)begin
  #1;
  if(rst_n&&av)begin if(add_y!=={4{32'h40400000}})$fatal(1,"array add");adds=adds+1;end
  if(rst_n&&mv&&mul_y!=={4{32'h40000000}})$fatal(1,"array mul");
  if(rst_n&&cv)begin if(mac_y!=={4{32'h41000000}})$fatal(1,"array MAC");macs=macs+1;end
 end
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  for(i=0;i<4;i=i+1)begin @(negedge clk);iv=1;first=i==0;last=i==3;end
  @(negedge clk);iv=0;
  repeat(8)@(negedge clk);
  if(adds!=4||macs!=1)$fatal(1,"array valid protocol");
  $display("PASS parallel4lane FP32 add/multiply and BF16 MAC accumulation");$finish;
 end
endmodule
