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
