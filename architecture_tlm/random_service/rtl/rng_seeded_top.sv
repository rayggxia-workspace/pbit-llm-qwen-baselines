// Core characterization top. Qualified seed bus -> packet -> warmup -> local service.
module rng_seeded_top #(
 parameter integer KIND=0,
 parameter integer LANES=(KIND==1 ? 64 : KIND==2 ? 20 : 1),
 parameter integer STATE_BITS=(KIND==2 ? 177 : 32),
 parameter [31:0] RESEED_CYCLES=32'd100000000
)(input wire clk, input wire rst_n,
 input wire word_valid, output wire word_ready, input wire [31:0] word_data,
 input wire qualified, output wire entropy_fault,
 input wire req_valid, output wire req_ready, input wire [LANES*9-1:0] thresholds,
 output wire rsp_valid, input wire rsp_ready,
 output wire [LANES*8-1:0] words, output wire [LANES-1:0] bits,
 input wire [1:0] command, output wire cmd_ready,
 output wire seed_req, output wire seed_error);
 wire sv,sr;
 wire [STATE_BITS-1:0] sd;
 rng_seed_ingress #(.STATE_BITS(STATE_BITS)) ingress(
 .clk(clk),.rst_n(rst_n),.seed_req(seed_req),.word_valid(word_valid),
 .word_ready(word_ready),.word_data(word_data),.qualified(qualified),.fault(entropy_fault),
 .seed_valid(sv),.seed_ready(sr),.seed_data(sd));
 rng_endpoint #(.KIND(KIND),.RESEED_CYCLES(RESEED_CYCLES)) endpoint(
 .clk(clk),.rst_n(rst_n),.req_valid(req_valid),.req_ready(req_ready),.thresholds(thresholds),
 .rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.words(words),.bits(bits),
 .seed_req(seed_req),.seed_valid(sv),.seed_ready(sr),.seed_data(sd),.seed_error(seed_error),
 .command(command),.cmd_ready(cmd_ready),.seeded(),.epoch_locked(),.epoch(),.age(),
 .warm_left(),.event_update(),.event_warmup(),.event_seed(),.event_consume(),.debug_state());
endmodule
