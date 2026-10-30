`timescale 1ns/1ps

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
