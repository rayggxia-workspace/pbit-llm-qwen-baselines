`timescale 1ns/1ps
// Exact fixed-W8, binary-sample, signed bucket counter.
// Boundary: no PRNG, comparator, coefficient restore, or weight storage.
// All weights, x_sign and bin_id must remain stable from frame acceptance
// through output acceptance. w_mag7 cannot encode -128 (range is 0..127).
// Weight lane (m,n) uses (m*N+n)*7; bin_id[n] always occupies THREE bits.
// Output lane (m,b) occupies out_counts[(m*BINS+b)*CW +: CW], signed.
// Synchronous active-low reset. N must be a power of two, N >= 2.
// N=64 has six registered pairwise reduction levels, with no serial sum loop.
// An accepted sample at edge c reaches the accumulator at edge c+$clog2(N).
// The T-th accepted sample produces out_valid at that same accumulator edge.
module ffn_counter #(
    parameter integer N = 64,
    parameter integer M = 1,
    parameter integer BINS = 4,
    parameter integer T = 64,
    parameter integer CW = 1 + $clog2(N * 127 * T + 1)
) (
    input  wire                         clk,
    input  wire                         rst_n,
    input  wire                         frame_valid,
    output wire                         frame_ready,
    input  wire [N*M*7-1:0]             w_mag7,
    input  wire [N*M-1:0]               w_sign,
    input  wire [N-1:0]                 x_sign,
    input  wire [N*3-1:0]               bin_id,
    input  wire [N-1:0]                 sample_bits,
    input  wire                         sample_valid,
    output wire                         sample_ready,
    output wire                         out_valid,
    input  wire                         out_ready,
    output wire [M*BINS*CW-1:0]         out_counts
);
    localparam integer LEVELS = $clog2(N);
    localparam integer TREE_W = 8 + LEVELS;
    localparam integer ACCEPT_W = (T > 1) ? $clog2(T) : 1;
    localparam [1:0] IDLE = 2'd0, RUN = 2'd1, DRAIN = 2'd2, OUTPUT = 2'd3;

    reg [1:0] state;
    reg [ACCEPT_W-1:0] accepted;
    reg [LEVELS-1:0] pipe_valid;
    reg [LEVELS-1:0] pipe_last;
    reg signed [CW-1:0] counts [0:M*BINS-1];
    wire frame_fire = frame_valid && frame_ready;
    wire sample_fire = sample_valid && sample_ready;
    wire sample_last = sample_fire && (accepted == T-1);

    assign frame_ready = (state == IDLE);
    assign sample_ready = (state == RUN);
    assign out_valid = (state == OUTPUT);

    // Magnitude AND, then sign XOR; routing by a 3-bit bucket index.
    // BINS<8: an out-of-range bin routes no contribution; caller supplies
    // valid bins 0..BINS-1. A zero magnitude has value zero for either sign.
    wire signed [7:0] leaf [0:M*BINS*N-1];
    genvar m, b, n, level, channel, node;
    generate
        for (m = 0; m < M; m = m+1) begin : g_m
            for (b = 0; b < BINS; b = b+1) begin : g_b
                for (n = 0; n < N; n = n+1) begin : g_n
                    wire [6:0] mag = w_mag7[(m*N+n)*7 +: 7];
                    wire negative = w_sign[m*N+n] ^ x_sign[n];
                    wire selected = sample_bits[n] && (bin_id[n*3 +: 3] == b);
                    assign leaf[(m*BINS+b)*N+n] = !selected ? 8'sd0 :
                        (negative ? -$signed({1'b0, mag}) : $signed({1'b0, mag}));
                end
            end
        end

        // Each register is driven by exactly one two-input signed adder.
        // Width grows by one bit at each level: 9,10,11,12,13,14 for N64.
        for (level = 0; level < LEVELS; level = level+1) begin : g_tree
            localparam integer NODES = N >> (level+1);
            localparam integer SW = 9 + level;
            reg signed [SW-1:0] partial [0:M*BINS*NODES-1];
            for (channel = 0; channel < M*BINS; channel = channel+1) begin : g_channel
                for (node = 0; node < NODES; node = node+1) begin : g_node
                    if (level == 0) begin : g_leaf_pair
                        wire signed [7:0] a = leaf[channel*N+2*node];
                        wire signed [7:0] z = leaf[channel*N+2*node+1];
                        always @(posedge clk) begin
                            if (!rst_n)
                                partial[channel*NODES+node] <= {SW{1'b0}};
                            else if (sample_fire)
                                partial[channel*NODES+node] <=
                                    $signed({a[7], a}) + $signed({z[7], z});
                        end
                    end else begin : g_registered_pair
                        wire signed [SW-2:0] a = g_tree[level-1].partial[channel*(2*NODES)+2*node];
                        wire signed [SW-2:0] z = g_tree[level-1].partial[channel*(2*NODES)+2*node+1];
                        always @(posedge clk) begin
                            if (!rst_n)
                                partial[channel*NODES+node] <= {SW{1'b0}};
                            else if (pipe_valid[level-1])
                                partial[channel*NODES+node] <=
                                    $signed({a[SW-2], a}) + $signed({z[SW-2], z});
                        end
                    end
                end
            end
        end

        for (channel = 0; channel < M*BINS; channel = channel+1) begin : g_accum
            wire signed [TREE_W-1:0] reduced = g_tree[LEVELS-1].partial[channel];
            wire signed [CW-1:0] extended = {{(CW-TREE_W){reduced[TREE_W-1]}}, reduced};
            always @(posedge clk) begin
                if (!rst_n)
                    counts[channel] <= {CW{1'b0}};
                else if (frame_fire)
                    counts[channel] <= {CW{1'b0}};
                else if (pipe_valid[LEVELS-1])
                    counts[channel] <= counts[channel] + extended;
            end
            // Reuse the accumulator as output holding storage; no duplicate bank.
            assign out_counts[channel*CW +: CW] = counts[channel];
        end
    endgenerate

    integer p;
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE;
            accepted <= {ACCEPT_W{1'b0}};
            pipe_valid <= {LEVELS{1'b0}};
            pipe_last <= {LEVELS{1'b0}};
        end else begin
            pipe_valid[0] <= sample_fire;
            pipe_last[0] <= sample_last;
            for (p = 1; p < LEVELS; p = p+1) begin
                pipe_valid[p] <= pipe_valid[p-1];
                pipe_last[p] <= pipe_last[p-1];
            end
            if (frame_fire) begin
                state <= RUN;
                accepted <= {ACCEPT_W{1'b0}};
                pipe_valid <= {LEVELS{1'b0}};
                pipe_last <= {LEVELS{1'b0}};
            end
            if (sample_fire) begin
                if (sample_last)
                    state <= DRAIN;
                else
                    accepted <= accepted + 1'b1;
            end
            if (pipe_valid[LEVELS-1] && pipe_last[LEVELS-1])
                state <= OUTPUT;
            if (out_valid && out_ready)
                state <= IDLE;
        end
    end

`ifndef SYNTHESIS
    initial begin
        if (N < 2 || (N & (N-1)) != 0 || M < 1 || BINS < 1 || BINS > 7 || T < 1)
            $fatal(1, "ffn_counter invalid parameters");
        if (CW < 1 + $clog2(N * 127 * T + 1))
            $fatal(1, "ffn_counter CW cannot represent the exact worst-case count");
    end
`endif
endmodule
