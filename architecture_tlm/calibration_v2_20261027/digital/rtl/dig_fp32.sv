`timescale 1ns/1ps
// Calibration candidate: RNE, input/output flush-to-zero, canonical NaN.
// Not a claim of complete IEEE-754 gradual-underflow support or 500 MHz timing.
// status[4:0] = {invalid_or_nan, input_flushed, output_flushed, overflow, inexact}.
// Global elastic stall: a blocked valid output freezes the whole pipeline.
module dig_fp32_add(
 input wire clk,rst_n,in_valid,output wire in_ready,
 input wire [31:0] a,b,output wire out_valid,input wire out_ready,
 output reg [31:0] y,output reg [4:0] status
);
 localparam integer L=7;
 reg [L-1:0] valid;
 reg [L-1:0] special;
 reg [31:0] special_y[0:L-1];
 reg [4:0] flags[0:L-1];
 wire advance=!valid[L-1]||out_ready;
 assign in_ready=rst_n&&advance;
 assign out_valid=rst_n&&valid[L-1];
 wire [31:0] aa=(a[30:23]==0)?{a[31],31'b0}:a;
 wire [31:0] bb=(b[30:23]==0)?{b[31],31'b0}:b;
 wire input_flush=((a[30:23]==0)&&(a[22:0]!=0))||((b[30:23]==0)&&(b[22:0]!=0));
 wire na=(aa[30:23]==255)&&(aa[22:0]!=0),nb=(bb[30:23]==255)&&(bb[22:0]!=0);
 wire ia=(aa[30:23]==255),ib=(bb[30:23]==255);
 wire za=(aa[30:0]==0),zb=(bb[30:0]==0);
 reg s_special;
 reg [31:0] s_special_y;
 reg [4:0] s_flags;
 always @* begin
  s_special=1'b1;s_special_y=0;s_flags={1'b0,input_flush,3'b0};
  if(na||nb||(ia&&ib&&(aa[31]!=bb[31]))) begin s_special_y=32'h7fc00000;s_flags[4]=1'b1;end
  else if(ia) s_special_y=aa;
  else if(ib) s_special_y=bb;
  else if(za&&zb) s_special_y={aa[31]&bb[31],31'b0};
  else if(za) s_special_y=bb;
  else if(zb) s_special_y=aa;
  else s_special=1'b0;
 end
 reg [23:0] big0,small0;
 reg [7:0] exp0,diff0;
 reg sign0,subtract0;
 reg [26:0] big1,small1;
 reg [7:0] exp1;
 reg sign1,subtract1;
 reg [27:0] sum2,sum3;
 reg [7:0] exp2,exp3;
 reg sign2,sign3;
 reg [4:0] left3;
 reg carry3,zero3;
 reg [26:0] norm4;
 reg signed [10:0] exp4,exp5;
 reg sign4,sign5,zero4,zero5,tiny_to_normal5;
 reg [24:0] rounded5;
 function automatic [26:0] right_jam27(input [26:0] x,input [7:0] sh);
  integer k;reg sticky;
  begin
   sticky=0;
   if(sh==0) right_jam27=x;
   else if(sh>=27) right_jam27={26'b0,|x};
   else begin
    for(k=0;k<27;k=k+1) if(k<sh) sticky=sticky|x[k];
    right_jam27=(x>>sh);right_jam27[0]=right_jam27[0]|sticky;
   end
  end
 endfunction
 integer z,j;
 reg found;
 reg [4:0] leading;
 always @* begin
  leading=0;found=0;
  for(z=26;z>=0;z=z-1) if(!found&&sum2[z]) begin leading=26-z;found=1;end
 end
 wire [23:0] q5=rounded5[24]?rounded5[24:1]:rounded5[23:0];
 wire signed [10:0] final_exp=exp5+(rounded5[24]?11'sd1:11'sd0);
 always @(posedge clk) begin
  if(!rst_n) begin
   valid<=0;special<=0;y<=0;status<=0;
   big0<=0;small0<=0;exp0<=0;diff0<=0;sign0<=0;subtract0<=0;
   big1<=0;small1<=0;exp1<=0;sign1<=0;subtract1<=0;
   sum2<=0;exp2<=0;sign2<=0;sum3<=0;exp3<=0;sign3<=0;left3<=0;carry3<=0;zero3<=1;
   norm4<=0;exp4<=0;sign4<=0;zero4<=1;rounded5<=0;exp5<=0;sign5<=0;zero5<=1;tiny_to_normal5<=0;
   for(j=0;j<L;j=j+1) begin special_y[j]<=0;flags[j]<=0;end
  end else if(advance) begin
   valid[0]<=in_valid;
   for(j=1;j<L;j=j+1) begin valid[j]<=valid[j-1];if(valid[j-1]) begin special[j]<=special[j-1];special_y[j]<=special_y[j-1];flags[j]<=flags[j-1];end end
   if(in_valid) begin
    special[0]<=s_special;special_y[0]<=s_special_y;flags[0]<=s_flags;
    if(aa[30:0]>=bb[30:0]) begin
     big0<={1'b1,aa[22:0]};small0<={1'b1,bb[22:0]};exp0<=aa[30:23];diff0<=aa[30:23]-bb[30:23];sign0<=aa[31];
    end else begin
     big0<={1'b1,bb[22:0]};small0<={1'b1,aa[22:0]};exp0<=bb[30:23];diff0<=bb[30:23]-aa[30:23];sign0<=bb[31];
    end
    subtract0<=aa[31]^bb[31];
   end
   if(valid[0]) begin big1<={big0,3'b0};small1<=right_jam27({small0,3'b0},diff0);exp1<=exp0;sign1<=sign0;subtract1<=subtract0;end
   if(valid[1]) begin sum2<=subtract1?({1'b0,big1}-{1'b0,small1}):({1'b0,big1}+{1'b0,small1});exp2<=exp1;sign2<=sign1;end
   if(valid[2]) begin sum3<=sum2;exp3<=exp2;sign3<=sign2;left3<=leading;carry3<=sum2[27];zero3<=(sum2==0);end
   if(valid[3]) begin
    sign4<=sign3;zero4<=zero3;
    if(carry3) begin norm4<={sum3[27:2],sum3[1]|sum3[0]};exp4<=$signed({3'b0,exp3})+11'sd1;end
    else begin norm4<=sum3[26:0]<<left3;exp4<=$signed({3'b0,exp3})-$signed({6'b0,left3});end
   end
   if(valid[4]) begin
    rounded5<={1'b0,norm4[26:3]}+(norm4[2]&&(norm4[1]||norm4[0]||norm4[3]));
    exp5<=exp4;sign5<=sign4;zero5<=zero4;
    tiny_to_normal5<=(exp4==0)&&(norm4[26:3]==24'hffffff);
    flags[5]<=flags[4]|{4'b0,|norm4[2:0]};
   end
   if(valid[5]) begin
    status<=flags[5];
    if(special[5]) begin y<=special_y[5];status<=flags[5]&5'b11000;end
    else if(zero5) begin y<=32'b0;status<=flags[5]&5'b11000;end
    else if(tiny_to_normal5) begin y<={sign5,8'h01,23'b0};status<=flags[5]|5'b00001;end
    else if(final_exp>=255) begin y<={sign5,8'hff,23'b0};status<=flags[5]|5'b00011;end
    else if(final_exp<=0) begin y<={sign5,31'b0};status<=flags[5]|5'b00101;end
    else y<={sign5,final_exp[7:0],q5[22:0]};
   end
  end
 end
endmodule

module dig_float_mul_pipe #(parameter integer BF16=0)(
 input wire clk,rst_n,in_valid,output wire in_ready,
 input wire [31:0] a,b,output wire out_valid,input wire out_ready,
 output reg [31:0] y,output reg [4:0] status
);
 localparam integer L=7;
 wire [31:0] ax=BF16?{a[15:0],16'b0}:a;
 wire [31:0] bx=BF16?{b[15:0],16'b0}:b;
 wire [31:0] aa=(ax[30:23]==0)?{ax[31],31'b0}:ax;
 wire [31:0] bb=(bx[30:23]==0)?{bx[31],31'b0}:bx;
 wire sign_in=aa[31]^bb[31];
 wire flush=((ax[30:23]==0)&&(ax[22:0]!=0))||((bx[30:23]==0)&&(bx[22:0]!=0));
 wire na=(aa[30:23]==255)&&(aa[22:0]!=0),nb=(bb[30:23]==255)&&(bb[22:0]!=0);
 wire ia=(aa[30:23]==255),ib=(bb[30:23]==255),za=(aa[30:0]==0),zb=(bb[30:0]==0);
 reg [L-1:0] valid,special;
 reg [31:0] special_y[0:L-1];
 reg [4:0] flags[0:L-1];
 reg signp[0:L-1];
 reg signed [10:0] expp[0:L-1];
 wire advance=!valid[L-1]||out_ready;
 assign in_ready=rst_n&&advance;
 assign out_valid=rst_n&&valid[L-1];
 reg [23:0] ma0,mb0;
 reg [23:0] pp00,pp01,pp10,pp11;
 reg [47:0] pair20,pair21,product3;
 reg [23:0] mant4;
 reg guard4,sticky4,tiny_to_normal5;
 reg [24:0] rounded5;
 wire [23:0] mant_final=rounded5[24]?rounded5[24:1]:rounded5[23:0];
 wire signed [10:0] exp_final=expp[5]+(rounded5[24]?11'sd1:11'sd0);
 integer j;
 always @(posedge clk) begin
  if(!rst_n) begin
   valid<=0;special<=0;y<=0;status<=0;ma0<=0;mb0<=0;
   pp00<=0;pp01<=0;pp10<=0;pp11<=0;pair20<=0;pair21<=0;product3<=0;mant4<=0;guard4<=0;sticky4<=0;rounded5<=0;tiny_to_normal5<=0;
   for(j=0;j<L;j=j+1) begin special_y[j]<=0;flags[j]<=0;signp[j]<=0;expp[j]<=0;end
  end else if(advance) begin
   valid[0]<=in_valid;
   for(j=1;j<L;j=j+1) begin valid[j]<=valid[j-1];if(valid[j-1]) begin special[j]<=special[j-1];special_y[j]<=special_y[j-1];flags[j]<=flags[j-1];signp[j]<=signp[j-1];expp[j]<=expp[j-1];end end
   if(in_valid) begin
    ma0<={1'b1,aa[22:0]};mb0<={1'b1,bb[22:0]};
    signp[0]<=sign_in;expp[0]<=$signed({3'b0,aa[30:23]})+$signed({3'b0,bb[30:23]})-11'sd127;
    flags[0]<={1'b0,flush,3'b0};special[0]<=1;
    if(na||nb||(ia&&zb)||(ib&&za)) begin special_y[0]<=32'h7fc00000;flags[0]<={1'b1,flush,3'b0};end
    else if(ia||ib) special_y[0]<={sign_in,8'hff,23'b0};
    else if(za||zb) special_y[0]<={sign_in,31'b0};
    else begin special[0]<=0;special_y[0]<=0;end
   end
   // Split significand multiply: four independent 12x12 products.
   // BF16 constants prune most logic; its effective multiplier is 8x8.
   if(valid[0]) begin
    pp00<=ma0[11:0]*mb0[11:0];pp01<=ma0[11:0]*mb0[23:12];
    pp10<=ma0[23:12]*mb0[11:0];pp11<=ma0[23:12]*mb0[23:12];
   end
   if(valid[1]) begin pair20<={24'b0,pp00}+{12'b0,pp01,12'b0};pair21<={12'b0,pp10,12'b0}+{pp11,24'b0};end
   if(valid[2]) product3<=pair20+pair21;
   if(valid[3]) begin
    if(product3[47]) begin mant4<=product3[47:24];guard4<=product3[23];sticky4<=|product3[22:0];expp[4]<=expp[3]+11'sd1;end
    else begin mant4<=product3[46:23];guard4<=product3[22];sticky4<=|product3[21:0];end
   end
   if(valid[4]) begin
    rounded5<={1'b0,mant4}+(guard4&&(sticky4||mant4[0]));flags[5]<=flags[4]|{4'b0,guard4|sticky4};
    // RNE on the subnormal lattice can round up to the smallest NORMAL.
    // Preserve this result before FTZ; all other tiny results flush to zero.
    tiny_to_normal5<=(expp[4]==0)&&(mant4==24'hffffff);
   end
   if(valid[5]) begin
    status<=flags[5];
    if(special[5]) begin y<=special_y[5];status<=flags[5]&5'b11000;end
    else if(tiny_to_normal5) begin y<={signp[5],8'h01,23'b0};status<=flags[5]|5'b00001;end
    else if(exp_final>=255) begin y<={signp[5],8'hff,23'b0};status<=flags[5]|5'b00011;end
    else if(exp_final<=0) begin y<={signp[5],31'b0};status<=flags[5]|5'b00101;end
    else y<={signp[5],exp_final[7:0],mant_final[22:0]};
   end
  end
 end
endmodule

module dig_fp32_mul(input wire clk,rst_n,in_valid,output wire in_ready,input wire [31:0] a,b,output wire out_valid,input wire out_ready,output wire [31:0] y,output wire [4:0] status);
 dig_float_mul_pipe #(.BF16(0)) core(.*);
endmodule
module dig_bf16_mul(input wire clk,rst_n,in_valid,output wire in_ready,input wire [31:0] a,b,output wire out_valid,input wire out_ready,output wire [31:0] y,output wire [4:0] status);
 dig_float_mul_pipe #(.BF16(1)) core(.*);
endmodule

module dig_fp32_to_bf16(input wire clk,rst_n,in_valid,output wire in_ready,input wire [31:0] a,b,output wire out_valid,input wire out_ready,output reg [31:0] y,output reg [4:0] status);
 reg [1:0] valid;
 reg [16:0] rounded;
 reg [15:0] special_y;
 reg special;
 reg [4:0] flags;
 wire advance=!valid[1]||out_ready;
 assign in_ready=rst_n&&advance;assign out_valid=rst_n&&valid[1];
 wire inc=a[15]&&((|a[14:0])||a[16]);
 always @(posedge clk) begin
  if(!rst_n) begin valid<=0;rounded<=0;special_y<=0;special<=0;flags<=0;y<=0;status<=0;end
  else if(advance) begin
   valid[0]<=in_valid;valid[1]<=valid[0];
   if(in_valid) begin
    rounded<={1'b0,a[31:16]}+inc;flags<={4'b0,|a[15:0]};special<=0;special_y<=0;
    if(a[30:23]==255) begin special<=1;special_y<=(a[22:0]!=0)?16'h7fc0:a[31:16];flags<={(a[22:0]!=0),4'b0};end
    else if(a[30:23]==0) begin special<=1;special_y<={a[31],15'b0};flags<={1'b0,(a[22:0]!=0),3'b0};end
   end
   if(valid[0]) begin
    y<={16'b0,special?special_y:rounded[15:0]};status<=flags;
    if(!special&&(rounded[14:7]==255)) status<=flags|5'b00011;
   end
  end
 end
endmodule
