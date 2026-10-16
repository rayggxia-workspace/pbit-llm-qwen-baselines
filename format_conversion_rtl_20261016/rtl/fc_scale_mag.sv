`timescale 1ns/1ps
// Unsigned exact power-of-two scaling, RNE, programmable saturation limit.
// value_out = min(limit, round_even(magnitude * 2**shift)).
module fc_scale_mag #(parameter integer IN_W=24, OUT_W=8)(
 input wire [IN_W-1:0] magnitude,
 input wire signed [15:0] shift,
 input wire [OUT_W-1:0] limit,
 output reg [OUT_W-1:0] value_out,
 output reg saturated,inexact
);
 localparam integer W=IN_W+OUT_W+2;
 reg [W-1:0] x,y,lim;
 reg guard_bit,sticky;
 integer k,j;
 always @* begin
  x={{(W-IN_W){1'b0}},magnitude};lim={{(W-OUT_W){1'b0}},limit};
  y=0;guard_bit=0;sticky=0;k=0;saturated=0;inexact=0;value_out=0;
  if(shift>=0) begin
   if(shift>OUT_W && magnitude!=0) begin y=lim;saturated=1;end
   else begin y=x<<shift;if(y>lim) begin y=lim;saturated=1;end end
  end else begin
   k=-$signed(shift);
   if(k>W) begin y=0;inexact=(x!=0);end
   else begin
    y=x>>k;
    for(j=0;j<W;j=j+1) begin
     if(j==k-1) guard_bit=x[j];
     if(j<k-1) sticky=sticky|x[j];
    end
    inexact=guard_bit|sticky;
    if(guard_bit&&(sticky||y[0])) y=y+1'b1;
    if(y>lim) begin y=lim;saturated=1;end
   end
  end
  value_out=y[OUT_W-1:0];inexact=inexact|saturated;
 end
endmodule
