`timescale 1ns/1ps
// Deterministic array characterization: use LANES1/16/64 (or MAC512 only after
// lane timing is known). Array wiring/clock cost is not inferred from one lane.
module nr_fp32_array #(parameter integer LANES=64,MULTIPLY=0)(
 input wire clk,rst_n,in_valid,input wire [LANES*32-1:0] a,b,
 output reg out_valid,output reg [LANES*32-1:0] y
);
 reg [LANES*32-1:0] ar,br;reg valid_r;wire [LANES*32-1:0] result;
 genvar i;
 generate for(i=0;i<LANES;i=i+1)begin:lane
  if(MULTIPLY)nr_fp32_mul core(ar[i*32+:32],br[i*32+:32],result[i*32+:32]);
  else fc_fp_add core(ar[i*32+:32],br[i*32+:32],result[i*32+:32],,,);
 end endgenerate
 always @(posedge clk)begin
  if(!rst_n)begin ar<=0;br<=0;valid_r<=0;out_valid<=0;y<=0;end
  else begin
   valid_r<=in_valid;out_valid<=valid_r;
   if(in_valid)begin ar<=a;br<=b;end
   if(valid_r)y<=result;
  end
 end
endmodule

module nr_bf16_mac_array #(parameter integer LANES=8)(
 input wire clk,rst_n,in_valid,first,last,input wire [LANES*16-1:0] a,b,
 output wire out_valid,output wire [LANES*32-1:0] y
);
 reg [LANES*16-1:0] ar,br;reg valid_r,first_r,last_r;
 wire [LANES-1:0] valid_lane;
 always @(posedge clk)begin
  if(!rst_n)begin ar<=0;br<=0;valid_r<=0;first_r<=0;last_r<=0;end
  else begin
   valid_r<=in_valid;
   if(in_valid)begin ar<=a;br<=b;first_r<=first;last_r<=last;end
  end
 end
 genvar i;
 generate for(i=0;i<LANES;i=i+1)begin:lane
  nr_stream_accumulator #(.KIND(1)) core(clk,rst_n,valid_r,first_r,last_r,ar[i*16+:16],br[i*16+:16],8'b0,32'b0,32'b0,valid_lane[i],y[i*32+:32],);
 end endgenerate
 assign out_valid=valid_lane[0];
endmodule
