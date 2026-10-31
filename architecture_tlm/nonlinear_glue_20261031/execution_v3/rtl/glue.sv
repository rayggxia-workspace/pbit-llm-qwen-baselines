`timescale 1ns/1ps
// K64 core only. External resident codes/scales and three distinct R8 words.
// Four PoT scale exponents are parameters; one selector shared by all 64 lanes.
module ng_convert #(parameter B=8, E0=3,E1=4,E2=5,E3=6)(
 input wire [B-1:0] g,u,input wire [1:0] sel,
 output wire [7:0] ag,au,field,output wire sg,su);
 wire [B-1:0] mag=g[B-1]?(~g+{{(B-1){1'b0}},1'b1}):g;
 function automatic [7:0] amplitude;
  input [B-1:0] m;input integer exponent;
  integer d,q,rem,half;
  begin
   d=13-B-exponent;
   if(d>=0)q=m<<d;
   else begin
    q=m>>(-d);rem=m-(q<<(-d));half=1<<(-d-1);
    if(rem>half||(rem==half&&(q&1)))q=q+1;
   end
   amplitude=q>255?8'd255:q[7:0];
  end
 endfunction
 assign ag=sel==0?amplitude(mag,E0):sel==1?amplitude(mag,E1):sel==2?amplitude(mag,E2):amplitude(mag,E3);
 assign sg=g[B-1];assign su=u[B-1];
 generate if(B==8)begin
  assign au={u[6:0],1'b0};assign field=g;
 end else begin
  assign au=u[7:0];
  function automatic [7:0] address;
   input [8:0] v;integer m,q;
   begin
    m=$signed(v);if(m<0)m=-m;
    q=(m>>1)+((m&3)==3);
    if(v[8])q=-q;
    address=q>127?8'h7f:q< -128?8'h80:q[7:0];
   end
  endfunction
  assign field=address(g);
 end endgenerate
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
