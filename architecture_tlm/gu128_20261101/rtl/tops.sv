`timescale 1ns/1ps
module gu128_two_m64(input wire clk,rst_n,en,input wire [67856:0] din,output wire [4112:0] dout);gu128_integrated #(.DUAL(1)) u(.*);endmodule
module gu128_fused(input wire clk,rst_n,en,input wire [67856:0] din,output wire [4112:0] dout);gu128_integrated #(.DUAL(0)) u(.*);endmodule
