`timescale 1ns/1ps
module p64_sum #(parameter N=64,LW=16,TW=LW+$clog2(N))(
 input wire [N*LW-1:0] leaves,output wire signed[TW-1:0] total);
 genvar l,k;generate for(l=0;l<$clog2(N);l=l+1)begin:level
  wire signed[LW+l:0] v[0:(N>>(l+1))-1];
  for(k=0;k<(N>>(l+1));k=k+1)begin:node
   wire signed[LW+l-1:0] a,b;
   if(l==0)begin assign a=leaves[2*k*LW+:LW];assign b=leaves[(2*k+1)*LW+:LW];end
   else begin assign a=level[l-1].v[2*k];assign b=level[l-1].v[2*k+1];end
   assign v[k]=$signed({a[LW+l-1],a})+$signed({b[LW+l-1],b});
  end
 end endgenerate
 assign total=level[$clog2(N)-1].v[0];
endmodule
// One N64 dot per valid input; no temporal multiplier sharing or weight bank.
module p64_dot #(parameter AW=32)(input wire clk,rst_n,en,input wire[511:0]a,b,
 output reg valid,output wire[31:0]dout);
 wire[1023:0] products;wire signed[21:0] dot;reg signed[AW-1:0] result;
 genvar i;generate for(i=0;i<64;i=i+1)begin:lane
  wire signed[7:0]x=a[i*8+:8],w=b[i*8+:8];assign products[i*16+:16]=x*w;
 end endgenerate
 p64_sum tree(products,dot);
 always @(posedge clk)begin if(!rst_n)result<=0;else if(en)result<=$signed(dot);end
 always @(posedge clk or negedge rst_n)begin if(!rst_n)valid<=0;else valid<=en;end
 assign dout={{(32-AW){result[AW-1]}},result};
endmodule
module i8_par64_a32(input wire clk,rst_n,en,input wire[511:0]a,b,output wire valid,output wire[31:0]dout);p64_dot #(.AW(32))u(.*);endmodule
module i8_par64_a22(input wire clk,rst_n,en,input wire[511:0]a,b,output wire valid,output wire[31:0]dout);p64_dot #(.AW(22))u(.*);endmodule
