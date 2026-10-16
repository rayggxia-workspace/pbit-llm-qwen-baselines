`timescale 1ns/1ps
// signed integer * 2**lsb_exp -> BF16/FP32, one RNE rounding.
// Supports subnormal outputs; overflow -> signed infinity. tiny is a status
// indicating nonzero input that becomes subnormal/zero, not an IEEE exception.
module fc_fixed_to_fp #(parameter integer IN_W=64,FRAC=23)(
 input wire signed [IN_W-1:0] value_in,
 input wire signed [15:0] lsb_exp,
 output reg [FRAC+8:0] fp,
 output reg overflow,tiny,
 output wire inexact
);
 wire negative=value_in[IN_W-1];
 wire [IN_W-1:0] magnitude=negative?(~value_in+1'b1):value_in;
 integer lead,j,e;
 reg signed [15:0] shift;
 always @* begin
  lead=-1;
  for(j=0;j<IN_W;j=j+1) if(magnitude[j]) lead=j;
  e=lead+$signed(lsb_exp);
  if(e>=-126) shift=FRAC-lead;
  else if($signed(lsb_exp)+126+FRAC< -32768) shift=-32768;
  else shift=$signed(lsb_exp)+126+FRAC;
 end
 wire [FRAC+1:0] rounded;
 wire unused_sat,ix;
 fc_scale_mag #(.IN_W(IN_W),.OUT_W(FRAC+2)) u_round(
  magnitude,shift,{(FRAC+2){1'b1}},rounded,unused_sat,ix);
 reg [FRAC+1:0] mant;
 reg [7:0] packed_exp;
 integer final_e;
 assign inexact=ix|overflow;
 always @* begin
  fp=0;overflow=0;tiny=0;mant=rounded;packed_exp=0;final_e=e;
  if(magnitude!=0) begin
   if(e>=-126) begin
    if(rounded[FRAC+1]) begin mant=rounded>>1;final_e=e+1;end
    if(final_e>127) begin
     overflow=1;fp={negative,8'hff,{FRAC{1'b0}}};
    end else begin packed_exp=final_e+127;fp={negative,packed_exp,mant[FRAC-1:0]};end
   end else begin
    if(rounded[FRAC]) fp={negative,8'h01,{FRAC{1'b0}}};
    else begin fp={negative,8'h00,rounded[FRAC-1:0]};tiny=1;end
   end
  end
 end
endmodule
