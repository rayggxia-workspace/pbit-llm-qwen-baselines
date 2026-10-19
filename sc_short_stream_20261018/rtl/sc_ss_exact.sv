`timescale 1ns/1ps
// Exact fixed signed W8 weighted sum for supplied binary input samples.
// G1 spatial reduction and B1 time accumulation: no OR collision/cache.
// Weight/probability/sign buses MUST remain stable for an entire frame.
// No weight/probability register bank is instantiated by this module.
module sc_ss_exact #(
    parameter integer N=64, MODE=1, LOG_T=7, INTERNAL_RNG=1,
    parameter integer ACC_W=27,
    parameter integer PART_W=8+$clog2(N)+1
)(
    input wire clk, rst_n, start, sample_valid, seed_load,
    input wire [31:0] seed_in,
    input wire [7:0] ext_random,
    input wire [N*8-1:0] probability, weights,
    input wire [N-1:0] input_sign,
    output wire busy, done, accept, rng_step,
    output wire [LOG_T:0] sample_count,
    output wire [7:0] threshold,
    output wire [N-1:0] bits_out,
    output wire [31:0] rng_state,
    output wire signed [ACC_W-1:0] raw_sum
);
    wire begin_frame=start&&!busy&&!seed_load;
    sc_ss_sampler #(.N(N),.MODE(MODE),.LOG_T(LOG_T),.INTERNAL_RNG(INTERNAL_RNG)) u_sampler(
        .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
        .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
        .probability(probability),.busy(busy),.done(done),.sample_count(sample_count),
        .accept(accept),.rng_step(rng_step),.threshold(threshold),
        .bits_out(bits_out),.rng_state(rng_state)
    );
    sc_ss_exact_body #(.N(N),.LOG_T(LOG_T),.ACC_W(ACC_W),.PART_W(PART_W)) u_body(
        .clk(clk),.rst_n(rst_n),.begin_frame(begin_frame),.accept(accept),
        .bits_in(bits_out),.input_sign(input_sign),.weights(weights),.raw_sum(raw_sum)
    );
endmodule

// Arithmetic-only column. Share one sampler/comparator group across columns.
module sc_ss_exact_body #(
    parameter integer N=64, LOG_T=12, ACC_W=27,
    parameter integer PART_W=8+$clog2(N)+1
)(
    input wire clk,rst_n,begin_frame,accept,
    input wire [N-1:0] bits_in,input_sign,
    input wire [N*8-1:0] weights,
    output reg signed [ACC_W-1:0] raw_sum
);
    wire [7:0] weight_mag[0:N-1];
    wire [N-1:0] negative;
    genvar k,b,n;
    generate for(k=0;k<N;k=k+1) begin:weight_decode
        wire [7:0] value=weights[8*k+:8];
        // Unsigned 8-bit magnitude retains abs(-128)=128.
        assign weight_mag[k]=value[7]?(~value+8'd1):value;
        assign negative[k]=value[7]^input_sign[k];
    end endgenerate
    localparam integer COUNT_W=$clog2(N+1);
    wire signed [PART_W-1:0] weighted_tree[1:15];
    generate
        for(b=0;b<8;b=b+1) begin:plane
            wire [N-1:0] pos,neg;
            for(k=0;k<N;k=k+1) begin:lane
                wire hit=accept&&bits_in[k]&&weight_mag[k][b];
                assign pos[k]=hit&&!negative[k];
                assign neg[k]=hit&&negative[k];
            end
            wire [COUNT_W-1:0] pc,nc;
            sc_ss_popcount #(.N(N)) u_pos(.bits_in(pos),.count(pc));
            sc_ss_popcount #(.N(N)) u_neg(.bits_in(neg),.count(nc));
            wire signed [PART_W-1:0] pe={{(PART_W-COUNT_W){1'b0}},pc};
            wire signed [PART_W-1:0] ne={{(PART_W-COUNT_W){1'b0}},nc};
            assign weighted_tree[8+b]=(pe-ne)<<<b;
        end
        for(n=1;n<8;n=n+1) begin:plane_reduce
            assign weighted_tree[n]=weighted_tree[2*n]+weighted_tree[2*n+1];
        end
    endgenerate
    wire signed [ACC_W-1:0] partial_ext={{(ACC_W-PART_W){weighted_tree[1][PART_W-1]}},weighted_tree[1]};
    always @(posedge clk) begin
        if(!rst_n) raw_sum<=0;
        else if(begin_frame) raw_sum<=0;
        else if(accept) raw_sum<=raw_sum+partial_ext;
    end
    // No explicit gated clock: register enable does not prove clock-tree savings.
    // synthesis translate_off
    initial begin
        if(N<1 || N>64 || (N&(N-1))!=0) $fatal(1,"Invalid body N");
        if(PART_W<8+$clog2(N)+1) $fatal(1,"Partial sum width too small");
        if(LOG_T<1 || LOG_T>12 || ACC_W<PART_W+LOG_T) $fatal(1,"Accumulator can overflow worst-case frame");
    end
    // synthesis translate_on
endmodule

// Same balanced exact popcount topology as historical sc_go_popcount.
module sc_ss_popcount #(
    parameter integer N=64, OUT_W=$clog2(N+1)
)(input wire [N-1:0] bits_in, output wire [OUT_W-1:0] count);
    localparam integer LEVELS=$clog2(N);
    genvar l,k;
    generate
        for(l=0;l<=LEVELS;l=l+1) begin:level
            wire [l:0] value[0:(N>>l)-1];
            for(k=0;k<(N>>l);k=k+1) begin:node
                if(l==0) assign value[k]=bits_in[k];
                else assign value[k]={1'b0,level[l-1].value[2*k]}+{1'b0,level[l-1].value[2*k+1]};
            end
        end
    endgenerate
    assign count=level[LEVELS].value[0];
endmodule
