// Digital characterization candidate; NOT the BF16 reference implementation.
// Accept at enabled edge N, produce at enabled edge N+3. II=1 enabled clock.
module swiglu_epilogue_q10 #(
    parameter integer OUT_W = 24
) (
    input  wire clk,
    input  wire rst,
    input  wire ce,
    input  wire in_valid,
    input  wire signed [15:0] g_in,
    input  wire signed [15:0] u_in,
    output reg out_valid,
    output reg signed [OUT_W-1:0] y_out,
    output reg saturated,
    output reg inexact
);
    // Verification-time parameter contract; excluded from synthesized logic.
    // synopsys translate_off
    initial begin
        if (OUT_W < 2 || OUT_W > 32)
            $fatal(1, "OUT_W must be in [2,32]");
    end
    // synopsys translate_on
    // Constant case ROM: synthesis is allowed to map it to logic or a ROM.
    // It is neither a writable probability register bank nor a foundry SRAM.
    `include "sigmoid_lut.svh"

    function automatic [16:0] sigmoid_q16;
        input signed [15:0] g;
        reg [16:0] magnitude;
        reg [16:0] positive;
        begin
            // 17-bit magnitude also handles g=-32768 without overflow.
            magnitude = g[15] ? ({1'b0, ~g} + 17'd1) : {1'b0, g};
            if (magnitude >= 17'd8192)
                sigmoid_q16 = g[15] ? 17'd0 : 17'd65536;
            else begin
                positive = sigmoid_positive_lut(magnitude[12:5]);
                sigmoid_q16 = g[15] ? 17'd65536 - positive : positive;
            end
        end
    endfunction

    reg v0, v1, v2;
    reg signed [15:0] g_q, u_q;
    reg signed [31:0] gu_q;
    reg [16:0] sigma_q;
    reg signed [49:0] product_q;
    wire signed [31:0] gu_next = g_q * u_q;
    wire signed [17:0] sigma_signed = $signed({1'b0, sigma_q});
    wire signed [49:0] product_next = gu_q * sigma_signed;

    // g/u are Q10, sigmoid is Q16. Product is Q36; output Q10 needs /2^26.
    // Round the unsigned magnitude once, then restore the sign. This makes
    // negative ties symmetric and avoids arithmetic-shift rounding bias.
    reg [49:0] magnitude;
    reg [24:0] rounded_magnitude;
    reg signed [50:0] signed_result;
    reg signed [OUT_W-1:0] y_next;
    reg saturated_next, inexact_next;
    localparam signed [50:0] OUT_MAX = (51'sd1 << (OUT_W-1)) - 51'sd1;
    localparam signed [50:0] OUT_MIN = -(51'sd1 << (OUT_W-1));
    always @* begin
        magnitude = product_q[49] ? (~product_q + 50'd1) : product_q;
        rounded_magnitude = {1'b0, magnitude[49:26]};
        if ((magnitude[25:0] > 26'd33554432) ||
            ((magnitude[25:0] == 26'd33554432) && magnitude[26]))
            rounded_magnitude = rounded_magnitude + 25'd1;
        signed_result = product_q[49] ?
            -$signed({26'd0, rounded_magnitude}) :
             $signed({26'd0, rounded_magnitude});
        saturated_next = 1'b0;
        inexact_next = |magnitude[25:0];
        if (signed_result > OUT_MAX) begin
            y_next = OUT_MAX[OUT_W-1:0];
            saturated_next = 1'b1;
            inexact_next = 1'b1;
        end else if (signed_result < OUT_MIN) begin
            y_next = OUT_MIN[OUT_W-1:0];
            saturated_next = 1'b1;
            inexact_next = 1'b1;
        end else
            y_next = signed_result[OUT_W-1:0];
    end

    always @(posedge clk) begin
        if (rst) begin
            v0 <= 1'b0;
            v1 <= 1'b0;
            v2 <= 1'b0;
            out_valid <= 1'b0;
            g_q <= 16'sd0;
            u_q <= 16'sd0;
            gu_q <= 32'sd0;
            sigma_q <= 17'd0;
            product_q <= 50'sd0;
            y_out <= {OUT_W{1'b0}};
            saturated <= 1'b0;
            inexact <= 1'b0;
        end else if (ce) begin
            v0 <= in_valid;
            v1 <= v0;
            v2 <= v1;
            out_valid <= v2;
            // Invalid external inputs cannot toggle the expensive datapath.
            if (in_valid) begin
                g_q <= g_in;
                u_q <= u_in;
            end
            if (v0) begin
                gu_q <= gu_next;
                sigma_q <= sigmoid_q16(g_q);
            end
            if (v1)
                product_q <= product_next;
            if (v2) begin
                y_out <= y_next;
                saturated <= saturated_next;
                inexact <= inexact_next;
            end
        end
    end
endmodule
