`timescale 1ns/1ps
// Balanced upsweep/downsweep exclusive scan, O(N) adders, power-of-two N.
// Structure follows the scan building block, not a copied third-party RTL.
module ac_scan #(parameter integer N=32,W=10)(
 input wire [N*W-1:0] values,
 output wire [N*W-1:0] prefix,
 output wire [W-1:0] total
);
 wire [W-1:0] sum[1:2*N-1],offset[1:2*N-1];
 assign offset[1]=0;assign total=sum[1];
 genvar i;
 generate for(i=0;i<N;i=i+1)begin:leaves
  assign sum[N+i]=values[i*W+:W];assign prefix[i*W+:W]=offset[N+i];
 end
 for(i=1;i<N;i=i+1)begin:branches
  assign sum[i]=sum[2*i]+sum[2*i+1];
  assign offset[2*i]=offset[i];assign offset[2*i+1]=offset[i]+sum[2*i];
 end endgenerate
endmodule
