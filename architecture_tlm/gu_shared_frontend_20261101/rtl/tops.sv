`timescale 1ns/1ps
module gu_m16_replicated8(input wire clk,rst_n,en,input wire [10511:0] din,output wire [528:0] dout);gu_integrated #(.M(16),.SHARE(0)) u(.*);endmodule
module gu_m16_shared(input wire clk,rst_n,en,input wire [10511:0] din,output wire [528:0] dout);gu_integrated #(.M(16),.SHARE(1)) u(.*);endmodule
module gu_m64_replicated8(input wire clk,rst_n,en,input wire [41999:0] din,output wire [2064:0] dout);gu_integrated #(.M(64),.SHARE(0)) u(.*);endmodule
module gu_m64_shared(input wire clk,rst_n,en,input wire [41999:0] din,output wire [2064:0] dout);gu_integrated #(.M(64),.SHARE(1)) u(.*);endmodule
