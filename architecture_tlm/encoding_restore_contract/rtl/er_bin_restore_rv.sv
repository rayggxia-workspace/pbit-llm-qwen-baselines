`timescale 1ns/1ps
// Literal (FUSED=0) bin order and FP32 rounding. Counts are flattened as
// ((bin*2+INPUT_SIGN)*8+WEIGHT_BIT)*COUNT_W. Weight bit7 has weight -128.
// A product-sign / magnitude counter bus is NOT a compatible representation.
// Acceptance k -> registered result visible after k+1; earliest transfer k+2.
// DEPTH>=2 sustains II=1 with ready high. No physical frequency claim is made.
module er_bin_restore_rv #(
 parameter integer COUNT_W=12,T_LOG2=5,DEPTH=3,TAG_W=32,
 parameter integer CW=(DEPTH<2?1:$clog2(DEPTH+1))
)(
 input wire clk,rst_n,in_valid,
 output wire in_ready,
 input wire [64*COUNT_W-1:0] counts,
 input wire signed [15:0] top_exp,
 input wire [31:0] weight_scale,
 input wire [TAG_W-1:0] in_tag,
 output wire out_valid,
 input wire out_ready,
 output wire [31:0] fp32_out,
 output wire [TAG_W-1:0] out_tag,
 output wire [CW-1:0] reserved_count,queued_count
);
 wire accept=in_valid&&in_ready;
 reg input_valid;reg [64*COUNT_W-1:0] counts_r;
 reg signed [15:0] exp_r;reg [31:0] scale_r;reg [TAG_W-1:0] tag_r;
 always @(posedge clk)begin
  if(!rst_n)begin input_valid<=0;counts_r<=0;exp_r<=0;scale_r<=0;tag_r<=0;end
  else begin
   input_valid<=accept;
   if(accept)begin counts_r<=counts;exp_r<=top_exp;scale_r<=weight_scale;tag_r<=in_tag;end
  end
 end
 wire [31:0] computed;
 nr_bin_restore #(.COUNT_W(COUNT_W),.T_LOG2(T_LOG2),.FUSED(0)) core(
  counts_r,exp_r,scale_r,computed);
 er_reserved_results #(.DATA_W(32+TAG_W),.DEPTH(DEPTH)) results(
  clk,rst_n,in_valid,in_ready,input_valid,{tag_r,computed},
  out_valid,out_ready,{out_tag,fp32_out},reserved_count,queued_count);
endmodule
