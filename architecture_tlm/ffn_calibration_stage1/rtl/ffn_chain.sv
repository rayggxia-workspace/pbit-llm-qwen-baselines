// First-round calibration chain, one output lane. No random source/storage.
// All input weights, signs and bins stay stable until frame output accepted.
// Synchronous active-low reset; at most one frame outstanding.
module ffn_chain #(parameter integer N=64, BINS=4, T=64,
    CW=1+$clog2(N*127*T+1))(
    input wire clk, rst_n, frame_valid, output wire frame_ready,
    input wire [N*7-1:0] w_mag7, input wire [N-1:0] w_sign,x_sign,
    input wire [N*3-1:0] bin_id, input wire [N-1:0] sample_bits,
    input wire sample_valid, output wire sample_ready,
    input wire [15:0] coeff, input wire [5:0] rshift, input wire frame_clear,
    output wire out_valid, input wire out_ready,
    output wire signed [63:0] out_sum, output wire out_overflow,out_sticky
);
    reg busy; reg [15:0] coeff_q; reg [5:0] shift_q; reg clear_q;
    wire c_frame_ready,c_valid,c_ready,r_valid,r_ready;
    wire [BINS*CW-1:0] counts; wire signed [63:0] delta;
    assign frame_ready = rst_n && !busy && c_frame_ready;
    always @(posedge clk) begin
        if (!rst_n) begin busy<=0; coeff_q<=0; shift_q<=0; clear_q<=0; end
        else begin
            if (frame_valid && frame_ready) begin
                busy<=1; coeff_q<=coeff; shift_q<=rshift; clear_q<=frame_clear;
            end
            if (out_valid && out_ready) busy<=0;
        end
    end
    ffn_counter #(.N(N),.M(1),.BINS(BINS),.T(T),.CW(CW)) counter(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid && !busy),
        .frame_ready(c_frame_ready),.w_mag7(w_mag7),.w_sign(w_sign),
        .x_sign(x_sign),.bin_id(bin_id),.sample_bits(sample_bits),
        .sample_valid(sample_valid),.sample_ready(sample_ready),
        .out_valid(c_valid),.out_ready(c_ready),.out_counts(counts));
    ffn_restore #(.BINS(BINS),.CW(CW)) restore(
        .clk(clk),.rst_n(rst_n),.in_valid(c_valid),.in_ready(c_ready),
        .counts(counts),.coeff(coeff_q),.rshift(shift_q),
        .out_valid(r_valid),.out_ready(r_ready),.out_delta(delta));
    ffn_accumulator accumulator(
        .clk(clk),.rst_n(rst_n),.in_valid(r_valid),.in_ready(r_ready),
        .in_delta(delta),.clear(clear_q),.out_valid(out_valid),.out_ready(out_ready),
        .out_sum(out_sum),.out_overflow(out_overflow),.out_sticky(out_sticky));
endmodule
