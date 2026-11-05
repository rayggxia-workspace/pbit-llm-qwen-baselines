`timescale 1ns/1ps
// Same harness for RTL and mapped netlist: compile with -DCASE=0..4.
`ifndef CASE
`define CASE 4
`endif
module tb_activity;
  parameter real PERIOD=10.0;
  reg clk=0, rst_n=0, en=0;
  reg [7:0] r8=0,q8=0;
  reg [8:0] q9=0;
  reg signed [7:0] drive8=0;
  wire bit_o,valid; wire [8:0] lut_out;
  generate
    if(`CASE==0) begin: c
      pbit_compare8_lt dut(r8,q8,bit_o);
    end else if(`CASE==1) begin: c
      pbit_compare8_q256 dut(r8,q9,bit_o);
    end else if(`CASE==2) begin: c
      pbit_sigmoid8_lut dut(drive8,lut_out);
    end else if(`CASE==3) begin: c
      pbit_sigmoid8_reg dut(clk,rst_n,en,drive8,lut_out,valid);
    end else begin: c
      pbit_sample8_reg dut(clk,rst_n,en,drive8,r8,bit_o,valid);
    end
  endgenerate
  always #(PERIOD/2.0) clk=~clk;
  integer f,n,idx,rv,qq,dd,ee,gold,cycles=0,ops=0;
  reg [8:0] held_q=0; reg held_bit=0;
  real start_ns,end_ns;
  initial begin
    f=$fopen("vectors.txt","r");
    if(!f) $fatal(1,"Missing vectors");
    $dumpfile("activity.vcd"); $dumpvars(0,tb_activity.c.dut); $dumpoff;
    repeat(2) @(negedge clk);
    #0.001;
    if(`CASE>=3 && valid !== 0) $fatal(1,"reset valid");
    if(`CASE==3 && lut_out !== 0) $fatal(1,"reset LUT data");
    if(`CASE==4 && bit_o !== 0) $fatal(1,"reset sample data");
    rst_n=1;
    idx=0;
    while(!$feof(f)) begin
      n=$fscanf(f,"%d %d %d %d %d\n",rv,qq,dd,ee,gold);
      if(n!=5) $fatal(1,"Malformed vector %d",idx);
      @(negedge clk);
      if(idx==16) begin start_ns=$realtime; $dumpon; end
      r8=rv; q9=qq;q8=qq;drive8=dd;en=ee;
      @(posedge clk); #(PERIOD/4.0);
      if(ee) begin held_q=gold;held_bit=(rv<gold);end
      if(`CASE==0 && bit_o !== (rv<(qq%256))) $fatal(1,"lt %d",idx);
      if(`CASE==1 && bit_o !== (rv<qq)) $fatal(1,"q256 %d",idx);
      if(`CASE==2 && lut_out !== gold[8:0]) $fatal(1,"lut %d",idx);
      if(`CASE>=3 && valid !== (ee!=0)) $fatal(1,"valid %d",idx);
      if(`CASE==3 && lut_out !== held_q) $fatal(1,"held LUT %d",idx);
      if(`CASE==4 && bit_o !== held_bit) $fatal(1,"held sample %d",idx);
      if(idx>=16) begin cycles=cycles+1;ops=ops+ee;end
      idx=idx+1;
    end
    @(negedge clk);end_ns=$realtime;$dumpoff;
    $display("ACTIVITY_PASS cycles=%0d enabled=%0d start_ns=%0.3f end_ns=%0.3f",cycles,ops,start_ns,end_ns);
    // Recovery check is outside the power window.
    rst_n=0; #(PERIOD/4.0);
    if(`CASE>=3 && valid !== 0) $fatal(1,"recovery valid");
    if(`CASE==3 && lut_out !== 0) $fatal(1,"recovery LUT");
    if(`CASE==4 && bit_o !== 0) $fatal(1,"recovery sample");
    $finish;
  end
endmodule
