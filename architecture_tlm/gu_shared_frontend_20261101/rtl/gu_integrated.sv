`timescale 1ns/1ps
// One encoded input source serves Wg and Wu. Baseline represents separate
// 8-column cores: distinct input ports prevent fictitious automatic merging.
module gu_sng64(input wire [1151:0] codes,output wire [63:0] bits,signs);
 genvar n;
 generate for(n=0;n<64;n=n+1)begin:lane
  assign bits[n]=codes[n*18+9] || (codes[n*18+10+:8]<codes[n*18+:8]);
  assign signs[n]=codes[n*18+8];
 end endgenerate
endmodule

module gu_integrated #(parameter M=16,SHARE=1,T=64)(
 input wire clk,rst_n,en,
 input wire [1152*(M/8)+M*512+15:0] din,
 output wire [M*32+16:0] dout);
 localparam GROUPS=M/8,FRONTS=SHARE?1:GROUPS,WO=1152*GROUPS,
  TAIL=WO+M*512,LOGT=$clog2(T),AW=14+LOGT;
 wire clear=din[TAIL+15];
 wire signed [7:0] ex={{3{din[TAIL+4]}},din[TAIL+:5]};
 wire signed [7:0] eg={{3{din[TAIL+9]}},din[TAIL+5+:5]};
 wire signed [7:0] eu={{3{din[TAIL+14]}},din[TAIL+10+:5]};
 wire signed [7:0] out_eg=ex+eg-LOGT,out_eu=ex+eu-LOGT;
 reg [LOGT-1:0] accepted;
 reg done;
 wire fire=en&&!done&&!clear;
 wire readout=done&&!clear;
 always @(posedge clk)begin
  if(!rst_n||clear)begin accepted<=0;done<=0;end
  else if(fire)begin
   if(accepted==T-1)done<=1;else accepted<=accepted+1'b1;
  end
 end
 wire [63:0] events[0:FRONTS-1],signs[0:FRONTS-1];
 genvar f,m,n;
 generate
 for(f=0;f<FRONTS;f=f+1)begin:frontend
  gu_sng64 sng(din[f*1152+:1152],events[f],signs[f]);
 end
 for(m=0;m<M;m=m+1)begin:column
  localparam F=SHARE?0:m/8;
  wire [511:0] leaves;
  for(n=0;n<64;n=n+1)begin:weight
   wire negative=signs[F][n]^din[WO+8*(m*64+n)+7];
   wire signed [7:0] magnitude={1'b0,din[WO+8*(m*64+n)+:7]};
   wire signed [7:0] signed_weight=negative?-magnitude:magnitude;
   assign leaves[n*8+:8]=(fire&&events[F][n])?signed_weight:8'd0;
  end
  wire signed [13:0] delta;
  wire signed [AW-1:0] count;
  me_sum #(.N(64),.LW(8)) reduce(leaves,delta);
  aw_acc #(.B(AW),.D(14),.SAT(0)) accumulator(clk,rst_n,clear,fire,delta,count);
  assign dout[m*32+:32]=readout?{{(32-AW){count[AW-1]}},count}:32'd0;
 end
 endgenerate
 assign dout[M*32+:8]=readout?out_eg:8'd0;
 assign dout[M*32+8+:8]=readout?out_eu:8'd0;
 assign dout[M*32+16]=readout;
endmodule
