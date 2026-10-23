// Raw two's-complement W8 gating, before signed/bin reduction. No accumulators.
// weights are stable local SRAM-side pins; there is NO DFF copy of the matrix.
module cim_w8_gate #(parameter integer N=64,M=64,OUT_PER_BRANCH=8)(
 input wire [N-1:0] bits,
 input wire [N*M*8-1:0] weights,
 output wire [N*M*8-1:0] products);
 localparam integer BRANCHES=(M+OUT_PER_BRANCH-1)/OUT_PER_BRANCH;
 wire [BRANCHES*N-1:0] local_bits;
 cim_fanout #(.WIDTH(N),.COPIES(BRANCHES)) sample_drive(.din(bits),.dout(local_bits));
 genvar o,i;
 generate for(o=0;o<M;o=o+1) begin: output_lane
  for(i=0;i<N;i=i+1) begin: input_lane
   assign products[(o*N+i)*8+:8]=weights[(o*N+i)*8+:8]&{8{local_bits[(o/OUT_PER_BRANCH)*N+i]}};
  end
 end endgenerate
endmodule

// Digital-only probe for one stable SRAM Q -> one or several local consumers.
// This is NOT a bitcell, wordline, bitline or sense-amplifier model.
module cim_sram_q_probe #(parameter integer WIDTH=64,COPIES=1)(
 input wire [WIDTH-1:0] sram_q,
 output wire [WIDTH*COPIES-1:0] local_q);
 cim_fanout #(.WIDTH(WIDTH),.COPIES(COPIES)) q_drive(.din(sram_q),.dout(local_q));
endmodule
