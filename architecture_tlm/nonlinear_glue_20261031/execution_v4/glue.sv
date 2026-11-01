`timescale 1ns/1ps
// Width-bounded equivalent for the explicitly tested scale catalog [3,4,5,6].
// Shift once, round once, saturate once; avoid signed32 intermediate arithmetic.
module ng_convert #(parameter B=8, E0=3,E1=4,E2=5,E3=6)(
 input wire [B-1:0] g,u,input wire [1:0] sel,
 output wire [7:0] ag,au,field,output wire sg,su);
 wire [B-1:0] mag=g[B-1]?(~g+{{(B-1){1'b0}},1'b1}):g;
 wire [9:0] expanded,shifted;
 wire increment;
 wire [8:0] rounded={1'b0,shifted[7:0]}+increment;
 assign shifted=expanded>>sel;
 assign ag=((|shifted[9:8])|rounded[8])?8'hff:rounded[7:0];
 assign sg=g[B-1];assign su=u[B-1];
 generate if(B==8)begin
  assign expanded={mag,2'b00};
  assign increment=(sel==3)&mag[0]&mag[1];
  assign au={u[6:0],1'b0};assign field=g;
 end else begin
  wire [7:0] address_rounded=g[8:1]+(g[0]&g[1]);
  assign expanded={mag,1'b0};
  assign increment=((sel==2)&mag[0]&mag[1])|((sel==3)&mag[1]&(mag[0]|mag[2]));
  assign au=u[7:0];
  // Positive255 rounds127.5 to128, then saturates127; all other codes fit.
  assign field=(!g[8]&&(&g[7:0]))?8'h7f:address_rounded;
 end endgenerate
`ifndef SYNTHESIS
 initial if(E0!=3||E1!=4||E2!=5||E3!=6)$fatal(1,"Optimized test catalog must be3,4,5,6");
`endif
endmodule

module ng_conversion64 #(parameter B=8)(input wire clk,rst_n,en,
 input wire [128*B+1:0] din,output wire [1663:0] dout);
 genvar k;
 generate for(k=0;k<64;k=k+1)begin:lane
  ng_convert #(B) cv(.g(din[k*2*B+:B]),.u(din[k*2*B+B+:B]),.sel(din[128*B+:2]),
   .ag(dout[k*26+:8]),.au(dout[k*26+8+:8]),.field(dout[k*26+16+:8]),.sg(dout[k*26+24]),.su(dout[k*26+25]));
 end endgenerate
endmodule

// Pipeline stores only 64 z bits plus one valid bit. Sign remains an external
// frame-held signal: do not replace g/u until valid has drained to zero.
module ng_finish64 #(parameter PIPE=0)(input wire clk,rst_n,en,
 input wire [63:0] a,b,c,sg,su,output wire [128:0] dout);
 wire [63:0] z=a&b&c;
 assign dout[127:64]=sg^su;
 generate if(PIPE)begin
  reg[63:0] zr;reg valid;
  always @(posedge clk)begin
   if(!rst_n)begin zr<=0;valid<=0;end
   else begin valid<=en;if(en)zr<=z;end
  end
  assign dout[63:0]=zr;assign dout[128]=valid;
 end else begin
  assign dout[63:0]=z;assign dout[128]=en;
 end endgenerate
endmodule

module ng_and64 #(parameter PIPE=0)(input wire clk,rst_n,en,
 input wire [319:0] din,output wire [128:0] dout);
 ng_finish64 #(PIPE) f(.clk(clk),.rst_n(rst_n),.en(en),
  .a(din[63:0]),.b(din[127:64]),.c(din[191:128]),.sg(din[255:192]),.su(din[319:256]),.dout(dout));
endmodule

// q_sigma comes from the already-characterized LUT and is held for the frame.
// A g-field output is unnecessary here: the standalone converter measures it.
module ng_core64 #(parameter B=8,PIPE=0)(input wire clk,rst_n,en,
 input wire [64*(2*B+33)+1:0] din,output wire [640:0] dout);
 localparam S=2*B+33;
 wire[63:0] bg,bs,bu,sg,su;
 genvar k;
 generate for(k=0;k<64;k=k+1)begin:lane
  wire[7:0] ag,au,field;
  ng_convert #(B) cv(.g(din[k*S+:B]),.u(din[k*S+B+:B]),.sel(din[64*S+:2]),
    .ag(ag),.au(au),.field(field),.sg(sg[k]),.su(su[k]));
  assign dout[129+k*8+:8]=field;
  pbit_compare8_lt cg(.r8(din[k*S+2*B+:8]),.q8(ag),.bit_o(bg[k]));
  pbit_compare8_lt cu(.r8(din[k*S+2*B+16+:8]),.q8(au),.bit_o(bu[k]));
  pbit_compare8_q256 cs(.r8(din[k*S+2*B+8+:8]),.q9(din[k*S+2*B+24+:9]),.bit_o(bs[k]));
 end endgenerate
 ng_finish64 #(PIPE) f(.clk(clk),.rst_n(rst_n),.en(en),.a(bg),.b(bs),.c(bu),.sg(sg),.su(su),.dout(dout[128:0]));
endmodule
