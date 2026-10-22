`timescale 1ns/1ps
// Candidate deterministic FP32 nonlinear circuits for characterization.
// KIND 0=sigmoid, 1=exp(x), DOMAIN x<=0 with x<=-16 flushed to0;
// 2=reciprocal, 3=reciprocal sqrt. Piecewise-linear ROM + FP32 arithmetic.
// They are APPROXIMATIONS and do not inherit the old FP32 model's PPL.
module nr_unary_lut #(parameter integer KIND=0)(
 input wire [31:0] x,output wire [31:0] y
);
 wire [7:0] ex=x[30:23];wire special=&ex;
 wire nan_value=special&&x[22:0]!=0;
 generate if(KIND<2)begin:bounded
  `include "nr_sigmoid_rom.svh"
  `include "nr_expneg_rom.svh"
  wire [17:0] q;wire sg,sat,ix,iv;
  fc_fp_to_quant #(.FRAC(23),.Q_W(18),.MAX_MAG(18'd131072)) cv(x,-16'sd13,q,sg,sat,ix,iv);
  wire [10:0] index=q>>8;
  wire [10:0] next_index=index==512?11'd512:index+1'b1;
  wire [10:0] sign_offset=x[31]?11'd513:11'd0;
  wire [31:0] v0,v1;
  if(KIND==0)begin:sig
   assign v0=nr_sigmoid_rom(index+sign_offset);
   assign v1=nr_sigmoid_rom(next_index+sign_offset);
  end else begin:expn
   assign v0=nr_expneg_rom(index);assign v1=nr_expneg_rom(next_index);
  end
  wire [31:0] fraction,interpolated;wire f0,f1,f2;
  fc_fixed_to_fp #(.IN_W(9),.FRAC(23)) frac($signed({1'b0,q[7:0]}),-16'sd8,fraction,f0,f1,f2);
  nr_fp32_lerp lerp(v0,v1,fraction,interpolated);
  if(KIND==0)begin:outsig
   assign y=nan_value ? 32'h7fc00000 : ((x[30:0]>=32'h41800000) ? (x[31] ? 32'b0 : 32'h3f800000) : interpolated);
  end else begin:outexp
   assign y=nan_value ? 32'h7fc00000 : (!x[31] ? 32'h3f800000 : ((x[30:0]>=32'h41800000) ? 32'b0 : interpolated));
  end
 end else begin:unbounded
  `include "nr_recip_rom.svh"
  `include "nr_rsqrt_rom.svh"
  integer e,j,lead;reg [23:0] normalized;reg signed [15:0] scale_exp;
  always @* begin
   lead=0;normalized={1'b1,x[22:0]};e=ex;e=e-127;
   if(ex==0)begin
    for(j=0;j<23;j=j+1)if(x[j])lead=j;
    normalized={1'b0,x[22:0]}<<(23-lead);e=-149+lead;
   end
   scale_exp=(KIND==2)?-e:-(e>>>1);
  end
  wire [10:0] index={3'b0,normalized[22:15]};
  wire [31:0] v0,v1;
  if(KIND==2)begin:rec
   assign v0=nr_recip_rom(index);assign v1=nr_recip_rom(index+1'b1);
  end else begin:rsq
   assign v0=nr_rsqrt_rom(index);assign v1=nr_rsqrt_rom(index+1'b1);
  end
  wire [31:0] fraction,interpolated,parity_adjusted,scaled;
  wire f0,f1,f2,f3,f4,f5,f6;
  fc_fixed_to_fp #(.IN_W(16),.FRAC(23)) frac($signed({1'b0,normalized[14:0]}),-16'sd15,fraction,f0,f1,f2);
  nr_fp32_lerp lerp(v0,v1,fraction,interpolated);
  if(KIND==3)begin:odd
   wire [31:0] adjusted;nr_fp32_mul m(interpolated,32'h3f3504f3,adjusted);
   assign parity_adjusted=e[0]?adjusted:interpolated;
  end else assign parity_adjusted={x[31],interpolated[30:0]};
  fc_fp_scale #(.IN_FRAC(23),.OUT_FRAC(23)) sc(parity_adjusted,scale_exp,scaled,f3,f4,f5,f6);
  if(KIND==2)begin:outrec
   assign y=nan_value?32'h7fc00000:(x[30:0]==0?{x[31],8'hff,23'b0}:(special?{x[31],31'b0}:scaled));
  end else begin:outrsq
   assign y=(nan_value||(x[31]&&x[30:0]!=0))?32'h7fc00000:(x[30:0]==0?{x[31],8'hff,23'b0}:(special?32'b0:scaled));
  end
 end endgenerate
endmodule
