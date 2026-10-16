`timescale 1ns/1ps
// One independent output channel; accepts one partial per valid cycle.
// first may coincide with valid, last may coincide with first. No backpressure.
// coef_exp and common_lsb_exp are software/configuration-provided constants
// for each partial/frame. common_lsb_exp MUST stay constant within a frame.
module fc_accum_fixed #(parameter integer ACC_W=64)(
 input wire clk,rst_n,valid,first,last,
 input wire signed [31:0] count,
 input wire [23:0] coefficient_mantissa,
 input wire signed [15:0] coef_exp,common_lsb_exp,
 output reg out_valid,
 output reg [31:0] result,
 output reg saturated,inexact
);
 wire signed [ACC_W-1:0] scaled;
 wire sat,ix;
 fc_count_to_fixed #(.OUT_W(ACC_W)) u_scale(count,coefficient_mantissa,coef_exp,common_lsb_exp,scaled,sat,ix);
 reg signed [ACC_W-1:0] acc;
 wire signed [ACC_W:0] sum=$signed(first?{ACC_W{1'b0}}:acc)+$signed({scaled[ACC_W-1],scaled});
 wire add_sat=(sum[ACC_W]!=sum[ACC_W-1]);
 wire signed [ACC_W-1:0] bounded=add_sat?
  (sum[ACC_W]?{1'b1,{(ACC_W-1){1'b0}}}:{1'b0,{(ACC_W-1){1'b1}}}):sum[ACC_W-1:0];
 // Isolate final converter until last; otherwise it would toggle each partial.
 wire signed [ACC_W-1:0] final_input=(valid&&last)?bounded:{ACC_W{1'b0}};
 wire [31:0] converted;
 wire fp_ov,fp_tiny,fp_ix;
 fc_fixed_to_fp #(.IN_W(ACC_W),.FRAC(23)) u_final(final_input,common_lsb_exp,converted,fp_ov,fp_tiny,fp_ix);
 reg frame_sat,frame_ix;
 always @(posedge clk) begin
  if(!rst_n) begin acc<=0;out_valid<=0;result<=0;saturated<=0;inexact<=0;frame_sat<=0;frame_ix<=0;end
  else begin
   out_valid<=valid&&last;
   if(valid) begin
    acc<=bounded;frame_sat<=(first?1'b0:frame_sat)|sat|add_sat;
    frame_ix<=(first?1'b0:frame_ix)|ix|add_sat;
    if(last) begin
     result<=converted;saturated<=(first?1'b0:frame_sat)|sat|add_sat|fp_ov;
     inexact<=(first?1'b0:frame_ix)|ix|add_sat|fp_ix;
    end
   end
  end
 end
endmodule

module fc_accum_float(
 input wire clk,rst_n,valid,first,last,
 input wire signed [31:0] count,
 input wire [23:0] coefficient_mantissa,
 input wire signed [15:0] coef_exp,
 output reg out_valid,
 output reg [31:0] result,
 output reg invalid,overflow,inexact
);
 wire [31:0] term,sum;
 wire term_ov,term_tiny,term_ix,add_inv,add_ov,add_ix;
 fc_count_to_fp u_convert(count,coefficient_mantissa,coef_exp,term,term_ov,term_tiny,term_ix);
 reg [31:0] acc;
 wire [31:0] base=first?32'b0:acc;
 fc_fp_add u_add(base,term,sum,add_inv,add_ov,add_ix);
 reg frame_inv,frame_ov,frame_ix;
 always @(posedge clk) begin
  if(!rst_n) begin acc<=0;out_valid<=0;result<=0;invalid<=0;overflow<=0;inexact<=0;
   frame_inv<=0;frame_ov<=0;frame_ix<=0;end
  else begin
   out_valid<=valid&&last;
   if(valid) begin
    acc<=sum;frame_inv<=(first?1'b0:frame_inv)|add_inv;
    frame_ov<=(first?1'b0:frame_ov)|term_ov|add_ov;
    frame_ix<=(first?1'b0:frame_ix)|term_ix|add_ix;
    if(last) begin
     result<=sum;invalid<=(first?1'b0:frame_inv)|add_inv;
     overflow<=(first?1'b0:frame_ov)|term_ov|add_ov;
     inexact<=(first?1'b0:frame_ix)|term_ix|add_ix;
    end
   end
  end
 end
endmodule
