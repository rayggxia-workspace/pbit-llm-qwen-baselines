`timescale 1ns/1ps
module nr_swiglu_fp32(input wire [31:0] g,u,output wire [31:0] z);
 wire [31:0] sigmoid,silu;
 nr_unary_lut #(.KIND(0)) sig(g,sigmoid);
 nr_fp32_mul m0(g,sigmoid,silu),m1(silu,u,z);
endmodule

module nr_rms_apply(input wire [15:0] x,gamma,input wire [31:0] inv_rms,output wire [15:0] y);
 wire [31:0] a,b;wire f0,f1,f2;
 nr_fp32_mul m0({x,16'b0},inv_rms,a),m1(a,{gamma,16'b0},b);
 fc_fp32_to_bf16 cv(b,y,f0,f1,f2);
endmodule

module nr_rope_pair(input wire [15:0] x0,x1,input wire [31:0] cosine,sine,output wire [31:0] y0,y1);
 wire [31:0] ac,bs,as,bc;wire [2:0] f0,f1;
 nr_fp32_mul m0({x0,16'b0},cosine,ac),m1({x1,16'b0},sine,bs),m2({x0,16'b0},sine,as),m3({x1,16'b0},cosine,bc);
 fc_fp_add a0(ac,{~bs[31],bs[30:0]},y0,f0[0],f0[1],f0[2]),a1(as,bc,y1,f1[0],f1[1],f1[2]);
endmodule

// Common stateful accumulator. BF16 V or BF16*BF16 products, FP32 state.
// first/last valid same edge are supported. No hidden vector/tensor SRAM.
// KIND0: repeated V sum/2^mean_log2 -> BF16 on last.
// KIND1: BF16 MAC -> FP32; KIND2: sum(x*x)*inverse_length then rsqrt(+epsilon).
module nr_stream_accumulator #(parameter integer KIND=0)(
 input wire clk,rst_n,in_valid,first,last,
 input wire [15:0] a,b,
 input wire [7:0] mean_log2,
 input wire [31:0] inverse_length,epsilon,
 output reg out_valid,output reg [31:0] fp32_result,output reg [15:0] bf16_result
);
 reg [31:0] state;
 wire [31:0] product,operand,sum,mean,eps_sum,inv;
 wire [15:0] bfmean;wire [2:0] flags;wire f0,f1,f2,f3;
 nr_fp32_mul mul({a,16'b0},{(KIND==2?a:b),16'b0},product);
 assign operand=(KIND==0)?{a,16'b0}:product;
 fc_fp_add add(first?32'b0:state,operand,sum,flags[0],flags[1],flags[2]);
 wire signed [15:0] neg_log=-$signed({1'b0,mean_log2});
 fc_fp_scale #(.IN_FRAC(23),.OUT_FRAC(7)) mean_cv(sum,neg_log,bfmean,f0,f1,f2,f3);
 nr_fp32_mul mmean(sum,inverse_length,mean);
 fc_fp_add ae(mean,epsilon,eps_sum,,,);
 nr_unary_lut #(.KIND(3)) rs(eps_sum,inv);
 always @(posedge clk) begin
  if(!rst_n)begin state<=0;out_valid<=0;fp32_result<=0;bf16_result<=0;end
  else begin
   out_valid<=0;
   if(in_valid)begin
    state<=sum;
    if(last)begin out_valid<=1;fp32_result<=(KIND==2)?inv:sum;bf16_result<=bfmean;end
   end
  end
 end
endmodule

// Conventional scalar min/max compare exchange. Finite signed FP32 ordering;
// NaNs flagged and ordered after finite values. Fixed-budget network building cell.
module nr_compare_exchange(input wire [31:0] a,b,input wire [15:0] ia,ib,
 output wire [31:0] lo,hi,output wire [15:0] ilo,ihi,output wire invalid);
 wire na=(&a[30:23])&&a[22:0]!=0,nb=(&b[30:23])&&b[22:0]!=0;
 wire [31:0] ka=a[31]?~a:(a^32'h80000000),kb=b[31]?~b:(b^32'h80000000);
 wire equal_value=(a==b)||((a[30:0]==0)&&(b[30:0]==0));
 wire swap=(na&&!nb)||(!na&&!nb&&((!equal_value&&ka>kb) || (equal_value&&ia>ib)));
 assign lo=swap?b:a;assign hi=swap?a:b;assign ilo=swap?ib:ia;assign ihi=swap?ia:ib;assign invalid=na|nb;
endmodule
