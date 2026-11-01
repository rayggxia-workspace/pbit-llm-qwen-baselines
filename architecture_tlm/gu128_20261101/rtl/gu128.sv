`timescale 1ns/1ps
// Common input coding: P8, sign, full-one, external R8 per input lane.
module gu128_sng64(input wire [1151:0] codes,output wire [63:0] bits,signs);
 genvar n;
 generate for(n=0;n<64;n=n+1)begin:lane
  assign bits[n]=codes[n*18+9] || (codes[n*18+10+:8]<codes[n*18+:8]);
  assign signs[n]=codes[n*18+8];
 end endgenerate
endmodule

module gu128_control(input wire clk,rst_n,en,clear,output wire fire,valid);
 reg [5:0] accepted;
 reg done;
 assign fire=en&&!done&&!clear;
 assign valid=done&&!clear;
 always @(posedge clk)begin
  if(!rst_n||clear)begin accepted<=0;done<=0;end
  else if(fire)begin
   if(accepted==63)done<=1;else accepted<=accepted+1'b1;
  end
 end
endmodule

// A single fixed-size mapped block is reused sixteen times in both candidates.
module gu128_backend8(
 input wire clk,rst_n,clear,fire,
 input wire [63:0] events,signs,
 input wire [4095:0] weights,
 output wire [159:0] counts);
 genvar m,n;
 generate for(m=0;m<8;m=m+1)begin:column
  wire [511:0] leaves;
  for(n=0;n<64;n=n+1)begin:weight
   wire negative=signs[n]^weights[8*(m*64+n)+7];
   wire signed [7:0] magnitude={1'b0,weights[8*(m*64+n)+:7]};
   wire signed [7:0] signed_weight=negative?-magnitude:magnitude;
   assign leaves[n*8+:8]=events[n]?signed_weight:8'd0;
  end
  wire signed [13:0] delta;
  me_sum #(.N(64),.LW(8)) reduce(leaves,delta);
  aw_acc #(.B(20),.D(14),.SAT(0)) accumulator(clk,rst_n,clear,fire,delta,counts[m*20+:20]);
 end endgenerate
endmodule

module gu128_core #(parameter COLS=64)(
 input wire clk,rst_n,en,clear,
 input wire [1151:0] source,
 input wire [COLS*512-1:0] weights,
 output wire [COLS*20-1:0] counts,
 output wire valid);
 wire [63:0] bits,signs,events;
 wire fire;
 gu128_sng64 sng(source,bits,signs);
 gu128_control control(clk,rst_n,en,clear,fire,valid);
 assign events=bits & {64{fire}};
 genvar b;
 generate for(b=0;b<COLS/8;b=b+1)begin:backend
  gu128_backend8 block(clk,rst_n,clear,fire,events,signs,weights[b*4096+:4096],counts[b*160+:160]);
 end endgenerate
endmodule

// Both candidates have identical ports and sixteen backend8 instances.
// DUAL=1: separate source/clear ports represent physically separate g/u cores.
// Contract: sourceA==sourceB, clearA==clearB for every transaction.
module gu128_integrated #(parameter DUAL=0)(
 input wire clk,rst_n,en,
 input wire [67856:0] din,
 output wire [4112:0] dout);
 localparam WO=2304,TAIL=67840;
 wire [2559:0] counts;
 wire valid;
 generate if(DUAL)begin:separate
  wire vg,vu;
  gu128_core #(.COLS(64)) g(clk,rst_n,en,din[TAIL+15],din[0+:1152],din[WO+:32768],counts[0+:1280],vg);
  gu128_core #(.COLS(64)) u(clk,rst_n,en,din[TAIL+16],din[1152+:1152],din[WO+32768+:32768],counts[1280+:1280],vu);
  assign valid=vg&&vu;
 end else begin:fused
  gu128_core #(.COLS(128)) gu(clk,rst_n,en,din[TAIL+15],din[0+:1152],din[WO+:65536],counts,valid);
 end endgenerate
 wire signed [7:0] ex={{3{din[TAIL+4]}},din[TAIL+:5]};
 wire signed [7:0] eg={{3{din[TAIL+9]}},din[TAIL+5+:5]};
 wire signed [7:0] eu={{3{din[TAIL+14]}},din[TAIL+10+:5]};
 wire signed [7:0] out_eg=ex+eg-8'd6,out_eu=ex+eu-8'd6;
 genvar m;
 generate for(m=0;m<128;m=m+1)begin:readout
  wire signed [19:0] count=counts[m*20+:20];
  assign dout[m*32+:32]=valid?{{12{count[19]}},count}:32'd0;
 end endgenerate
 assign dout[4096+:8]=valid?out_eg:8'd0;
 assign dout[4104+:8]=valid?out_eu:8'd0;
 assign dout[4112]=valid;
endmodule
