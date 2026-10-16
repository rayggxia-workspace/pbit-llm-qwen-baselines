`timescale 1ns/1ps
// BF16 (FRAC=7) or FP32 (FRAC=23). E=8, bias=127.
// magnitude=clip(round_even(abs(fp)/2**lsb_exp),0,MAX_MAG).
// Handles subnormals; NaN -> 0+invalid, infinity -> saturation.
module fc_fp_to_quant #(
 parameter integer FRAC=7,Q_W=8,
 parameter [Q_W-1:0] MAX_MAG={Q_W{1'b1}}
)(
 input wire [FRAC+8:0] fp,
 input wire signed [15:0] lsb_exp,
 output wire [Q_W-1:0] magnitude,
 output wire sign_out,
 output wire saturated,inexact,invalid
);
 wire [7:0] ex=fp[FRAC+7:FRAC];
 wire [FRAC-1:0] fraction=fp[FRAC-1:0];
 wire special=&ex;
 assign invalid=special&&(fraction!=0);
 wire [FRAC:0] sig={ex!=0,fraction};
 reg signed [15:0] shift;
 integer tmp;
 always @* begin
  // Convert exponent to signed integer BEFORE combining with signed lsb_exp.
  // Otherwise the unsigned exponent can zero-extend a negative scale exponent.
  tmp=ex;
  if(ex==0) tmp=1;
  tmp=tmp-127-FRAC;
  tmp=tmp-$signed(lsb_exp);
  if(tmp>32767) shift=32767;else if(tmp< -32768) shift=-32768;else shift=tmp;
 end
 wire [Q_W-1:0] q;
 wire sat,ix;
 fc_scale_mag #(.IN_W(FRAC+1),.OUT_W(Q_W)) u_scale(sig,shift,MAX_MAG,q,sat,ix);
 assign magnitude=invalid?{Q_W{1'b0}}:(special?MAX_MAG:q);
 assign sign_out=fp[FRAC+8]&&(magnitude!=0);
 assign saturated=special?!invalid:sat;
 assign inexact=special?!invalid:ix;
endmodule
