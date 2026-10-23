`timescale 1ns/1ps
// B4 / N64, q/256, true-one and original input sign are preserved verbatim.
// Acceptance edge k -> result visible after edge k+2; earliest transfer k+3.
// DEPTH>=3 sustains II=1 with ready always high. These are RTL edges, not STA.
module er_pot_encoder_rv #(
 parameter integer FRAC=7,DEPTH=3,TAG_W=32,
 parameter integer CW=(DEPTH<2?1:$clog2(DEPTH+1))
)(
 input wire clk,rst_n,in_valid,
 output wire in_ready,
 input wire [64*(FRAC+9)-1:0] values,
 input wire [TAG_W-1:0] in_tag,
 output wire out_valid,
 input wire out_ready,
 output wire [511:0] q,
 output wire [127:0] bin,
 output wire [63:0] sign_bits,true_one,
 output wire signed [15:0] top_exp,
 output wire invalid,
 output wire [TAG_W-1:0] out_tag,
 output wire [CW-1:0] reserved_count,queued_count
);
 wire accept=in_valid&&in_ready;
 wire complete;
 wire [511:0] core_q;wire [127:0] core_bin;
 wire [63:0] core_sign,core_one;wire [15:0] core_exp;wire core_invalid;
 reg accepted_d1;reg [TAG_W-1:0] tag_d1,tag_d2;
 always @(posedge clk)begin
  if(!rst_n)begin accepted_d1<=0;tag_d1<=0;tag_d2<=0;end
  else begin
   accepted_d1<=accept;
   if(accept)tag_d1<=in_tag;
   if(accepted_d1)tag_d2<=tag_d1;
  end
 end
 nr_pot_encoder #(.FRAC(FRAC),.N(64)) core(
  clk,rst_n,accept,values,complete,core_q,core_bin,core_sign,core_one,core_exp,core_invalid);
 er_reserved_results #(.DATA_W(785+TAG_W),.DEPTH(DEPTH)) results(
  clk,rst_n,in_valid,in_ready,complete,
  {tag_d2,core_invalid,core_exp,core_one,core_sign,core_bin,core_q},
  out_valid,out_ready,{out_tag,invalid,top_exp,true_one,sign_bits,bin,q},
  reserved_count,queued_count);
`ifndef SYNTHESIS
 initial if(FRAC!=7&&FRAC!=23)$fatal(1,"only BF16 or FP32 input formats are supported");
`endif
endmodule
