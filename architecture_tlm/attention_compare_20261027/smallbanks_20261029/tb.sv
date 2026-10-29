`timescale 1ns/1ps
module tb;
  reg clk=0,write_en=0;
  reg [895:0] bit_addr=0;
  reg [255:0] write_data=0;
  wire [127:0] sample;
  reg [127:0] oracle[0:127];
  reg [127:0] expected;
  integer seed,prob,n,b,a,k,ignored,checks=0;
  banks dut(clk,write_en,bit_addr,write_data,sample);
  always #5 clk=~clk;
  initial begin
    if (!$value$plusargs("SEED=%d",seed)) $fatal(1,"missing seed");
    if (!$value$plusargs("PROB32=%d",prob)) $fatal(1,"missing probability");
    ignored=$urandom(seed);
    $dumpfile("activity.vcd");$dumpvars(0,tb.dut);
    // 64 physical writes/bank. Upstream provides 256 bits per cycle.
    for(n=0;n<64;n=n+1) begin
      @(negedge clk);write_en=1;
      for(b=0;b<128;b=b+1) begin
        bit_addr[b*7 +: 7]=2*n;
        for(k=0;k<2;k=k+1) begin
          oracle[b][2*n+k]=(($urandom % 32)<prob);
          write_data[2*b+k]=oracle[b][2*n+k];
        end
      end
    end
    // All 128 positions, followed by independent random addresses in each bank.
    for(n=0;n<256;n=n+1) begin
      @(negedge clk);write_en=0;
      for(b=0;b<128;b=b+1) begin
        a=(n<128)?n:($urandom % 128);
        bit_addr[b*7 +: 7]=a;
        expected[b]=oracle[b][a];
      end
      @(posedge clk);#4;
      if(sample !== expected) $fatal(1,"mismatch frame=%0d got=%h expected=%h",n,sample,expected);
      checks=checks+1;
    end
    #1;$display("PASS frames=%0d checked_bits=%0d",checks,checks*128);$finish;
  end
endmodule
