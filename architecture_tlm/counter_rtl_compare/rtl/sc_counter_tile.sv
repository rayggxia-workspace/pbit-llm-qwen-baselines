// Identical framing, input/output protocol and readout register for A and B.
// Full parallel *external* weight pins: NO implicit SRAM or weight DFF copy.
module sc_counter_tile #(parameter integer ARCH=0,N=64,M=1,T=32,PIPE=1,
 parameter integer BINS=4,SW=$clog2(N*T*128+1)+1)(
 input wire clk,rst_n,cfg_start,
 output wire cfg_ready,
 input wire [N*M*8-1:0] weights,
 input wire [N-1:0] input_sign,true_one,
 input wire [N*2-1:0] input_bin,
 input wire in_valid,
 output wire in_ready,
 input wire [N-1:0] sample_bits,
 output wire out_valid,
 input wire out_ready,
 output reg [M*BINS*SW-1:0] result);
 localparam integer IDLE=0,RUN=1,DRAIN=2,CAPTURE=3,OUTPUT=4;
 localparam integer TW=$clog2(T+1);
 reg [2:0] state;
 reg [TW-1:0] accepted;
 wire clear=cfg_ready&&cfg_start;
 wire accept=in_valid&&in_ready;
 wire last=accepted==T-1;
 wire [M-1:0] lane_valid,lane_last;
 wire update_valid=lane_valid[0],update_last=lane_last[0];
 wire [M*BINS*SW-1:0] sums;
 assign cfg_ready=state==IDLE;
 assign in_ready=state==RUN;
 assign out_valid=state==OUTPUT;
 genvar o;
 generate for(o=0;o<M;o=o+1) begin: output_lane
  if(ARCH==0) begin: A
   sc_counter_a #(.N(N),.M(1),.T(T),.BINS(BINS),.PIPE(PIPE),.SW(SW)) core
    (.clk(clk),.rst_n(rst_n),.clear(clear),.accept(accept),.last(last),.weights(weights[o*N*8+:N*8]),
     .bits(sample_bits),.input_sign(input_sign),.true_one(true_one),.input_bin(input_bin),
     .update_valid(lane_valid[o]),.update_last(lane_last[o]),.sums(sums[o*BINS*SW+:BINS*SW]));
  end else begin: B
   sc_counter_b #(.N(N),.M(1),.T(T),.BINS(BINS),.PIPE(PIPE),.SW(SW)) core
    (.clk(clk),.rst_n(rst_n),.clear(clear),.accept(accept),.last(last),.weights(weights[o*N*8+:N*8]),
     .bits(sample_bits),.input_sign(input_sign),.true_one(true_one),.input_bin(input_bin),
     .update_valid(lane_valid[o]),.update_last(lane_last[o]),.sums(sums[o*BINS*SW+:BINS*SW]));
  end
 end endgenerate
 always @(posedge clk) begin
  if(!rst_n) begin state<=IDLE;accepted<=0;result<=0;end
  else begin
   case(state)
    IDLE: if(clear) begin accepted<=0;state<=RUN;end
    RUN: if(accept) begin accepted<=accepted+1'b1;if(last)state<=DRAIN;end
    CAPTURE: begin result<=sums;state<=OUTPUT;end
    OUTPUT: if(out_ready) state<=IDLE;
    default: begin end
   endcase
   if(update_valid&&update_last) state<=CAPTURE;
  end
 end
endmodule
