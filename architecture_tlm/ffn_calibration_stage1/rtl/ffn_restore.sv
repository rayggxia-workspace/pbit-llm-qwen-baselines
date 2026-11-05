`timescale 1ns/1ps
// Issue193: integer restore contract, not a Qwen coefficient compiler.
// Bucket zero is the least-significant packed count.
// S = sum_b counts[b] * 2**(2*(BINS-1-b));
// out_delta = signed ties-to-even round(S * unsigned(coeff) / 2**rshift).
// Synchronous active-low reset. Global elastic stall: all pipeline state
// freezes while a valid output is blocked. Input metadata travels with data.
// With out_ready=1: II=1; accept-to-earliest-output-HANDSHAKE latency is
// PIPE_STAGES clocks: 8 for BINS=4, 10 for BINS=7 (CW=20 or 21).
// out_valid presents after the PIPE_STAGES-th registering edge, i.e.
// PIPE_STAGES-1 periods after the input acceptance edge. No EDA timing claim.
module ffn_restore #(
    parameter integer BINS = 4,
    parameter integer CW = 20
)(
    input wire clk,
    input wire rst_n,
    input wire in_valid,
    output wire in_ready,
    input wire [BINS*CW-1:0] counts,
    input wire [15:0] coeff,
    input wire [5:0] rshift,
    output wire out_valid,
    input wire out_ready,
    output wire signed [63:0] out_delta
);
    // Geometric shifts total < 4/3 * 2**max_shift. This signed width
    // covers every CW-bit signed count, including its most-negative value.
    localparam integer SW = CW + 2*(BINS-1) + 1;
    localparam integer TREE_LEVELS = $clog2(BINS);
    localparam integer TREE_LEAVES = 1 << TREE_LEVELS;
    localparam integer CHUNKS = (SW+15)/16;
    localparam integer PRODUCT_LEVELS = $clog2(CHUNKS);
    localparam integer PRODUCT_LEAVES = 1 << PRODUCT_LEVELS;
    localparam integer PW = SW + 16;
    localparam integer ABS_STAGE = TREE_LEVELS + 1;
    localparam integer MUL_STAGE = ABS_STAGE + 1;
    localparam integer PRODUCT_STAGE = MUL_STAGE + PRODUCT_LEVELS;
    localparam integer ROUND_STAGE = PRODUCT_STAGE + 1;
    localparam integer SIGN_STAGE = ROUND_STAGE + 1;
    localparam integer PIPE_STAGES = SIGN_STAGE + 1;

    reg [PIPE_STAGES-1:0] valid_pipe;
    reg [15:0] coeff_pipe [0:PIPE_STAGES-1];
    reg [5:0] shift_pipe [0:PIPE_STAGES-1];
    reg negate_pipe [0:PIPE_STAGES-1];
    reg signed [SW-1:0] tree [0:TREE_LEVELS][0:TREE_LEAVES-1];
    reg [SW-1:0] magnitude;
    reg [PW-1:0] products [0:PRODUCT_LEVELS][0:PRODUCT_LEAVES-1];
    reg [PW:0] rounded_magnitude;
    reg signed [63:0] result;
    wire advance = !valid_pipe[PIPE_STAGES-1] || out_ready;
    assign in_ready = rst_n && advance;
    assign out_valid = rst_n && valid_pipe[PIPE_STAGES-1];
    assign out_delta = result;

    integer s;
    always @(posedge clk) begin
        if (!rst_n) begin
            valid_pipe <= 0;
            for (s=0;s<PIPE_STAGES;s=s+1) begin
                coeff_pipe[s] <= 0;
                shift_pipe[s] <= 0;
                negate_pipe[s] <= 0;
            end
        end else if (advance) begin
            valid_pipe[0] <= in_valid;
            coeff_pipe[0] <= coeff;
            shift_pipe[0] <= rshift;
            for (s=1;s<PIPE_STAGES;s=s+1) begin
                valid_pipe[s] <= valid_pipe[s-1];
                coeff_pipe[s] <= coeff_pipe[s-1];
                shift_pipe[s] <= shift_pipe[s-1];
            end
            negate_pipe[ABS_STAGE] <= tree[TREE_LEVELS][0][SW-1];
            for (s=ABS_STAGE+1;s<PIPE_STAGES;s=s+1)
                negate_pipe[s] <= negate_pipe[s-1];
        end
    end

    genvar b,l,j,c;
    generate
        for (b=0;b<TREE_LEAVES;b=b+1) begin: align_bucket
            if (b<BINS) begin: used
                wire signed [CW-1:0] value = $signed(counts[b*CW+:CW]);
                wire signed [SW-1:0] extended = {{(SW-CW){value[CW-1]}},value};
                always @(posedge clk) begin
                    if (!rst_n) tree[0][b] <= 0;
                    else if (advance) tree[0][b] <= extended <<< (2*(BINS-1-b));
                end
            end else begin: padding
                always @(posedge clk) begin
                    if (!rst_n) tree[0][b] <= 0;
                    else if (advance) tree[0][b] <= 0;
                end
            end
        end
        for (l=1;l<=TREE_LEVELS;l=l+1) begin: balanced_bucket_tree
            for (j=0;j<(TREE_LEAVES>>l);j=j+1) begin: node
                always @(posedge clk) begin
                    if (!rst_n) tree[l][j] <= 0;
                    else if (advance) tree[l][j] <= tree[l-1][2*j] + tree[l-1][2*j+1];
                end
            end
        end
        for (c=0;c<PRODUCT_LEAVES;c=c+1) begin: chunk_multiplier
            if (c<CHUNKS) begin: used
                // Each multiplier is exactly unsigned 16 x 16.
                wire [15:0] chunk = magnitude >> (16*c);
                wire [31:0] partial = chunk * coeff_pipe[ABS_STAGE];
                always @(posedge clk) begin
                    if (!rst_n) products[0][c] <= 0;
                    else if (advance) products[0][c] <= {{(PW-32){1'b0}},partial} << (16*c);
                end
            end else begin: padding
                always @(posedge clk) begin
                    if (!rst_n) products[0][c] <= 0;
                    else if (advance) products[0][c] <= 0;
                end
            end
        end
        for (l=1;l<=PRODUCT_LEVELS;l=l+1) begin: balanced_product_tree
            for (j=0;j<(PRODUCT_LEAVES>>l);j=j+1) begin: node
                always @(posedge clk) begin
                    if (!rst_n) products[l][j] <= 0;
                    else if (advance) products[l][j] <= products[l-1][2*j] + products[l-1][2*j+1];
                end
            end
        end
    endgenerate

    always @(posedge clk) begin
        if (!rst_n) magnitude <= 0;
        else if (advance)
            magnitude <= tree[TREE_LEVELS][0][SW-1] ?
                         -tree[TREE_LEVELS][0] : tree[TREE_LEVELS][0];
    end

    reg [PW-1:0] quotient, remainder, halfway, remainder_mask;
    reg round_up;
    always @* begin
        quotient = 0;
        remainder = 0;
        halfway = 0;
        remainder_mask = 0;
        round_up = 0;
        if (shift_pipe[PRODUCT_STAGE] == 0) begin
            quotient = products[PRODUCT_LEVELS][0];
        end else if (shift_pipe[PRODUCT_STAGE] <= PW) begin
            quotient = products[PRODUCT_LEVELS][0] >> shift_pipe[PRODUCT_STAGE];
            remainder_mask = {PW{1'b1}} >> (PW-shift_pipe[PRODUCT_STAGE]);
            remainder = products[PRODUCT_LEVELS][0] & remainder_mask;
            halfway = {{(PW-1){1'b0}},1'b1} << (shift_pipe[PRODUCT_STAGE]-1);
            round_up = (remainder > halfway) || ((remainder == halfway) && quotient[0]);
        end
        // shift > PW: magnitude is strictly below half, so rounded value=0.
    end
    always @(posedge clk) begin
        if (!rst_n) rounded_magnitude <= 0;
        else if (advance) rounded_magnitude <= {1'b0,quotient} + round_up;
    end
    wire signed [63:0] extended_result = $signed({{(63-PW){1'b0}},rounded_magnitude});
    always @(posedge clk) begin
        if (!rst_n) result <= 0;
        else if (advance)
            result <= negate_pipe[ROUND_STAGE] ? -extended_result : extended_result;
    end

    // synthesis translate_off
    initial begin
        if ((BINS!=4 && BINS!=7) || (CW!=20 && CW!=21) || PW>=63)
            $fatal(1,"unsupported restore geometry");
    end
    // synthesis translate_on
endmodule
