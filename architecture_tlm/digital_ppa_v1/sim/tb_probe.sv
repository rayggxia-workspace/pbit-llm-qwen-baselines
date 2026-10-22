`timescale 1ns/1ps
`ifndef KIND
`define KIND 0
`endif
module tb_probe;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,in_valid=0,first=0,last=0;
 reg [2047:0] data_a=0,data_b=0;reg [31:0] aux0=0,aux1=0;
 reg signed [15:0] scale_exp=0;reg [7:0] mean_log2=0;
 wire out_valid;wire [2047:0] result;
 nr_digital_probe #(.KIND(`KIND)) dut(clk,rst_n,in_valid,first,last,data_a,data_b,aux0,aux1,scale_exp,mean_log2,out_valid,result);
 integer fd,rc,cycle=0;reg [4095:0] file_name;
 always @(posedge clk)begin
  cycle=cycle+1;
  if(rst_n&&in_valid)$display("ACCEPT %0d %0d %0d",cycle,first,last);
  #1;
  if(rst_n&&out_valid)begin
   if(^result===1'bx)$fatal(1,"X in valid output");
   $display("RESULT %0d %h",cycle,result);
  end
 end
 initial begin
  if(!$value$plusargs("VECTORS=%s",file_name))$fatal(1,"VECTORS required");
  fd=$fopen(file_name,"r");if(!fd)$fatal(1,"vector open failed");
  repeat(3)@(negedge clk);rst_n=1;
  while(!$feof(fd))begin
   @(negedge clk);
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h\n",in_valid,first,last,data_a,data_b,aux0,aux1,scale_exp,mean_log2);
   if(rc!=9&&!$feof(fd))$fatal(1,"malformed vector");
  end
  @(negedge clk);in_valid=0;first=0;last=0;
  repeat(20)@(negedge clk);$fclose(fd);$finish;
 end
endmodule
