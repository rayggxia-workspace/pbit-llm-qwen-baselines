`timescale 1ns/1ps
// Signed64 saturating accumulation with a one-deep output/state register.
// Accept exactly on in_valid && in_ready. clear starts a new sum at delta,
// and clears sticky overflow. Otherwise: saturate(state+delta).
// out_overflow reports this transaction; out_sticky reports the current sum's
// cumulative overflow status. Synchronous active-low reset drops valid/state.
// II=1 and feedback distance=1 require this 65-bit add/detect/select path to
// meet the target clock; functional RTL is not an STA claim. Earliest output
// handshake is one clock after acceptance. Output stays fixed while blocked.
module ffn_accumulator(
    input wire clk,
    input wire rst_n,
    input wire in_valid,
    output wire in_ready,
    input wire signed [63:0] in_delta,
    input wire clear,
    output wire out_valid,
    input wire out_ready,
    output wire signed [63:0] out_sum,
    output wire out_overflow,
    output wire out_sticky
);
    reg full;
    reg signed [63:0] state;
    reg overflow_flag, sticky;
    wire can_accept = !full || out_ready;
    wire accept = in_valid && in_ready;
    wire signed [64:0] extended_sum =
        $signed({state[63],state}) + $signed({in_delta[63],in_delta});
    wire add_overflow = extended_sum[64] != extended_sum[63];
    wire signed [63:0] saturated_sum = add_overflow ?
        (extended_sum[64] ? 64'sh8000000000000000 : 64'sh7fffffffffffffff) :
        extended_sum[63:0];
    assign in_ready = rst_n && can_accept;
    assign out_valid = rst_n && full;
    assign out_sum = state;
    assign out_overflow = overflow_flag;
    assign out_sticky = sticky;
    always @(posedge clk) begin
        if (!rst_n) begin
            full <= 0;
            state <= 0;
            overflow_flag <= 0;
            sticky <= 0;
        end else if (can_accept) begin
            full <= in_valid;
            if (accept) begin
                state <= clear ? in_delta : saturated_sum;
                overflow_flag <= !clear && add_overflow;
                sticky <= clear ? 1'b0 : (sticky || add_overflow);
            end
        end
    end
endmodule
