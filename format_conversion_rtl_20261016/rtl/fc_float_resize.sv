`timescale 1ns/1ps
module fc_bf16_to_fp32(input wire [15:0] bf16,output wire [31:0] fp32);
 assign fp32={bf16,16'b0};
endmodule

// Exact power-of-two scaling, optionally fused FP32->BF16 rounding. Useful for
// N=512 sparse-PV mean: scale_pow=-9. Non-power-of-two division is not included.
module fc_fp_scale #(parameter integer IN_FRAC=23,OUT_FRAC=23)(
 input wire [IN_FRAC+8:0] value_in,
 input wire signed [15:0] scale_pow,
 output wire [OUT_FRAC+8:0] value_out,
 output wire overflow,tiny,inexact,invalid
);
 wire sign_in=value_in[IN_FRAC+8];
 wire [7:0] ex=value_in[IN_FRAC+7:IN_FRAC];
 wire [IN_FRAC-1:0] frac=value_in[IN_FRAC-1:0];
 wire [IN_FRAC:0] mag={ex!=0,frac};
 wire signed [IN_FRAC+1:0] signed_mag=sign_in?-$signed({1'b0,mag}):$signed({1'b0,mag});
 integer tmp;
 reg signed [15:0] lsb;
 always @* begin
  tmp=ex;if(ex==0)tmp=1;
  tmp=tmp-127-IN_FRAC;tmp=tmp+$signed(scale_pow);
  if(tmp>32767)lsb=32767;else if(tmp< -32768)lsb=-32768;else lsb=tmp;
 end
 wire [OUT_FRAC+8:0] converted;wire ov,tn,ix;
 fc_fixed_to_fp #(.IN_W(IN_FRAC+2),.FRAC(OUT_FRAC)) u(signed_mag,lsb,converted,ov,tn,ix);
 wire special=&ex;
 assign invalid=special&&(frac!=0);
 assign value_out=invalid?{1'b0,8'hff,1'b1,{(OUT_FRAC-1){1'b0}}}:
  special?{sign_in,8'hff,{OUT_FRAC{1'b0}}}:
  (ex==0&&frac==0)?{sign_in,{(OUT_FRAC+8){1'b0}}}:converted;
 assign overflow=special?1'b0:ov;
 assign tiny=special?1'b0:tn;
 assign inexact=special?1'b0:ix;
endmodule

module fc_fp32_to_bf16(
 input wire [31:0] fp32,output wire [15:0] bf16,
 output wire inexact,invalid,overflow
);
 wire nan_value=(&fp32[30:23])&&(fp32[22:0]!=0);
 wire [16:0] rounded={1'b0,fp32[31:16]}+
  ((fp32[15:0]>16'h8000)||((fp32[15:0]==16'h8000)&&fp32[16]));
 assign bf16=nan_value?(fp32[31:16]|16'h0040):rounded[15:0];
 assign invalid=nan_value;
 assign overflow=(!(&fp32[30:23]))&&(&bf16[14:7]);
 assign inexact=!nan_value&&(fp32[15:0]!=0);
endmodule
