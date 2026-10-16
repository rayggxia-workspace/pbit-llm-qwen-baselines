`timescale 1ns/1ps
// Small conventional binary floating-point adder, E=8, bias=127, RNE.
// Combinational, supports subnormals, signed zeros, infinity, canonical NaN.
// Separate multiply/restoration before this add: NOT fused multiply-add.
module fc_fp_add #(parameter integer FRAC=23)(
 input wire [FRAC+8:0] a,b,
 output reg [FRAC+8:0] y,
 output reg invalid,overflow,inexact
);
 localparam integer W=FRAC+5;
 reg sa,sb,sign_big;
 reg [7:0] ea,eb,packed_exp;
 reg [FRAC:0] ma,mb;
 reg [W-1:0] big,small_operand,aligned,sum;
 reg [FRAC+1:0] mant;
 reg sticky,guard_bit;
 integer e,d,j;
 always @* begin
  sa=a[FRAC+8];sb=b[FRAC+8];ea=a[FRAC+7:FRAC];eb=b[FRAC+7:FRAC];
  ma={ea!=0,a[FRAC-1:0]};mb={eb!=0,b[FRAC-1:0]};
  sign_big=0;big=0;small_operand=0;aligned=0;sum=0;mant=0;packed_exp=0;
  sticky=0;guard_bit=0;e=0;d=0;y=0;invalid=0;overflow=0;inexact=0;
  if((ea==255&&a[FRAC-1:0]!=0)||(eb==255&&b[FRAC-1:0]!=0)||
      (ea==255&&eb==255&&sa!=sb)) begin
   y={1'b0,8'hff,1'b1,{(FRAC-1){1'b0}}};invalid=1;
  end else if(ea==255) y=a;
  else if(eb==255) y=b;
  else if(ma==0&&mb==0) y={sa&sb,{(FRAC+8){1'b0}}};
  else begin
   if(ea==0) ea=1;if(eb==0) eb=1;
   if(ea>eb||(ea==eb&&ma>=mb)) begin
    big={1'b0,ma,3'b000};small_operand={1'b0,mb,3'b000};sign_big=sa;e=ea;d=ea-eb;
   end else begin
    big={1'b0,mb,3'b000};small_operand={1'b0,ma,3'b000};sign_big=sb;e=eb;d=eb-ea;
   end
   aligned=small_operand>>d;
   for(j=0;j<W;j=j+1) if(j<d) sticky=sticky|small_operand[j];
   aligned[0]=aligned[0]|sticky;
   if(sa==sb) sum=big+aligned;else sum=big-aligned;
   if(sum[FRAC+4]) begin sum=(sum>>1)|sum[0];e=e+1;end
   for(j=0;j<FRAC+3;j=j+1)
    if(!sum[FRAC+3]&&sum!=0&&e>1) begin sum=sum<<1;e=e-1;end
   guard_bit=sum[2];sticky=sum[1]|sum[0];inexact=guard_bit|sticky;
   mant={1'b0,sum[FRAC+3:3]}+(guard_bit&&(sticky||sum[3]));
   if(mant[FRAC+1]) begin mant=mant>>1;e=e+1;end
   if(sum==0) y=0;
   else if(e>=255) begin y={sign_big,8'hff,{FRAC{1'b0}}};overflow=1;inexact=1;end
   else begin
    packed_exp=(e==1&&!mant[FRAC])?0:e;
    y={sign_big,packed_exp,mant[FRAC-1:0]};
   end
  end
 end
endmodule
