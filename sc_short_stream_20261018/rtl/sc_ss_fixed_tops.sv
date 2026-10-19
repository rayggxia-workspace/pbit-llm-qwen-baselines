`timescale 1ns/1ps
// Fixed synthesis tops: identical ACC_W=27, N=64, A8/W8.
// _ext excludes the source; _rng includes one shared source per group.

module sc_ss_iid4096_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [12:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(0),.LOG_T(12),.INTERNAL_RNG(1),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_iid4096_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [12:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(0),.LOG_T(12),.INTERNAL_RNG(1)) dut(.*);
endmodule

module sc_ss_iid4096_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [12:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(0),.LOG_T(12),.INTERNAL_RNG(0),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_iid4096_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [12:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(0),.LOG_T(12),.INTERNAL_RNG(0)) dut(.*);
endmodule

module sc_ss_iid128_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(0),.LOG_T(7),.INTERNAL_RNG(1),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_iid128_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(0),.LOG_T(7),.INTERNAL_RNG(1)) dut(.*);
endmodule

module sc_ss_iid128_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(0),.LOG_T(7),.INTERNAL_RNG(0),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_iid128_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(0),.LOG_T(7),.INTERNAL_RNG(0)) dut(.*);
endmodule

module sc_ss_strat64_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [6:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(1),.LOG_T(6),.INTERNAL_RNG(1),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_strat64_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [6:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(1),.LOG_T(6),.INTERNAL_RNG(1)) dut(.*);
endmodule

module sc_ss_strat64_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [6:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(1),.LOG_T(6),.INTERNAL_RNG(0),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_strat64_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [6:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(1),.LOG_T(6),.INTERNAL_RNG(0)) dut(.*);
endmodule

module sc_ss_strat128_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(1),.LOG_T(7),.INTERNAL_RNG(1),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_strat128_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(1),.LOG_T(7),.INTERNAL_RNG(1)) dut(.*);
endmodule

module sc_ss_strat128_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(1),.LOG_T(7),.INTERNAL_RNG(0),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_strat128_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(1),.LOG_T(7),.INTERNAL_RNG(0)) dut(.*);
endmodule

module sc_ss_enum256_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [8:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(2),.LOG_T(8),.INTERNAL_RNG(1),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_enum256_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [8:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(2),.LOG_T(8),.INTERNAL_RNG(1)) dut(.*);
endmodule

module sc_ss_enum256_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,weights,
    input wire [63:0] input_sign,
    output wire busy,done,accept,rng_step,
    output wire [8:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact #(.MODE(2),.LOG_T(8),.INTERNAL_RNG(0),.ACC_W(27)) dut(.*);
endmodule

module sc_ss_sampler_enum256_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [511:0] probability,
    output wire busy,done,accept,rng_step,
    output wire [8:0] sample_count,
    output wire [7:0] threshold,
    output wire [63:0] bits_out,
    output wire [31:0] rng_state
);
    sc_ss_sampler #(.MODE(2),.LOG_T(8),.INTERNAL_RNG(0)) dut(.*);
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_iid4096_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [12:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(0),.LOG_T(12),.INTERNAL_RNG(1)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_iid4096_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [12:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(0),.LOG_T(12),.INTERNAL_RNG(0)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_iid128_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(0),.LOG_T(7),.INTERNAL_RNG(1)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_iid128_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(0),.LOG_T(7),.INTERNAL_RNG(0)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_strat64_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [6:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(1),.LOG_T(6),.INTERNAL_RNG(1)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_strat64_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [6:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(1),.LOG_T(6),.INTERNAL_RNG(0)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_strat128_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(1),.LOG_T(7),.INTERNAL_RNG(1)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_strat128_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [7:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(1),.LOG_T(7),.INTERNAL_RNG(0)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_enum256_rng(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [8:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(2),.LOG_T(8),.INTERNAL_RNG(1)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Threshold + frame control only; the N=1 comparator is unused and pruned.
module sc_ss_threshold_enum256_ext(
    input wire clk,rst_n,start,sample_valid,seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    output wire busy,done,accept,rng_step,
    output wire [8:0] sample_count,
    output wire [7:0] threshold,
    output wire [31:0] rng_state
);
    wire unused_bit;
    sc_ss_sampler #(.N(1),.MODE(2),.LOG_T(8),.INTERNAL_RNG(0)) dut(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(8'b0),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(unused_bit),.rng_state(rng_state));
endmodule

// Per-output-column compute only; no PRNG, frame counter, or comparator bank.
module sc_ss_body_n64_acc27(
    input wire clk,rst_n,begin_frame,accept,
    input wire [63:0] bits_in,input_sign,
    input wire [511:0] weights,
    output wire signed [26:0] raw_sum
);
    sc_ss_exact_body #(.N(64),.LOG_T(12),.ACC_W(27)) dut(.*);
endmodule
