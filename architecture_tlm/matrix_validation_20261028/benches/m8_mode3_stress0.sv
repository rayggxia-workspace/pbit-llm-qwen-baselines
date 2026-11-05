`timescale 1ns/1ps
module tb;
localparam N=64,M=8,T=32,F=15,MODE=3,STRESS=0;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,frame_valid=0,sample_valid=0,out_ready=0;
reg [N*M*7-1:0] w_mag7=0;reg [N*M-1:0] w_sign=0;
reg [N-1:0] x_sign=0,sample_bits=0;reg [N*3-1:0] bin_id=0;reg [N*9-1:0] q9=0;
wire frame_ready,sample_ready,out_valid;wire [M*32-1:0] out_sum;
matrix_s3_m8 dut(.*);
reg [N*M*7-1:0] wm[0:F-1];reg [N*M-1:0] ws[0:F-1];reg [N-1:0] xs[0:F-1];
reg [N*3-1:0] bs[0:F-1];reg [N*9-1:0] qs[0:F-1];reg [N-1:0] events[0:F*T-1];
reg [M*32-1:0] expected[0:F-1];
integer f,t,c=0,fc,latency;real start_ns,end_ns,idle_start,idle_end;
always @(posedge clk) c=c+1;
initial begin #2000000; $fatal(1,"timeout");end
initial begin
 $dumpfile("activity.vcd");$dumpvars(0,tb);
 $readmemh("wmag.hex",wm);$readmemh("wsign.hex",ws);$readmemh("xsign.hex",xs);
 $readmemh("bins.hex",bs);$readmemh("q9.hex",qs);$readmemh("samples.hex",events);
 $readmemh("expect3.hex",expected);
 repeat(4) @(negedge clk);rst_n=1;
 // Abort an in-flight frame and reset. A fresh frame must not retain data.
 frame_valid=1;@(negedge clk);frame_valid=0;
 if(MODE<4) begin sample_valid=1;sample_bits=~64'b0;repeat(4) @(negedge clk);end
 rst_n=0;frame_valid=0;sample_valid=0;repeat(3) @(negedge clk);rst_n=1;
 repeat(2) @(negedge clk);start_ns=$realtime;
 for(f=0;f<F;f=f+1) begin
  while(!frame_ready) @(negedge clk);
  w_mag7=wm[f];w_sign=ws[f];x_sign=xs[f];bin_id=bs[f];q9=qs[f];
  frame_valid=1;fc=c;@(negedge clk);frame_valid=0;
  if(MODE<4) begin
   for(t=0;t<T;t=t+1) begin
    if(STRESS && (t%7==3)) begin sample_valid=0;repeat(2) @(negedge clk);end
    while(!sample_ready) @(negedge clk);
    sample_valid=1;sample_bits=events[f*T+t];@(negedge clk);
   end
   sample_valid=0;sample_bits=0;
  end
  while(!out_valid) @(negedge clk);
  latency=c-fc;
  if(out_sum!==expected[f]) $fatal(1,"mismatch frame=%d got=%h expected=%h",f,out_sum,expected[f]);
  if(sample_ready) $fatal(1,"sample_ready while output pending");
  if(STRESS) repeat(3) begin
   @(negedge clk);if(!out_valid || out_sum!==expected[f]) $fatal(1,"stall stability");
  end
  $display("FRAME %0d %0d",f,latency);
  out_ready=1;@(negedge clk);out_ready=0;
 end
 end_ns=$realtime;idle_start=end_ns+20;
 repeat(2) @(negedge clk);
 repeat(64) begin @(negedge clk);if(out_valid || !frame_ready) $fatal(1,"idle handshake");end
 idle_end=$realtime;
 $display("WINDOW active %0.3f %0.3f %0d",start_ns,end_ns,F);
 $display("WINDOW idle %0.3f %0.3f 0",idle_start,idle_end);
 $display("FUNCTION_PASS mode=%0d M=%0d frames=%0d stress=%0d",MODE,M,F,STRESS);
 $finish;
end
endmodule
