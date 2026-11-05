`timescale 1ns/1ps
module ssg_s6_m1(input wire clk,rst_n,frame_valid,output wire frame_ready,input wire [511:0] w8,input wire [511:0] x8,input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,output wire out_valid,input wire out_ready,output wire [31:0] out_sum);
ss_matrix_signed #(.M(1),.MODE(6)) core(.*);
endmodule
module ssg_s6_m8(input wire clk,rst_n,frame_valid,output wire frame_ready,input wire [4095:0] w8,input wire [511:0] x8,input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,output wire out_valid,input wire out_ready,output wire [255:0] out_sum);
ss_matrix_signed #(.M(8),.MODE(6)) core(.*);
endmodule
