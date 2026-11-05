`timescale 1ns/1ps
module matrix_s0_m1(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [1*448-1:0] w_mag7,input wire [1*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [1*32-1:0] out_sum);
wire [1*25-1:0] sums;
 sc_counter_merged #(.M(1),.T(32),.BINS(4),.PIPE_EVERY(2),.GATE_MODE(0),.AW(25)) core(
 .clk(clk),.rst_n(rst_n),.test_en(1'b0),.frame_valid(frame_valid),.frame_ready(frame_ready),
 .w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),.bin_id(bin_id),
 .sample_bits(sample_bits),.sample_valid(sample_valid),.sample_ready(sample_ready),
 .out_valid(out_valid),.out_ready(out_ready),.out_sum(sums));
 genvar j;generate for(j=0;j<1;j=j+1) begin:extend
  assign out_sum[j*32+:32]={{7{sums[j*25+24]}},sums[j*25+:25]};
 end endgenerate
endmodule
module matrix_s1_m1(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [1*448-1:0] w_mag7,input wire [1*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [1*32-1:0] out_sum);
matrix_variant #(.M(1),.MODE(1)) core(.*);
endmodule
module matrix_s2_m1(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [1*448-1:0] w_mag7,input wire [1*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [1*32-1:0] out_sum);
matrix_variant #(.M(1),.MODE(2)) core(.*);
endmodule
module matrix_s3_m1(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [1*448-1:0] w_mag7,input wire [1*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [1*32-1:0] out_sum);
matrix_variant #(.M(1),.MODE(3)) core(.*);
endmodule
module matrix_s4_m1(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [1*448-1:0] w_mag7,input wire [1*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [1*32-1:0] out_sum);
matrix_variant #(.M(1),.MODE(4)) core(.*);
endmodule
module matrix_s5_m1(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [1*448-1:0] w_mag7,input wire [1*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [1*32-1:0] out_sum);
matrix_variant #(.M(1),.MODE(5)) core(.*);
endmodule
module matrix_s0_m8(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [8*448-1:0] w_mag7,input wire [8*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [8*32-1:0] out_sum);
wire [8*25-1:0] sums;
 sc_counter_merged #(.M(8),.T(32),.BINS(4),.PIPE_EVERY(2),.GATE_MODE(0),.AW(25)) core(
 .clk(clk),.rst_n(rst_n),.test_en(1'b0),.frame_valid(frame_valid),.frame_ready(frame_ready),
 .w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),.bin_id(bin_id),
 .sample_bits(sample_bits),.sample_valid(sample_valid),.sample_ready(sample_ready),
 .out_valid(out_valid),.out_ready(out_ready),.out_sum(sums));
 genvar j;generate for(j=0;j<8;j=j+1) begin:extend
  assign out_sum[j*32+:32]={{7{sums[j*25+24]}},sums[j*25+:25]};
 end endgenerate
endmodule
module matrix_s1_m8(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [8*448-1:0] w_mag7,input wire [8*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [8*32-1:0] out_sum);
matrix_variant #(.M(8),.MODE(1)) core(.*);
endmodule
module matrix_s2_m8(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [8*448-1:0] w_mag7,input wire [8*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [8*32-1:0] out_sum);
matrix_variant #(.M(8),.MODE(2)) core(.*);
endmodule
module matrix_s3_m8(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [8*448-1:0] w_mag7,input wire [8*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [8*32-1:0] out_sum);
matrix_variant #(.M(8),.MODE(3)) core(.*);
endmodule
module matrix_s4_m8(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [8*448-1:0] w_mag7,input wire [8*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [8*32-1:0] out_sum);
matrix_variant #(.M(8),.MODE(4)) core(.*);
endmodule
module matrix_s5_m8(input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [8*448-1:0] w_mag7,input wire [8*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [8*32-1:0] out_sum);
matrix_variant #(.M(8),.MODE(5)) core(.*);
endmodule
