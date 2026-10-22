`timescale 1ns/1ps
// Registered characterization shell; KIND fixed during synthesis.
// Incoming buses are latched only on in_valid. No PRNG or stimulus is in DUT.
// Simple combinational cores: accepted edge k -> out_valid at edge k+1.
// Native pipelined/stateful cores have their own latency, tested separately.
module nr_digital_probe #(parameter integer KIND=0)(
 input wire clk,rst_n,in_valid,first,last,
 input wire [2047:0] data_a,data_b,
 input wire [31:0] aux0,aux1,
 input wire signed [15:0] scale_exp,
 input wire [7:0] mean_log2,
 output reg out_valid,output reg [2047:0] result
);
 reg [2047:0] ar,br;reg [31:0] u0,u1;reg signed [15:0] exp_r;
 reg [7:0] mean_r;reg valid_r,first_r,last_r;
 always @(posedge clk)begin
  if(!rst_n)begin ar<=0;br<=0;u0<=0;u1<=0;exp_r<=0;mean_r<=0;valid_r<=0;first_r<=0;last_r<=0;end
  else begin
   valid_r<=in_valid;
   if(in_valid)begin ar<=data_a;br<=data_b;u0<=aux0;u1<=aux1;exp_r<=scale_exp;mean_r<=mean_log2;first_r<=first;last_r<=last;end
  end
 end
 wire [2047:0] computed;wire computed_valid;
 generate if(KIND==0)begin:add
  wire [31:0] y;fc_fp_add a(ar[31:0],br[31:0],y,,,);
  assign computed={{2016{1'b0}},y};assign computed_valid=valid_r;
 end else if(KIND==1)begin:mul
  wire [31:0] y;nr_fp32_mul m(ar[31:0],br[31:0],y);
  assign computed={{2016{1'b0}},y};assign computed_valid=valid_r;
 end else if(KIND==2 || KIND==8 || KIND==9)begin:accum
  wire [31:0] y;wire [15:0] b;
  nr_stream_accumulator #(.KIND(KIND==2?1:(KIND==8?0:2))) core(clk,rst_n,valid_r,first_r,last_r,ar[15:0],br[15:0],mean_r,u0,u1,computed_valid,y,b);
  assign computed={{2016{1'b0}},(KIND==8?{16'b0,b}:y)};
 end else if(KIND==3)begin:residual
  wire [31:0] sum;wire [15:0] bf;
  fc_fp_add a({ar[15:0],16'b0},{br[15:0],16'b0},sum,,,);
  fc_fp32_to_bf16 cv(sum,bf,,,);
  assign computed={{2032{1'b0}},bf};assign computed_valid=valid_r;
 end else if(KIND==4 || KIND==5)begin:encoder
  wire [511:0] q;wire [127:0] bin;wire [63:0] sg,one;wire [15:0] e;wire iv;
  nr_pot_encoder #(.FRAC(KIND==4?7:23)) core(clk,rst_n,valid_r,ar[(KIND==4?1024:2048)-1:0],computed_valid,q,bin,sg,one,e,iv);
  assign computed={{1263{1'b0}},iv,e,one,sg,bin,q};
 end else if(KIND==6 || KIND==22)begin:restore
  wire [31:0] y;nr_bin_restore #(.FUSED(KIND==22)) core(ar[767:0],exp_r,u0,y);
  assign computed={{2016{1'b0}},y};assign computed_valid=valid_r;
 end else if(KIND==7)begin:swiglu
  wire [31:0] y;nr_swiglu_fp32 core(ar[31:0],br[31:0],y);
  assign computed={{2016{1'b0}},y};assign computed_valid=valid_r;
 end else if(KIND==10)begin:rms_apply
  wire [15:0] y;nr_rms_apply core(ar[15:0],br[15:0],u0,y);
  assign computed={{2032{1'b0}},y};assign computed_valid=valid_r;
 end else if(KIND>=11 && KIND<=13)begin:unary
  wire [31:0] y;nr_unary_lut #(.KIND(KIND-10)) core(ar[31:0],y);
  assign computed={{2016{1'b0}},y};assign computed_valid=valid_r;
 end else if(KIND==14)begin:compare_exchange
  wire [31:0] lo,hi;wire [15:0] il,ih;wire iv;
  nr_compare_exchange core(ar[31:0],br[31:0],ar[47:32],br[47:32],lo,hi,il,ih,iv);
  assign computed={{1951{1'b0}},iv,ih,il,hi,lo};assign computed_valid=valid_r;
 end else if(KIND==15)begin:prefix
  wire [447:0] dest;wire [6:0] count;nr_mask_prefix core(ar[63:0],dest,count);
  assign computed={{1593{1'b0}},count,dest};assign computed_valid=valid_r;
 end else if(KIND==16)begin:cdf
  wire [7:0] count;nr_cdf_counts core(clk,rst_n,valid_r,first_r,last_r,ar[32:0],u0,computed_valid,count);
  assign computed={{2040{1'b0}},count};
 end else if(KIND==17)begin:singleton
  wire [1:0] count;wire [8:0] index;
  nr_singleton_tree core(clk,rst_n,valid_r,ar[511:0],br[511:0],computed_valid,count,index);
  assign computed={{2037{1'b0}},count,index};
 end else if(KIND==20)begin:rope
  wire [31:0] y0,y1;nr_rope_pair core(ar[15:0],ar[31:16],u0,u1,y0,y1);
  assign computed={{1984{1'b0}},y1,y0};assign computed_valid=valid_r;
 end else if(KIND==21)begin:resize
  wire [15:0] bf;fc_fp32_to_bf16 core(ar[31:0],bf,,,);
  assign computed={{2032{1'b0}},bf};assign computed_valid=valid_r;
 end else begin:invalid_kind
  assign computed=0;assign computed_valid=0;
 end endgenerate
 always @(posedge clk)begin
  if(!rst_n)begin result<=0;out_valid<=0;end
  else begin out_valid<=computed_valid;if(computed_valid)result<=computed;end
 end
endmodule
