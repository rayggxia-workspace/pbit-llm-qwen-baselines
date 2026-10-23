// Balanced exact integer reduction. PAD leaves are zero, not serial additions.
module sc_sum_tree #(parameter integer N=64, W=15)(
 input wire [N*W-1:0] terms, output wire signed [W-1:0] total);
 localparam integer P=2**$clog2(N);
 wire signed [W-1:0] node [1:2*P-1];
 genvar i;
 generate
  for(i=0;i<P;i=i+1) begin: leaf
   if(i<N) assign node[P+i]=$signed(terms[i*W+:W]);
   else assign node[P+i]={W{1'b0}};
  end
  for(i=1;i<P;i=i+1) begin: add
   assign node[i]=node[2*i]+node[2*i+1];
  end
 endgenerate
 assign total=node[1];
endmodule
