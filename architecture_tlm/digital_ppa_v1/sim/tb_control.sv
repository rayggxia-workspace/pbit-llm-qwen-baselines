`timescale 1ns/1ps
module tb_control;
 reg clk=0;always #5 clk=~clk;reg rst_n=0;
 reg valid=0;reg [15:0] bits_in=0,mask=16'hffff;wire tv;wire [1:0] card;wire [3:0] address;
 nr_singleton_tree #(.N(16)) tree(clk,rst_n,valid,bits_in,mask,tv,card,address);
 reg [7:0] pm=0;wire [31:0] dest;wire [3:0] count;
 nr_mask_prefix #(.N(8)) prefix(pm,dest,count);
 reg cv=0,first=0,last=0;reg [32:0] probability=0;reg [31:0] offset=32'h20000000;
 wire ov;wire [2:0] multiplicity;
 nr_cdf_counts #(.S_LOG2(2)) cdf(clk,rst_n,cv,first,last,probability,offset,ov,multiplicity);
 integer i,total,timeout;
 task tree_case(input [15:0] value,input [15:0] enabled,input [1:0] expected,input [3:0] index);
 begin
  @(negedge clk);bits_in=value;mask=enabled;valid=1;
  @(negedge clk);valid=0;
  timeout=0;
  while(!tv&&timeout<10)begin @(negedge clk);timeout=timeout+1;end
  if(!tv||card!==expected||(expected!=0&&address!==index))$fatal(1,"singleton mismatch");
  repeat(2)@(negedge clk);
 end endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  pm=8'had;#1;total=0;
  for(i=0;i<8;i=i+1)begin if(dest[i*4+:4]!==total[3:0])$fatal(1,"prefix mismatch");total=total+pm[i];end
  if(count!==5)$fatal(1,"prefix total");
  tree_case(0,16'hffff,0,0);tree_case(16'h400,16'hffff,1,10);tree_case(16'h401,16'hffff,2,0);tree_case(16'h401,16'h400,1,10);
  for(i=0;i<4;i=i+1)begin
   @(negedge clk);cv=1;first=i==0;last=i==3;probability=33'h040000000;
   @(posedge clk);#1;if(!ov||multiplicity!==1)$fatal(1,"CDF uniform count");
  end
  @(negedge clk);cv=1;first=1;last=1;probability=0;
  @(posedge clk);#1;if(!ov||multiplicity!==4)$fatal(1,"CDF close/first-last");
  @(negedge clk);cv=0;
  $display("PASS prefix, zero/single/multi masked tree, CDF boundaries");$finish;
 end
endmodule
