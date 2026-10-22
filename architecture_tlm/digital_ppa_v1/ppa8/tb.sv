`timescale 1ns/1ps
`ifndef KIND
`define KIND 0
`endif
module tb_ppa;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0,in_valid=0,first=0,last=0;
 reg [2047:0] data_a=0,data_b=0;
 reg [31:0] aux0=0,aux1=0;
 reg signed [15:0] scale_exp=0;
 reg [7:0] mean_log2=0;
 wire out_valid; wire [2047:0] result;
`ifdef GATE
 nr_digital_probe_mapped dut(clk,rst_n,in_valid,first,last,data_a,data_b,aux0,aux1,scale_exp,mean_log2,out_valid,result);
`else
 nr_digital_probe #(.KIND(`KIND)) dut(clk,rst_n,in_valid,first,last,data_a,data_b,aux0,aux1,scale_exp,mean_log2,out_valid,result);
`endif
 integer fd,gd,rc,i,nrows,nout,received=0,accepted=0,countfd;
 reg [4095:0] vectors,gold,vcd;
 reg [2047:0] expected;
 always @(posedge clk) begin
  if(rst_n&&in_valid) accepted=accepted+1;
  #1;
  if(rst_n) begin
   if(out_valid!==1'b0 && out_valid!==1'b1) $fatal(1,"Unknown out_valid");
   if(out_valid) begin
    rc=$fscanf(gd,"%h\n",expected);
    if(rc!=1 || result!==expected) $fatal(1,"Mismatch output=%0d actual=%h expected=%h",received,result,expected);
    received=received+1;
   end
  end
 end
 initial begin
  if(!$value$plusargs("VECTORS=%s",vectors) || !$value$plusargs("GOLD=%s",gold) ||
     !$value$plusargs("ROWS=%d",nrows) || !$value$plusargs("OUTPUTS=%d",nout)) $fatal(1,"Missing arguments");
  fd=$fopen(vectors,"r");gd=$fopen(gold,"r");
  if(!fd||!gd||nrows<=0||nout<=0) $fatal(1,"Input file/size invalid");
  if($value$plusargs("VCD=%s",vcd)) begin
   $dumpfile(vcd);
`ifdef GATE
   `include "dump_scopes.svh"
`else
   $dumpvars(0,dut);
`endif
  end
  repeat(4) @(negedge clk);
  rst_n=1;
  // First vector at 50ns, accepted at 55ns; no testbench/clock race.
  for(i=0;i<nrows;i=i+1) begin
   @(negedge clk);
   if($fscanf(fd,"%h %h %h %h %h %h %h %h %h\n",in_valid,first,last,data_a,data_b,aux0,aux1,scale_exp,mean_log2)!=9)
    $fatal(1,"Malformed vector row %0d",i);
  end
  @(negedge clk); in_valid=0;first=0;last=0;
  repeat(20) @(negedge clk);
  if(received!=nout) $fatal(1,"Missing output: %0d != %0d",received,nout);
  if($fscanf(gd,"%h",expected)==1) $fatal(1,"Unused expected output");
  countfd=$fopen("counts.txt","w");
  $fdisplay(countfd,"inputs=%0d\noutputs=%0d",accepted,received);$fclose(countfd);
  $display("DIGITAL_PPA_PASS inputs=%0d outputs=%0d",accepted,received);
  $finish;
 end
 initial begin #1000000; $fatal(1,"Watchdog"); end
endmodule
