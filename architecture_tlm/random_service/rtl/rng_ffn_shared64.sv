// Optional complete shared-input frontend. One random word, 64 q/256 comparisons.
// Threshold registers are EXPLICIT here; do not add them again in consumer area.
module rng_ffn_shared64 #(parameter [31:0] RESEED_CYCLES=32'd100000000)(
 input wire clk, input wire rst_n,
 input wire word_valid, output wire word_ready, input wire [31:0] word_data,
 input wire qualified, output wire entropy_fault,
 input wire req_valid, output wire req_ready, input wire [575:0] thresholds,
 output wire rsp_valid, input wire rsp_ready, output wire [63:0] mask,
 input wire [1:0] command, output wire cmd_ready,
 output wire seed_req, output wire seed_error);
 reg [575:0] held_q;
 wire [7:0] random_word;
 wire unused_bit;
 rng_seeded_top #(.KIND(0),.RESEED_CYCLES(RESEED_CYCLES)) source(
 .clk(clk),.rst_n(rst_n),.word_valid(word_valid),.word_ready(word_ready),.word_data(word_data),
 .qualified(qualified),.entropy_fault(entropy_fault),.req_valid(req_valid),.req_ready(req_ready),
 .thresholds(9'd128),.rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.words(random_word),.bits(unused_bit),
 .command(command),.cmd_ready(cmd_ready),.seed_req(seed_req),.seed_error(seed_error));
 always @(posedge clk or negedge rst_n)
   if (!rst_n) held_q<=0;
   else if (req_valid && req_ready) held_q<=thresholds;
 genvar i;
 generate for(i=0;i<64;i=i+1) begin: compare
   assign mask[i]=({1'b0,random_word}<held_q[i*9 +: 9]);
 end endgenerate
endmodule

