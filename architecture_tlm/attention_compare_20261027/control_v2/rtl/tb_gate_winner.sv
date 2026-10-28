`timescale 1ns/1ps
`ifndef AC_TOP
`define AC_TOP win512_g16_p2_o0_e0
`endif
module tb_gate_winner;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,start=0,cfg_ready=0,frame_valid=0,fair_valid=0,out_ready=0;
 reg [511:0] candidate_mask=0,frame_bits=0;
 reg [8:0] initial_index=0,fair_word=0;
 reg [31:0] requested_samples=0,burn_updates=0;
 wire start_ready,busy,cfg_valid,frame_ready,fair_ready,out_valid,done,failed;
 wire [8:0] out_index;
 `AC_TOP dut(.*);
 reg [4095:0] vector_path,vcd_path;integer fd,rc,cycle=0;
 initial begin
  if($value$plusargs("VCD=%s",vcd_path))begin $dumpfile(vcd_path);$dumpvars(0,tb_gate_winner.dut);end
  if(!$value$plusargs("VECTORS=%s",vector_path))$fatal(1,"vectors");
  fd=$fopen(vector_path,"r");if(!fd)$fatal(1,"open");
  while(!$feof(fd))begin
   @(negedge clk);
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h\n",rst_n,start,candidate_mask,initial_index,
       requested_samples,burn_updates,cfg_ready,frame_valid,frame_bits,fair_valid,fair_word,out_ready);
   if(rc!=12)$fatal(1,"fields");
   #1;$display("P %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,start_ready,busy,cfg_valid,
       frame_ready,fair_ready,out_valid,out_index,done,failed);
   @(posedge clk);#1;$display("C %0d %0d %0d %0d %0d %0d",cycle,busy,out_valid,out_index,done,failed);
   cycle=cycle+1;
  end
  $fclose(fd);$finish;
 end
endmodule
