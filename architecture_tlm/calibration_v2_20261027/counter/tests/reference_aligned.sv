`timescale 1ns/1ps
// Simulation equivalence wrapper. Old per-bin outputs aligned once without rounding.
module reference_aligned #(parameter N=64,M=1,BINS=4,T=64,
 parameter CW=1+$clog2(N*127*T+1), AW=CW+2*(BINS-1))(
 input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [N*M*7-1:0] w_mag7,input wire [N*M-1:0] w_sign,
 input wire [N-1:0] x_sign,input wire [N*3-1:0] bin_id,
 input wire [N-1:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [M*AW-1:0] out_sum);
 wire [M*BINS*CW-1:0] counts;
 ffn_counter #(.N(N),.M(M),.BINS(BINS),.T(T),.CW(CW)) old(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),
 .w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),.bin_id(bin_id),
 .sample_bits(sample_bits),.sample_valid(sample_valid),.sample_ready(sample_ready),
 .out_valid(out_valid),.out_ready(out_ready),.out_counts(counts));
 genvar m;
 generate for(m=0;m<M;m=m+1) begin:out_lane
   integer b; reg signed [AW-1:0] total; reg signed [CW-1:0] v;
   reg signed [AW-1:0] ext;
   always @* begin
     total=0;v=0;ext=0;
     for(b=0;b<BINS;b=b+1) begin
       v=$signed(counts[(m*BINS+b)*CW+:CW]);
       ext={{(AW-CW){v[CW-1]}},v};
       total=total+(ext<<<(2*(BINS-1-b)));
     end
   end
   assign out_sum[m*AW+:AW]=total;
 end endgenerate
endmodule
