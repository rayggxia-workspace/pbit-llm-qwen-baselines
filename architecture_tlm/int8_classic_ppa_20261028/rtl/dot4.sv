`timescale 1ns/1ps
// Conventional product pipeline -> balanced reduction -> output-stationary sum.
// Asynchronous control reset; synchronous accumulator reset. Product flops need no reset: valid masks
// their startup contents. No SRAM, hidden resident-weight array or inferred ICG.
module i8_dot64 #(parameter integer AW=32)(
 input wire clk,rst_n,start,en,input wire [31:0] a,b,
 output wire ready,output reg valid,output wire [31:0] dout);
 reg busy,product_valid;reg [4:0] accepted,returned;
 reg signed [15:0] products[0:3];reg signed [AW-1:0] acc;
 assign ready=busy&&(accepted<16);
 wire push=en&&ready;
 assign dout={{(32-AW){acc[AW-1]}},acc};
 wire signed [16:0] pair0=$signed({products[0][15],products[0]})+$signed({products[1][15],products[1]});
 wire signed [16:0] pair1=$signed({products[2][15],products[2]})+$signed({products[3][15],products[3]});
 wire signed [17:0] group_sum=$signed({pair0[16],pair0})+$signed({pair1[16],pair1});
 wire signed [AW-1:0] next_acc=acc+$signed({{(AW-18){group_sum[17]}},group_sum});
 genvar i;generate for(i=0;i<4;i=i+1)begin:lane
  always @(posedge clk)if(rst_n&&push)products[i]<=$signed(a[i*8+:8])*$signed(b[i*8+:8]);
 end endgenerate
 always @(posedge clk)begin
  if(!rst_n || (start&&!busy))acc<=0;
  else if(busy&&product_valid)acc<=next_acc;
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin busy<=0;product_valid<=0;accepted<=0;returned<=0;valid<=0;end
  else begin
   valid<=0;
   if(start&&!busy)begin busy<=1;accepted<=0;returned<=0;product_valid<=0;end
   else begin
    product_valid<=push;
    if(push)accepted<=accepted+1;
    if(busy&&product_valid)begin
     returned<=returned+1;
     if(returned==15)begin valid<=1;busy<=0;end
    end
   end
  end
 end
endmodule
module i8_dot4_a32(input wire clk,rst_n,start,en,input wire [31:0]a,b,output wire ready,valid,output wire[31:0]dout);i8_dot64 #(.AW(32))u(.*);endmodule
module i8_dot4_a22(input wire clk,rst_n,start,en,input wire [31:0]a,b,output wire ready,valid,output wire[31:0]dout);i8_dot64 #(.AW(22))u(.*);endmodule
