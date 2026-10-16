`timescale 1ns/1ps
// Offline coefficient representation: positive scale = mantissa * 2**coef_exp.
// mantissa is an UNSIGNED 24-bit integer, not a hidden-bit fraction here.
// T normalization and fixed Sx can be merged into coef_exp/mantissa offline.
// The runtime count*mantissa multiply remains real hardware and is included.
module fc_count_product #(parameter integer IN_W=32)(
 input wire signed [IN_W-1:0] count,
 input wire [23:0] coefficient_mantissa,
 output wire signed [IN_W+24:0] product
);
 wire signed [24:0] positive_coefficient={1'b0,coefficient_mantissa};
 assign product=count*positive_coefficient;
endmodule

module fc_fixed_align #(parameter integer IN_W=64,OUT_W=64)(
 input wire signed [IN_W-1:0] value_in,
 input wire signed [15:0] shift,
 output wire signed [OUT_W-1:0] value_out,
 output wire saturated,inexact
);
 wire neg=value_in[IN_W-1];
 wire [IN_W-1:0] mag=neg?(~value_in+1'b1):value_in;
 wire [OUT_W-1:0] limit=neg?{1'b1,{(OUT_W-1){1'b0}}}:{1'b0,{(OUT_W-1){1'b1}}};
 wire [OUT_W-1:0] q;
 fc_scale_mag #(.IN_W(IN_W),.OUT_W(OUT_W)) u_scale(mag,shift,limit,q,saturated,inexact);
 assign value_out=neg?(~q+1'b1):q;
endmodule

module fc_count_to_fixed #(parameter integer IN_W=32,OUT_W=64)(
 input wire signed [IN_W-1:0] count,
 input wire [23:0] coefficient_mantissa,
 input wire signed [15:0] coef_exp,common_lsb_exp,
 output wire signed [OUT_W-1:0] value_out,
 output wire saturated,inexact
);
 wire signed [IN_W+24:0] product;
 reg signed [15:0] shift;
 integer tmp;
 fc_count_product #(.IN_W(IN_W)) u_product(count,coefficient_mantissa,product);
 always @* begin
  tmp=$signed(coef_exp)-$signed(common_lsb_exp);
  if(tmp>32767) shift=32767;else if(tmp< -32768) shift=-32768;else shift=tmp;
 end
 fc_fixed_align #(.IN_W(IN_W+25),.OUT_W(OUT_W)) u_align(product,shift,value_out,saturated,inexact);
endmodule

module fc_count_to_fp #(parameter integer IN_W=32,FRAC=23)(
 input wire signed [IN_W-1:0] count,
 input wire [23:0] coefficient_mantissa,
 input wire signed [15:0] coef_exp,
 output wire [FRAC+8:0] fp,
 output wire overflow,tiny,inexact
);
 wire signed [IN_W+24:0] product;
 fc_count_product #(.IN_W(IN_W)) u_product(count,coefficient_mantissa,product);
 fc_fixed_to_fp #(.IN_W(IN_W+25),.FRAC(FRAC)) u_convert(product,coef_exp,fp,overflow,tiny,inexact);
endmodule
