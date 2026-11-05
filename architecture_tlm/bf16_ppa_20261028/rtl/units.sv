`timescale 1ns/1ps
module bf_unit #(parameter integer KIND=0,PIPES=3)(input wire clk,rst_n,en,input wire [31:0] a,b,c,output wire valid,output wire [31:0] dout);
 wire ready;wire [2:0][31:0] operands;
 assign operands[0]=a;assign operands[1]=b;assign operands[2]=c;
 fpnew_fma_multi #(.FpFmtConfig(5'b10001),.NumPipeRegs(PIPES),.PipeConfig(fpnew_pkg::DISTRIBUTED),.TagType(logic),.AuxType(logic)) core(
 .clk_i(clk),.rst_ni(rst_n),.operands_i(operands),.is_boxed_i('1),.rnd_mode_i(fpnew_pkg::RNE),
 .op_i(KIND==2?fpnew_pkg::ADD:(KIND==1?fpnew_pkg::MUL:fpnew_pkg::FMADD)),.op_mod_i(1'b0),
 .src_fmt_i(KIND==2?fpnew_pkg::FP32:fpnew_pkg::FP16ALT),.src2_fmt_i(fpnew_pkg::FP32),.dst_fmt_i(fpnew_pkg::FP32),
 .tag_i(1'b0),.mask_i(1'b1),.aux_i(1'b0),.in_valid_i(en),.in_ready_o(ready),.flush_i(1'b0),
 .result_o(dout),.status_o(),.extension_bit_o(),.tag_o(),.mask_o(),.aux_o(),.out_valid_o(valid),.out_ready_i(1'b1),.busy_o(),.reg_ena_i('0),.early_out_valid_o());
endmodule
module bf_fma2(input wire clk,rst_n,en,input wire [31:0] a,b,c,output wire valid,output wire [31:0] dout);bf_unit #(.KIND(0),.PIPES(2)) u(.*);endmodule
module bf_fma3(input wire clk,rst_n,en,input wire [31:0] a,b,c,output wire valid,output wire [31:0] dout);bf_unit #(.KIND(0),.PIPES(3)) u(.*);endmodule
module bf_mul1(input wire clk,rst_n,en,input wire [31:0] a,b,c,output wire valid,output wire [31:0] dout);bf_unit #(.KIND(1),.PIPES(1)) u(.*);endmodule
module bf_add2(input wire clk,rst_n,en,input wire [31:0] a,b,c,output wire valid,output wire [31:0] dout);bf_unit #(.KIND(2),.PIPES(2)) u(.*);endmodule
