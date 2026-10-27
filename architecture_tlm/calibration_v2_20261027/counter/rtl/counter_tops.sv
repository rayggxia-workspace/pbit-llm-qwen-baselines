`timescale 1ns/1ps
// Fixed tops: g0=clock always on, g2=actual technology ICG mapping required.
module counter_b4_t64_m1_p1_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [25:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(4),.T(64),.PIPE_EVERY(1),.GATE_MODE(0),.AW(26)) dut(.*);
endmodule
module counter_b4_t64_m1_p1_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [25:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(4),.T(64),.PIPE_EVERY(1),.GATE_MODE(2),.AW(26)) dut(.*);
endmodule
module counter_b4_t64_m1_p2_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [25:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(4),.T(64),.PIPE_EVERY(2),.GATE_MODE(0),.AW(26)) dut(.*);
endmodule
module counter_b4_t64_m1_p2_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [25:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(4),.T(64),.PIPE_EVERY(2),.GATE_MODE(2),.AW(26)) dut(.*);
endmodule
module counter_b4_t64_m8_p1_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [207:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(4),.T(64),.PIPE_EVERY(1),.GATE_MODE(0),.AW(26)) dut(.*);
endmodule
module counter_b4_t64_m8_p1_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [207:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(4),.T(64),.PIPE_EVERY(1),.GATE_MODE(2),.AW(26)) dut(.*);
endmodule
module counter_b4_t64_m8_p2_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [207:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(4),.T(64),.PIPE_EVERY(2),.GATE_MODE(0),.AW(26)) dut(.*);
endmodule
module counter_b4_t64_m8_p2_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [207:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(4),.T(64),.PIPE_EVERY(2),.GATE_MODE(2),.AW(26)) dut(.*);
endmodule
module counter_b7_t128_m1_p1_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [32:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(7),.T(128),.PIPE_EVERY(1),.GATE_MODE(0),.AW(33)) dut(.*);
endmodule
module counter_b7_t128_m1_p1_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [32:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(7),.T(128),.PIPE_EVERY(1),.GATE_MODE(2),.AW(33)) dut(.*);
endmodule
module counter_b7_t128_m1_p2_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [32:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(7),.T(128),.PIPE_EVERY(2),.GATE_MODE(0),.AW(33)) dut(.*);
endmodule
module counter_b7_t128_m1_p2_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [447:0] w_mag7,input wire [63:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [32:0] out_sum);
sc_counter_merged #(.N(64),.M(1),.BINS(7),.T(128),.PIPE_EVERY(2),.GATE_MODE(2),.AW(33)) dut(.*);
endmodule
module counter_b7_t128_m8_p1_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [263:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(7),.T(128),.PIPE_EVERY(1),.GATE_MODE(0),.AW(33)) dut(.*);
endmodule
module counter_b7_t128_m8_p1_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [263:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(7),.T(128),.PIPE_EVERY(1),.GATE_MODE(2),.AW(33)) dut(.*);
endmodule
module counter_b7_t128_m8_p2_g0(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [263:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(7),.T(128),.PIPE_EVERY(2),.GATE_MODE(0),.AW(33)) dut(.*);
endmodule
module counter_b7_t128_m8_p2_g2(input wire clk,rst_n,test_en,frame_valid, output wire frame_ready,
input wire [3583:0] w_mag7,input wire [511:0] w_sign,input wire [63:0] x_sign,
input wire [191:0] bin_id,input wire [63:0] sample_bits,input wire sample_valid,
output wire sample_ready,output wire out_valid,input wire out_ready,output wire [263:0] out_sum);
sc_counter_merged #(.N(64),.M(8),.BINS(7),.T(128),.PIPE_EVERY(2),.GATE_MODE(2),.AW(33)) dut(.*);
endmodule
