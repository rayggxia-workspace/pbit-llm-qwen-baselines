`timescale 1ns/1ps
// Stable external g/u and resident W; all64 nonlinear lanes shared by8 columns.
// q_sigma is computed by the original full LUT, not an external probability.
module ns_integrated #(parameter B=8,M=8,OR4=1,CW=11,SAT=0,WEIGHTED=0,SHARE=0,GATE=0)(
 input wire clk,rst_n,en,
 input wire [64*(2*B+24)+M*512+12:0] din,
 output wire [M*32+8:0] dout);
 localparam S=2*B+24,WO=64*S,TAIL=WO+M*512;
 wire [1:0] scale_sel=din[TAIL+:2];
 wire clear=din[TAIL+12];
 wire signed [7:0] eg=8'sd3+$signed({6'b0,scale_sel});
 wire signed [7:0] eu={{3{din[TAIL+6]}},din[TAIL+2+:5]};
 wire signed [7:0] ew={{3{din[TAIL+11]}},din[TAIL+7+:5]};
 wire signed [7:0] output_exponent=eg+eu+ew-8'sd5;
 reg [4:0] accepted;reg done;
 reg [4:0] load_index;reg ready;
 always @(posedge clk)begin
  if(!rst_n||clear)begin load_index<=0;ready<=!SHARE;end
  else if(SHARE&&!ready)begin
   if(load_index==31)ready<=1;
   else load_index<=load_index+1'b1;
  end
 end
 wire fire=en&&ready&&!done&&!clear;
 wire readout=done&&!clear;
 always @(posedge clk)begin
  if(!rst_n||clear)begin accepted<=0;done<=0;end
  else if(fire)begin
   if(accepted==31)done<=1;
   else accepted<=accepted+1'b1;
  end
 end
 wire[63:0] z,xsign;
 wire[511:0] fields;
 wire[15:0] shared_q8;
 genvar s;
 generate if(SHARE)begin:shared_lookup
  for(s=0;s<2;s=s+1)begin:group32
   wire[8:0] q;
   pbit_sigmoid8_lut lut(.drive8(fields[(s*32+load_index)*8+:8]),.q9(q));
   assign shared_q8[s*8+:8]=q[7:0];
  end
 end else begin:unused_lookup
  assign shared_q8=16'd0;
 end endgenerate
 genvar n,m,p,g;
 generate for(n=0;n<64;n=n+1)begin:front
  wire[7:0] ag,au,field;wire sg,su,bg,bs,bu;wire[8:0] q;
  if(B==8)begin:c8
   nw_convert8 #(8) cv(.g(din[n*S+:B]),.u(din[n*S+B+:B]),.sel(scale_sel),.ag(ag),.au(au),.field(field),.sg(sg),.su(su));
  end else begin:c9
   nw_convert9 #(9) cv(.g(din[n*S+:B]),.u(din[n*S+B+:B]),.sel(scale_sel),.ag(ag),.au(au),.field(field),.sg(sg),.su(su));
  end
  assign fields[n*8+:8]=field;
  if(SHARE)begin:cached_sigma
   reg[7:0] probability;
   wire write_word=rst_n&&!clear&&!ready&&(load_index==(n%32));
   if(GATE)begin:word_gate
    wire probability_clk;
    ns_icg gate(.clk(clk),.enable(write_word),.gclk(probability_clk));
    always @(posedge probability_clk)probability<=shared_q8[(n/32)*8+:8];
   end else begin:clock_enable
    always @(posedge clk)if(write_word)probability<=shared_q8[(n/32)*8+:8];
   end
   // Reuse the already-required g sign to distinguish q=0 from q=256.
   // The unsigned comparator itself is strictly eight bits.
   assign q={(!sg&&(probability==8'd0)),probability};
  end else begin:full_sigma
   pbit_sigmoid8_lut lut(.drive8(field),.q9(q));
  end
  pbit_compare8_lt cg(.r8(din[n*S+2*B+:8]),.q8(ag),.bit_o(bg));
  pbit_compare8_q256 cs(.r8(din[n*S+2*B+8+:8]),.q9(q),.bit_o(bs));
  pbit_compare8_lt cu(.r8(din[n*S+2*B+16+:8]),.q8(au),.bit_o(bu));
  assign z[n]=bg&bs&bu;assign xsign[n]=sg^su;
 end
 for(m=0;m<M;m=m+1)begin:column
  if(WEIGHTED)begin:weighted_sum
   wire[64*8-1:0] leaves;
   for(n=0;n<64;n=n+1)begin:weight
    wire negative=xsign[n]^din[WO+8*(m*64+n)+7];
    wire signed[7:0] positive={1'b0,din[WO+8*(m*64+n)+:7]};
    wire signed[7:0] signed_weight=negative?-positive:positive;
    assign leaves[n*8+:8]=(z[n]&&fire)?signed_weight:8'd0;
   end
   wire signed[13:0] delta;wire signed[18:0] count;
   me_sum #(.N(64),.LW(8)) sum(leaves,delta);
   aw_acc #(.B(19),.D(14),.SAT(0)) acc(.clk(clk),.rst_n(rst_n),.clear(clear),.en(fire),.delta(delta),.value(count));
   assign dout[m*32+:32]=readout?{{13{count[18]}},count}:32'd0;
  end else begin:bit_planes
  wire [7*20-1:0] restore_leaves;
  for(p=0;p<7;p=p+1)begin:plane
   wire[63:0] pos,neg;
   for(n=0;n<64;n=n+1)begin:mask
    wire negative=xsign[n]^din[WO+8*(m*64+n)+7];
    wire product=z[n]&din[WO+8*(m*64+n)+p]&fire;
    assign pos[n]=product&!negative;assign neg[n]=product&negative;
   end
   wire signed [CW-1:0] count;
   if(OR4)begin:grouped
    wire[31:0] bits;wire signed[5:0] delta;
    for(g=0;g<16;g=g+1)begin:or4
     assign bits[g]=|pos[g*4+:4];assign bits[16+g]=|neg[g*4+:4];
    end
    me_diff #(16) pc(bits,delta);
    aw_acc #(.B(CW),.D(6),.SAT(SAT)) acc(.clk(clk),.rst_n(rst_n),.clear(clear),.en(fire),.delta(delta),.value(count));
   end else begin:exact
    wire signed[7:0] delta;
    me_diff #(64) pc({neg,pos},delta);
    aw_acc #(.B(CW),.D(8),.SAT(SAT)) acc(.clk(clk),.rst_n(rst_n),.clear(clear),.en(fire),.delta(delta),.value(count));
   end
   wire signed[19:0] extended={{(20-CW){count[CW-1]}},count};
   // Arithmetic output remains isolated until the last sample has accumulated.
   assign restore_leaves[p*20+:20]=readout?(extended<<<p):20'd0;
  end
  wire signed[22:0] restored;
  me_sum #(.N(8),.LW(20)) restore({20'd0,restore_leaves},restored);
  assign dout[m*32+:32]={{9{restored[22]}},restored};
  end
 end endgenerate
 assign dout[M*32+:8]=readout?output_exponent:8'd0;
 assign dout[M*32+8]=readout;
endmodule
