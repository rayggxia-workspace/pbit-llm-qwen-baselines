`timescale 1ns/1ps
// Common characterization payload. Only the selected generate branch exists.
// data: float bits / signed integer; aux: second floating operand;
// exp_a: quant LSB / integer LSB / coefficient exponent / alignment shift;
// exp_b: common fixed-point LSB (case 8 only).
module fc_comb_case #(parameter integer KIND=0)(
 input wire [63:0] data,
 input wire [31:0] aux,
 input wire [23:0] coefficient,
 input wire signed [15:0] exp_a,exp_b,
 output wire [63:0] result,
 output wire [3:0] flags
);
 generate
 if(KIND==0||KIND==1||KIND==2||KIND==3) begin:q
  localparam integer F=(KIND==0||KIND==2)?7:23;
  localparam integer Q=(KIND==3)?16:8;
  localparam [Q-1:0] LIMIT=(KIND==2||KIND==3)?{1'b0,{(Q-1){1'b1}}}:{Q{1'b1}};
  wire [Q-1:0] mag;
  wire sg,sat,ix,inv;
  fc_fp_to_quant #(.FRAC(F),.Q_W(Q),.MAX_MAG(LIMIT)) u(data[F+8:0],exp_a,mag,sg,sat,ix,inv);
  if(KIND==2||KIND==3) begin:signed_code
   wire [Q-1:0] code=sg?(~mag+1'b1):mag;
   assign result={{(64-Q){1'b0}},code};
  end else begin:prob_code
   assign result={{(63-Q){1'b0}},sg,mag};
  end
  assign flags={1'b0,inv,sat,ix};
 end else if(KIND==4||KIND==5||KIND==13||KIND==14) begin:f
  localparam integer IW=(KIND==4||KIND==14)?32:64;
  localparam integer F=(KIND==4||KIND==13)?7:23;
  wire [F+8:0] fp;
  wire ov,tiny,ix;
  fc_fixed_to_fp #(.IN_W(IW),.FRAC(F)) u(data[IW-1:0],exp_a,fp,ov,tiny,ix);
  assign result={{(55-F){1'b0}},fp};assign flags={tiny,1'b0,ov,ix};
 end else if(KIND==6) begin:narrow
  wire [15:0] fp;wire ix,inv,ov;
  fc_fp32_to_bf16 u(data[31:0],fp,ix,inv,ov);
  assign result={48'b0,fp};assign flags={1'b0,inv,ov,ix};
 end else if(KIND==7) begin:widen
  wire [31:0] fp;
  fc_bf16_to_fp32 u(data[15:0],fp);
  assign result={32'b0,fp};assign flags=0;
 end else if(KIND==8) begin:scaled_fixed
  wire signed [63:0] value;wire sat,ix;
  fc_count_to_fixed u(data[31:0],coefficient,exp_a,exp_b,value,sat,ix);
  assign result=value;assign flags={2'b0,sat,ix};
 end else if(KIND==9||KIND==12) begin:scaled_fp
  localparam integer F=(KIND==9)?23:7;
  wire [F+8:0] fp;wire ov,tiny,ix;
  fc_count_to_fp #(.FRAC(F)) u(data[31:0],coefficient,exp_a,fp,ov,tiny,ix);
  assign result={{(55-F){1'b0}},fp};assign flags={tiny,1'b0,ov,ix};
 end else if(KIND==10) begin:align
  wire signed [63:0] value;wire sat,ix;
  fc_fixed_align u(data,exp_a,value,sat,ix);
  assign result=value;assign flags={2'b0,sat,ix};
 end else if(KIND==11) begin:add
  wire [31:0] fp;wire inv,ov,ix;
  fc_fp_add u(data[31:0],aux,fp,inv,ov,ix);
  assign result={32'b0,fp};assign flags={1'b0,inv,ov,ix};
 end else if(KIND==17) begin:probability_u32
  // 33-bit endpoint represents 2**32 exactly, so p=1 always passes a U32 RNG.
  wire [32:0] mag;wire sg,sat,ix,inv;
  fc_fp_to_quant #(.FRAC(23),.Q_W(33),.MAX_MAG(33'h100000000)) u(data[31:0],exp_a,mag,sg,sat,ix,inv);
  wire neg_nonzero=data[31]&&(data[30:0]!=0)&&!inv;
  assign result=neg_nonzero?64'b0:{31'b0,mag};
  assign flags={1'b0,inv,sat|neg_nonzero,ix|neg_nonzero};
 end else if(KIND==15||KIND==16) begin:scale_fp
  localparam integer F=(KIND==15)?23:7;
  wire [F+8:0] fp;wire ov,tn,ix,inv;
  fc_fp_scale #(.OUT_FRAC(F)) u(data[31:0],exp_a,fp,ov,tn,ix,inv);
  assign result={{(55-F){1'b0}},fp};assign flags={tn,inv,ov,ix};
 end else begin:unsupported
  assign result=0;assign flags=0;
 end
 endgenerate
endmodule

// Equal interface methodology for DC/PT: one input and one output register
// boundary. Throughput 1 value/cycle IF reported STA meets the target period.
// Clock enables are RTL enables, not a claim of inserted ICG or zero idle power.
module fc_conversion_probe #(parameter integer KIND=0)(
 input wire clk,rst_n,in_valid,
 input wire [63:0] data,
 input wire [31:0] aux,
 input wire [23:0] coefficient,
 input wire signed [15:0] exp_a,exp_b,
 output reg out_valid,
 output reg [63:0] result,
 output reg [3:0] flags
);
 reg valid_q;
 reg [63:0] data_q;
 reg [31:0] aux_q;
 reg [23:0] coefficient_q;
 reg signed [15:0] exp_a_q,exp_b_q;
 wire [63:0] comb_result;wire [3:0] comb_flags;
 fc_comb_case #(.KIND(KIND)) u_core(data_q,aux_q,coefficient_q,exp_a_q,exp_b_q,comb_result,comb_flags);
 always @(posedge clk) begin
  if(!rst_n) begin valid_q<=0;out_valid<=0;data_q<=0;aux_q<=0;coefficient_q<=0;
   exp_a_q<=0;exp_b_q<=0;result<=0;flags<=0;end
  else begin
   valid_q<=in_valid;out_valid<=valid_q;
   if(in_valid) begin data_q<=data;aux_q<=aux;coefficient_q<=coefficient;exp_a_q<=exp_a;exp_b_q<=exp_b;end
   if(valid_q) begin result<=comb_result;flags<=comb_flags;end
  end
 end
endmodule

module fc_accum_probe #(parameter integer FIXED=1,ACC_W=64)(
 input wire clk,rst_n,in_valid,first,last,
 input wire signed [31:0] count,
 input wire [23:0] coefficient,
 input wire signed [15:0] coef_exp,common_lsb_exp,
 output wire out_valid,
 output wire [31:0] result,
 output wire [3:0] flags
);
 reg valid_q,first_q,last_q;
 reg signed [31:0] count_q;
 reg [23:0] coefficient_q;
 reg signed [15:0] coef_exp_q,common_exp_q;
 always @(posedge clk) begin
  if(!rst_n) begin valid_q<=0;first_q<=0;last_q<=0;count_q<=0;coefficient_q<=0;coef_exp_q<=0;common_exp_q<=0;end
  else begin
   valid_q<=in_valid;
   if(in_valid) begin first_q<=first;last_q<=last;count_q<=count;
    coefficient_q<=coefficient;coef_exp_q<=coef_exp;common_exp_q<=common_lsb_exp;end
  end
 end
 generate if(FIXED) begin:fixed_path
  wire sat,ix;
  fc_accum_fixed #(.ACC_W(ACC_W)) u_accum(clk,rst_n,valid_q,first_q,last_q,count_q,
   coefficient_q,coef_exp_q,common_exp_q,out_valid,result,sat,ix);
  assign flags={2'b0,sat,ix};
 end else begin:float_path
  wire inv,ov,ix;
  fc_accum_float u_accum(clk,rst_n,valid_q,first_q,last_q,count_q,coefficient_q,
   coef_exp_q,out_valid,result,inv,ov,ix);
  assign flags={1'b0,inv,ov,ix};
 end endgenerate
endmodule
