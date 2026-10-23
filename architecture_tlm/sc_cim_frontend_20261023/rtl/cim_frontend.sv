// Diagnostic complete frontend: SNG + explicit sample distribution + raw W8 AND.
// Do NOT add its complete power to Issue133 counters: those already include AND.
module cim_frontend #(parameter integer N=64,M=64,T=32,K=32,EXTERNAL_RNG=0,
 parameter integer OUT_PER_BRANCH=8)(
 input wire clk,rst_n,seed_valid, input wire [31:0] seed_data,
 output wire seed_ready,seed_error,
 input wire frame_start, output wire frame_ready,
 input wire [N*8-1:0] q8, input wire [N-1:0] one,
 input wire [N*M*8-1:0] weights,
 input wire ext_valid, input wire [7:0] ext_word, output wire ext_ready,
 output wire sample_valid,input wire sample_ready,
 output wire [N-1:0] sample_bits,output wire [7:0] threshold,
 output wire [N*M*8-1:0] products, output wire done);
 cim_sng #(.N(N),.T(T),.K(K),.EXTERNAL_RNG(EXTERNAL_RNG)) sng(
  .clk(clk),.rst_n(rst_n),.seed_valid(seed_valid),.seed_data(seed_data),
  .seed_ready(seed_ready),.seed_error(seed_error),.frame_start(frame_start),.frame_ready(frame_ready),
  .q8(q8),.one(one),.ext_valid(ext_valid),.ext_word(ext_word),.ext_ready(ext_ready),
  .sample_valid(sample_valid),.sample_ready(sample_ready),.sample_bits(sample_bits),.threshold(threshold),.done(done));
 cim_w8_gate #(.N(N),.M(M),.OUT_PER_BRANCH(OUT_PER_BRANCH)) gates(
  .bits(sample_bits),.weights(weights),.products(products));
endmodule
