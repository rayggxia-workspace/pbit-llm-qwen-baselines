`timescale 1ns/1ps
// Balanced clipped-popcount/priority tree. Input bits are supplied by a separate
// source; no random generator, probability LUT, reseeding or source timing here.
// N must be a power of2. Registers every LEVELS_PER_STAGE logical tree levels.
module nr_singleton_tree #(parameter integer N=512,LEVELS_PER_STAGE=2)(
 input wire clk,rst_n,in_valid,
 input wire [N-1:0] bits_in,mask,
 output wire out_valid,output wire [1:0] cardinality,
 output wire [$clog2(N)-1:0] first_index
);
 localparam integer L=$clog2(N),STAGES=(L+LEVELS_PER_STAGE-1)/LEVELS_PER_STAGE;
 wire [1:0] count[0:L][0:N-1];wire [L-1:0] address[0:L][0:N-1];
 reg [STAGES-1:0] valid;
 genvar l,n;
 generate for(n=0;n<N;n=n+1)begin:leaf
  assign count[0][n]={1'b0,bits_in[n]&mask[n]};assign address[0][n]=n;
 end
 for(l=1;l<=L;l=l+1)begin:level
  for(n=0;n<(N>>l);n=n+1)begin:node
   wire [2:0] s=count[l-1][2*n]+{1'b0,count[l-1][2*n+1]};
   wire [1:0] clipped=s>1?2'd2:s[1:0];
   wire [L-1:0] chosen=count[l-1][2*n]!=0?address[l-1][2*n]:address[l-1][2*n+1];
   if(l%LEVELS_PER_STAGE==0 || l==L)begin:reg_boundary
    reg [1:0] c;reg [L-1:0] a;
    localparam integer VSTAGE=(l-1)/LEVELS_PER_STAGE;
    wire enable=(VSTAGE==0)?in_valid:valid[VSTAGE-1];
    always @(posedge clk)begin
     if(!rst_n)begin c<=0;a<=0;end
     else if(enable)begin c<=clipped;a<=chosen;end
    end
    assign count[l][n]=c;assign address[l][n]=a;
   end else begin:comb_boundary
    assign count[l][n]=clipped;assign address[l][n]=chosen;
   end
  end
 end endgenerate
 integer k;
 always @(posedge clk)begin
  if(!rst_n)valid<=0;
  else begin valid[0]<=in_valid;for(k=1;k<STAGES;k=k+1)valid[k]<=valid[k-1];end
 end
 assign cardinality=count[L][0];assign first_index=address[L][0];assign out_valid=valid[STAGES-1];
endmodule

// Inclusive parallel prefix for a compact-address write map; N power-of2.
module nr_mask_prefix #(parameter integer N=64)(
 input wire [N-1:0] mask,
 output wire [N*($clog2(N)+1)-1:0] destination,
 output wire [$clog2(N):0] count
);
 localparam integer L=$clog2(N),W=L+1;
 wire [W-1:0] scan[0:L][0:N-1];genvar l,i;
 generate for(i=0;i<N;i=i+1)begin:leaf
  assign scan[0][i]=mask[i];
  assign destination[i*W+:W]=scan[L][i]-mask[i];
 end
 for(l=1;l<=L;l=l+1)begin:level
  for(i=0;i<N;i=i+1)begin:node
   if(i>=(1<<(l-1)))assign scan[l][i]=scan[l-1][i]+scan[l-1][i-(1<<(l-1))];
   else assign scan[l][i]=scan[l-1][i];
  end
 end endgenerate
 assign count=scan[L][N-1];
endmodule

// Systematic inverse-CDF without RNG. Probability input Q0.32 INCLUDING1.
// offset is supplied externally, low(32-S_LOG2)bits are used; S=2^S_LOG2.
// One probability/edge; output count for that interval on the accepting edge.
// last closes the CDF at1, accounting for quantized-probability sum rounding.
module nr_cdf_counts #(parameter integer S_LOG2=7)(
 input wire clk,rst_n,in_valid,first,last,
 input wire [32:0] probability,input wire [31:0] offset,
 output reg out_valid,output reg [S_LOG2:0] multiplicity
);
 reg [32:0] cumulative;reg [S_LOG2:0] emitted;reg [31:0] offset_r;
 localparam integer STEP_LOG=32-S_LOG2;
 localparam [32:0] ONE=33'h100000000;
 reg [33:0] sum,diff;reg [32:0] next_cdf,off;reg [S_LOG2:0] next_emitted,old_emitted;
 always @* begin
  off={1'b0,(first?offset:offset_r)}&((33'd1<<STEP_LOG)-1'b1);
  sum={1'b0,(first?33'b0:cumulative)}+{1'b0,probability};
  next_cdf=(last||sum>=ONE)?ONE:sum[32:0];
  old_emitted=first?0:emitted;diff=0;next_emitted=0;
  if(next_cdf>off)begin
   diff={1'b0,next_cdf}-{1'b0,off}+(34'd1<<STEP_LOG)-1'b1;
   next_emitted=diff>>STEP_LOG;
  end
 end
 always @(posedge clk)begin
  if(!rst_n)begin cumulative<=0;emitted<=0;offset_r<=0;out_valid<=0;multiplicity<=0;end
  else begin
   out_valid<=in_valid;
   if(in_valid)begin
    cumulative<=next_cdf;emitted<=next_emitted;multiplicity<=next_emitted-old_emitted;
    if(first)offset_r<=offset;
   end
  end
 end
endmodule
