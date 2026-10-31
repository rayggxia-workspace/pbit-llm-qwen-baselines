`timescale 1ns/1ps
// K64 core only. External resident codes/scales and three distinct R8 words.
// Four PoT scale exponents are parameters; one selector shared by all 64 lanes.
module nw_convert8 #(parameter B=8, E0=3,E1=4,E2=5,E3=6)(
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


`timescale 1ns/1ps
// Width-bounded equivalent for the explicitly tested scale catalog [3,4,5,6].
// Shift once, round once, saturate once; avoid signed32 intermediate arithmetic.
module nw_convert9 #(parameter B=8, E0=3,E1=4,E2=5,E3=6)(
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
