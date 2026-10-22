`timescale 1ns/1ps
// Complete 64-value group encoder. Fixed B4 scales top,top/4,top/16,top/64.
// No RNG/comparator stream generator. q/256, explicit true-one, original order.
// One group accepted at each edge; output at the following edge. No backpressure.
module nr_pot_encoder #(parameter integer FRAC=7,N=64)(
 input wire clk,rst_n,in_valid,
 input wire [N*(FRAC+9)-1:0] values,
 output reg out_valid,
 output reg [N*8-1:0] q,
 output reg [N*2-1:0] bin,
 output reg [N-1:0] sign_bits,true_one,
 output reg signed [15:0] top_exp,
 output reg invalid
);
 localparam integer W=FRAC+9;
 wire [W-2:0] tree[0:2*N-2];
 genvar g;
 generate for(g=0;g<N;g=g+1) begin:leaf
  assign tree[N-1+g]=values[g*W+:W-1];
 end
 for(g=0;g<N-1;g=g+1)begin:level
  assign tree[g]=tree[2*g+1]>tree[2*g+2]?tree[2*g+1]:tree[2*g+2];
 end endgenerate
 function automatic signed [15:0] ceiling_pow2(input [W-2:0] mag);
  integer e,j,lead;reg [FRAC-1:0] f;
  begin
   e=mag[FRAC+:8];f=mag[FRAC-1:0];lead=-1;
   if(mag==0)ceiling_pow2=0;
   else if(e==255)ceiling_pow2=128;
   else if(e!=0)ceiling_pow2=e-127+(f!=0);
   else begin
    for(j=0;j<FRAC;j=j+1)if(f[j])lead=j;
    ceiling_pow2=-126-FRAC+lead+((f&(f-1'b1))!=0);
   end
  end
 endfunction
 reg [N*W-1:0] values_r;reg signed [15:0] exponent_r;reg valid_r;
 wire [N*8-1:0] next_q;wire [N*2-1:0] next_bin;
 wire [N-1:0] next_sign,next_one,next_invalid;
 generate for(g=0;g<N;g=g+1) begin:encode
  wire [W-1:0] v=values_r[g*W+:W];
  wire [W-2:0] mag=v[W-2:0];
  integer floor_e,j,normal_e,scale_e;reg signed [15:0] lsb;reg [1:0] b;
  reg [FRAC:0] mant;reg [7:0] ex;
  always @* begin
   ex=v[FRAC+:8];mant={ex!=0,v[FRAC-1:0]};floor_e=-32768;
   normal_e=ex;if(normal_e==0)normal_e=-126;else normal_e=normal_e-127;
   for(j=0;j<=FRAC;j=j+1)if(mant[j])floor_e=normal_e-FRAC+j;
   // <= boundary matters: values exactly at scale/4 use the next bin.
   b=0;
   for(j=1;j<4;j=j+1)
    if(mag==0 || floor_e< $signed(exponent_r)-2*j ||
       (floor_e==$signed(exponent_r)-2*j && (mant&(mant-1'b1))==0)) b=j;
   // Convert the unsigned bin to a signed INTEGER before exponent arithmetic.
   // Otherwise a negative top_exp is zero-extended in a mixed expression.
   scale_e=b;scale_e=$signed(exponent_r)-2*scale_e;lsb=scale_e-8;
  end
  wire sat,ix,iv,sg;wire [7:0] code;
  fc_fp_to_quant #(.FRAC(FRAC),.Q_W(8)) quant(v,lsb,code,sg,sat,ix,iv);
  assign next_q[g*8+:8]=code;
  assign next_bin[g*2+:2]=b;
  assign next_sign[g]=v[W-1];
  assign next_invalid[g]=&ex;
  assign next_one[g]=mag!=0 && floor_e>=scale_e;
 end endgenerate
 always @(posedge clk) begin
  if(!rst_n)begin valid_r<=0;out_valid<=0;q<=0;bin<=0;sign_bits<=0;true_one<=0;top_exp<=0;invalid<=0;values_r<=0;exponent_r<=0;end
  else begin
   valid_r<=in_valid;out_valid<=valid_r;
   if(in_valid)begin values_r<=values;exponent_r<=ceiling_pow2(tree[0]);end
   if(valid_r)begin q<=next_q;bin<=next_bin;sign_bits<=next_sign;true_one<=next_one;top_exp<=exponent_r;invalid<=|next_invalid;end
  end
 end
endmodule
