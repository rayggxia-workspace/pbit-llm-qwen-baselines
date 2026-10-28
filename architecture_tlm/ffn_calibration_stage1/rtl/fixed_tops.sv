// Generated fixed elaboration wrappers; contract is cases.json.

module top_counter_b4_t64_m1(input wire clk,rst_n,frame_valid, output wire frame_ready, input wire [447:0] w_mag7, input wire [63:0] w_sign, input wire [63:0] x_sign, input wire [191:0] bin_id, input wire [63:0] sample_bits, input wire sample_valid, output wire sample_ready,out_valid, input wire out_ready, output wire [79:0] out_counts);
  ffn_counter #(.N(64),.M(1),.BINS(4),.T(64)) dut(.*);
endmodule

module top_counter_b7_t128_m1(input wire clk,rst_n,frame_valid, output wire frame_ready, input wire [447:0] w_mag7, input wire [63:0] w_sign, input wire [63:0] x_sign, input wire [191:0] bin_id, input wire [63:0] sample_bits, input wire sample_valid, output wire sample_ready,out_valid, input wire out_ready, output wire [146:0] out_counts);
  ffn_counter #(.N(64),.M(1),.BINS(7),.T(128)) dut(.*);
endmodule

module top_counter_b4_t64_m8(input wire clk,rst_n,frame_valid, output wire frame_ready, input wire [3583:0] w_mag7, input wire [511:0] w_sign, input wire [63:0] x_sign, input wire [191:0] bin_id, input wire [63:0] sample_bits, input wire sample_valid, output wire sample_ready,out_valid, input wire out_ready, output wire [639:0] out_counts);
  ffn_counter #(.N(64),.M(8),.BINS(4),.T(64)) dut(.*);
endmodule

module top_counter_b7_t128_m8(input wire clk,rst_n,frame_valid, output wire frame_ready, input wire [3583:0] w_mag7, input wire [511:0] w_sign, input wire [63:0] x_sign, input wire [191:0] bin_id, input wire [63:0] sample_bits, input wire sample_valid, output wire sample_ready,out_valid, input wire out_ready, output wire [1175:0] out_counts);
  ffn_counter #(.N(64),.M(8),.BINS(7),.T(128)) dut(.*);
endmodule

module top_restore_b4_c20(input wire clk,rst_n,in_valid, output wire in_ready, input wire [79:0] counts, input wire [15:0] coeff, input wire [5:0] rshift, output wire out_valid, input wire out_ready, output wire signed [63:0] out_delta);
  ffn_restore #(.BINS(4),.CW(20)) dut(.*);
endmodule

module top_restore_b7_c21(input wire clk,rst_n,in_valid, output wire in_ready, input wire [146:0] counts, input wire [15:0] coeff, input wire [5:0] rshift, output wire out_valid, input wire out_ready, output wire signed [63:0] out_delta);
  ffn_restore #(.BINS(7),.CW(21)) dut(.*);
endmodule

module top_accumulator64(input wire clk,rst_n,in_valid, output wire in_ready, input wire signed [63:0] in_delta, input wire clear, output wire out_valid, input wire out_ready, output wire signed [63:0] out_sum, output wire out_overflow,out_sticky);
  ffn_accumulator dut(.*);
endmodule

module top_chain_b4_t64_m1(input wire clk,rst_n,frame_valid, output wire frame_ready, input wire [447:0] w_mag7, input wire [63:0] w_sign,x_sign, input wire [191:0] bin_id, input wire [63:0] sample_bits, input wire sample_valid, output wire sample_ready, input wire [15:0] coeff, input wire [5:0] rshift, input wire frame_clear, output wire out_valid, input wire out_ready, output wire signed [63:0] out_sum, output wire out_overflow,out_sticky);
  ffn_chain #(.N(64),.BINS(4),.T(64)) dut(.*);
endmodule

module top_chain_b7_t128_m1(input wire clk,rst_n,frame_valid, output wire frame_ready, input wire [447:0] w_mag7, input wire [63:0] w_sign,x_sign, input wire [191:0] bin_id, input wire [63:0] sample_bits, input wire sample_valid, output wire sample_ready, input wire [15:0] coeff, input wire [5:0] rshift, input wire frame_clear, output wire out_valid, input wire out_ready, output wire signed [63:0] out_sum, output wire out_overflow,out_sticky);
  ffn_chain #(.N(64),.BINS(7),.T(128)) dut(.*);
endmodule
