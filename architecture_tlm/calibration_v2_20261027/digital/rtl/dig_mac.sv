`timescale 1ns/1ps
// NON-FUSED BF16 product followed by FP32 add. c is externally supplied.
// L=14 clocks, II=1 for independent (a,b,c) transactions, not a one-cycle
// dependent accumulator. Reusing one context requires its prior result first.
module dig_bf16_mac(
 input wire clk,rst_n,in_valid,output wire in_ready,
 input wire [15:0] a,b,input wire [31:0] c,
 output wire out_valid,input wire out_ready,
 output wire [31:0] y,output wire [4:0] status
);
 wire product_valid,product_ready;
 wire [31:0] product;
 wire [4:0] mul_status,add_status;
 reg [31:0] c_pipe[0:6];
 reg [4:0] f_pipe[0:6];
 wire add_in_ready;
 wire mul_advance=in_ready;
 wire add_advance=add_in_ready;
 integer i;
 dig_bf16_mul mul(clk,rst_n,in_valid,in_ready,{16'b0,a},{16'b0,b},product_valid,product_ready,product,mul_status);
 assign product_ready=add_in_ready;
 dig_fp32_add add(clk,rst_n,product_valid,add_in_ready,product,c_pipe[6],out_valid,out_ready,y,add_status);
 always @(posedge clk) begin
  if(!rst_n) begin for(i=0;i<7;i=i+1) begin c_pipe[i]<=0;f_pipe[i]<=0;end end
  else begin
   if(mul_advance) begin c_pipe[0]<=c;for(i=1;i<7;i=i+1)c_pipe[i]<=c_pipe[i-1];end
   if(add_advance) begin f_pipe[0]<=mul_status;for(i=1;i<7;i=i+1)f_pipe[i]<=f_pipe[i-1];end
  end
 end
 assign status=add_status|f_pipe[6];
endmodule

// 16 explicitly stored accumulation contexts. An external scheduler supplies
// in_context; busy contexts backpressure. Round-robin independent contexts can
// sustain II=1, whereas one dependent context still waits for its result.
// Storage is REAL: 16x32 accumulator bits, 16 busy bits, 16x4 tag FIFO + control.
// Cross-context final reduction is NOT included or charged by this module.
module dig_bf16_context16(
 input wire clk,rst_n,in_valid,output wire in_ready,
 input wire [3:0] in_context,input wire [15:0] a,b,
 output wire out_valid,input wire out_ready,
 output wire [3:0] out_context,output wire [31:0] y,output wire [4:0] status,
 output wire [15:0] busy_mask,output wire [4:0] occupancy
);
 reg [31:0] accum[0:15];reg [15:0] busy;
 reg [3:0] tags[0:15];reg [3:0] rdptr,wrptr;reg [4:0] count;
 wire mac_in_ready,mac_out_valid;
 wire accept=in_valid&&in_ready;
 wire retire=out_valid&&out_ready;
 assign in_ready=rst_n&&!busy[in_context]&&(count<16)&&mac_in_ready;
 assign out_valid=mac_out_valid;
 assign out_context=tags[rdptr];
 assign busy_mask=busy;assign occupancy=count;
 dig_bf16_mac mac(clk,rst_n,accept,mac_in_ready,a,b,accum[in_context],mac_out_valid,out_ready,y,status);
 integer i;
 always @(posedge clk)begin
  if(!rst_n)begin
   busy<=0;count<=0;rdptr<=0;wrptr<=0;
   for(i=0;i<16;i=i+1)begin accum[i]<=0;tags[i]<=0;end
  end else begin
   case({accept,retire})2'b10:count<=count+1'b1;2'b01:count<=count-1'b1;default:count<=count;endcase
   if(accept)begin tags[wrptr]<=in_context;wrptr<=wrptr+1'b1;busy[in_context]<=1;end
   if(retire)begin accum[out_context]<=y;busy[out_context]<=0;rdptr<=rdptr+1'b1;end
  end
 end
endmodule

// Eight independent MAC lanes; common handshake, 8 products + 8 adds per beat.
// This is NOT an 8-input dot reduction and contains no hidden accumulation SRAM.
module dig_bf16_mac8(
 input wire clk,rst_n,in_valid,output wire in_ready,
 input wire [127:0] a,b,input wire [255:0] c,
 output wire out_valid,input wire out_ready,
 output wire [255:0] y,output wire [39:0] status
);
 wire [7:0] ir,ov;
 assign in_ready=&ir;assign out_valid=&ov;
 genvar i;
 generate for(i=0;i<8;i=i+1) begin: lanes
  dig_bf16_mac lane(clk,rst_n,in_valid,ir[i],a[i*16+:16],b[i*16+:16],c[i*32+:32],ov[i],out_ready,y[i*32+:32],status[i*5+:5]);
 end endgenerate
endmodule

// Honest dependent accumulator: no hidden context interleaving. It waits for
// each result to be consumed before accepting the next product (II >= 15).
// clear is only legal while idle and no input is accepted in that cycle.
module dig_bf16_accum(
 input wire clk,rst_n,clear,in_valid,output wire in_ready,
 input wire [15:0] a,b,output wire out_valid,input wire out_ready,
 output wire [31:0] y,output wire [4:0] status
);
 reg busy;reg [31:0] acc;
 wire mac_ready;
 assign in_ready=rst_n&&!busy&&!clear&&mac_ready;
 dig_bf16_mac mac(clk,rst_n,in_valid&&in_ready,mac_ready,a,b,acc,out_valid,out_ready,y,status);
 always @(posedge clk) begin
  if(!rst_n) begin busy<=0;acc<=0;end
  else begin
   if(clear&&!busy) acc<=0;
   if(in_valid&&in_ready)busy<=1;
   if(out_valid&&out_ready)begin acc<=y;busy<=0;end
  end
 end
endmodule
