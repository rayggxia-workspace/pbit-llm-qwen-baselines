`timescale 1ns/1ps
// Conventional deterministic FP32 multiply, RNE. Reuses the project's
// integer-normalization/rounding circuit. No real, shortreal, DPI or black box.
module nr_fp32_mul(input wire [31:0] a,b, output wire [31:0] y);
 wire [7:0] ea=a[30:23],eb=b[30:23];
 wire [23:0] ma={ea!=0,a[22:0]},mb={eb!=0,b[22:0]};
 wire [47:0] magnitude=ma*mb;
 wire sign_y=a[31]^b[31];
 wire signed [48:0] signed_product=sign_y?-$signed({1'b0,magnitude}):$signed({1'b0,magnitude});
 reg signed [15:0] lsb;
 integer ex_a,ex_b;
 always @* begin
  ex_a=ea;ex_b=eb;if(ex_a==0)ex_a=1;if(ex_b==0)ex_b=1;
  lsb=ex_a+ex_b-300;
 end
 wire [31:0] ordinary;wire ov,tn,ix;
 fc_fixed_to_fp #(.IN_W(49),.FRAC(23)) cv(signed_product,lsb,ordinary,ov,tn,ix);
 wire nan_a=(ea==255&&a[22:0]!=0),nan_b=(eb==255&&b[22:0]!=0);
 wire zero_a=(ea==0&&a[22:0]==0),zero_b=(eb==0&&b[22:0]==0);
 assign y=(nan_a||nan_b||(ea==255&&zero_b)||(eb==255&&zero_a))?32'h7fc00000:
          (ea==255||eb==255)?{sign_y,8'hff,23'b0}:
          (zero_a||zero_b)?{sign_y,31'b0}:ordinary;
endmodule

module nr_fp32_lerp(input wire [31:0] a,b,t, output wire [31:0] y);
 wire [31:0] diff,product;wire [2:0] f0,f1;
 fc_fp_add sub(b,{~a[31],a[30:0]},diff,f0[0],f0[1],f0[2]);
 nr_fp32_mul mul(diff,t,product);
 fc_fp_add add(a,product,y,f1[0],f1[1],f1[2]);
endmodule
