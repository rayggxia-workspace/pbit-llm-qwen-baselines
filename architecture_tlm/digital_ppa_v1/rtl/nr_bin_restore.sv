`timescale 1ns/1ps
// Exact integer bit-plane/bin reconstruction BEFORE one floating conversion.
// Counts flatten as ((bin*2+input_sign)*8+weight_bit)*COUNT_W; input_sign 0=+.
// W8 is two's complement: weight bit7 has NEGATIVE positional weight.
// Does not include stochastic counter storage, SRAM or random sources.
module nr_bin_restore #(parameter integer COUNT_W=12,T_LOG2=5,FUSED=0)(
 input wire [4*2*8*COUNT_W-1:0] counts,
 input wire signed [15:0] top_exp,
 input wire [31:0] weight_scale,
 output wire [31:0] fp32_out
);
 localparam integer IW=COUNT_W+18;
 reg signed [IW-1:0] total,term,difference;
 integer b,p;
 always @* begin
  total=0;term=0;difference=0;
  for(b=0;b<4;b=b+1)for(p=0;p<8;p=p+1)begin
   difference=$signed({1'b0,counts[((b*2)*8+p)*COUNT_W+:COUNT_W]})-
              $signed({1'b0,counts[((b*2+1)*8+p)*COUNT_W+:COUNT_W]});
   term=difference<<<(p+2*(3-b));
   total=total+(p==7?-term:term);
  end
 end
 wire signed [15:0] lsb=$signed(top_exp)-6-T_LOG2;
 wire [31:0] unscaled;wire ov,tn,ix;
 fc_fixed_to_fp #(.IN_W(IW),.FRAC(23)) cv(total,lsb,unscaled,ov,tn,ix);
 generate if(FUSED)begin:fused
  // Optional cost candidate: changes intermediate FP32 rounding order.
  nr_fp32_mul scale(unscaled,weight_scale,fp32_out);
 end else begin:literal
  // Preserve separate per-bin scale multiply and ordered FP32 bin summation.
  wire [31:0] sum[0:4];assign sum[0]=0;
  genvar bn;
  for(bn=0;bn<4;bn=bn+1)begin:bin_unit
   reg signed [COUNT_W+9:0] integer_sum,diff,weighted;
   integer bit_index;
   always @* begin
    integer_sum=0;diff=0;weighted=0;
    for(bit_index=0;bit_index<8;bit_index=bit_index+1)begin
     diff=$signed({1'b0,counts[((bn*2)*8+bit_index)*COUNT_W+:COUNT_W]})-
          $signed({1'b0,counts[((bn*2+1)*8+bit_index)*COUNT_W+:COUNT_W]});
     weighted=diff<<<bit_index;
     integer_sum=integer_sum+(bit_index==7?-weighted:weighted);
    end
   end
   wire signed [15:0] bin_lsb=$signed(top_exp)-2*bn-T_LOG2;
   wire [31:0] value,scaled_bin;wire ovb,tnb,ixb;
   fc_fixed_to_fp #(.IN_W(COUNT_W+10),.FRAC(23)) cv_bin(integer_sum,bin_lsb,value,ovb,tnb,ixb);
   nr_fp32_mul mul_bin(value,weight_scale,scaled_bin);
   fc_fp_add add_bin(sum[bn],scaled_bin,sum[bn+1],,,);
  end
  assign fp32_out=sum[4];
 end endgenerate
endmodule
