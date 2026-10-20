`timescale 1ns/1ps
// One threshold per N-lane group (N<=64). All probabilities are q/256.
// MODE: 0 IID-like PRNG, 1 randomized ordered strata, 2 full enumeration.
// INTERNAL_RNG=0 accepts ext_random[7:0]; its generation cost is external.
module sc_ss_sampler #(
    parameter integer N=64, MODE=1, LOG_T=7, INTERNAL_RNG=1
)(
    input wire clk, rst_n, start, sample_valid,
    input wire seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [N*8-1:0] probability,
    output reg busy, done,
    output reg [LOG_T:0] sample_count,
    output wire accept, rng_step,
    output wire [7:0] threshold,
    output wire [N-1:0] bits_out,
    output wire [31:0] rng_state
);
    localparam integer SAMPLES=1<<LOG_T;
    localparam integer NEEDS_RANDOM=(MODE!=2)&&!(MODE==1&&LOG_T==8);
    wire begin_frame=start&&!busy&&!seed_load;
    assign accept=busy&&sample_valid;
    assign rng_step=accept&&NEEDS_RANDOM;
    // This is BOTH the frame counter and the source of stratum upper bits.
    // There is no independent stratum/phase counter.
    always @(posedge clk) begin
        if(!rst_n) begin busy<=0;done<=0;sample_count<=0;end
        else begin
            done<=0;
            if(begin_frame) begin busy<=1;sample_count<=0;end
            else if(accept) begin
                sample_count<=sample_count+1'b1;
                if(sample_count==SAMPLES-1) begin busy<=0;done<=1;end
            end
        end
    end
    function automatic [31:0] xorshift32(input [31:0] value);
        reg [31:0] a;
        begin
            a=value^(value<<13);
            a=a^(a>>17);
            xorshift32=a^(a<<5);
        end
    endfunction
    wire [7:0] random_byte;
    generate
        if(INTERNAL_RNG && NEEDS_RANDOM) begin:internal_rng
            reg [31:0] state;
            always @(posedge clk) begin
                if(!rst_n) state<=32'h1;
                else if(seed_load&&!busy) state<=seed_in==0?32'h1:seed_in;
                else if(rng_step) state<=xorshift32(state);
            end
            assign rng_state=state;
            assign random_byte=state[7:0];
        end else begin:external_rng
            assign rng_state=32'b0;
            assign random_byte=NEEDS_RANDOM?ext_random:8'b0;
        end
        if(MODE==0) begin:iid
            assign threshold=random_byte;
        end else if(MODE==1) begin:stratified
            localparam integer JITTER_BITS=8-LOG_T;
            // Constant shifts/masks are wiring. Only JITTER_BITS random bits
            // affect a comparison (1 for T128, 2 for T64).
            assign threshold=(sample_count<<JITTER_BITS)
                             |(random_byte&((1<<JITTER_BITS)-1));
        end else begin:enumerate_all
            assign threshold=sample_count;
        end
    endgenerate
    genvar i;
    generate for(i=0;i<N;i=i+1) begin:compare_lane
        assign bits_out[i]=probability[8*i+:8]>threshold;
    end endgenerate
    // synthesis translate_off
    initial begin
        if(N<1 || N>64 || (N&(N-1))!=0) $fatal(1,"N must be a power of two <=64");
        if(MODE<0 || MODE>2 || LOG_T<1 || LOG_T>12) $fatal(1,"Invalid sampler mode/length");
        if(MODE==1 && LOG_T>8) $fatal(1,"Stratification must divide 256");
        if(MODE==2 && LOG_T!=8) $fatal(1,"Enumeration requires exactly 256 samples");
        if(INTERNAL_RNG!=0 && INTERNAL_RNG!=1) $fatal(1,"Invalid INTERNAL_RNG");
    end
    // synthesis translate_on
endmodule
