`timescale 1ns/1ps
module tb_winner;
 parameter integer N=64,GROUP=8,PREP_STAGES=2,STREAM=1,WINNER_ONEHOT=0,RANK_CAP=8,EARLY_HOLD=0;
 localparam AW=$clog2(N);
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,start=0,cfg_ready=0,frame_valid=0,fair_valid=0,out_ready=0;
 reg [N-1:0] candidate_mask=0,frame_bits=0;
 reg [AW-1:0] initial_index=0,fair_word=0;
 reg [31:0] requested_samples=0,burn_updates=0;
 wire start_ready,busy,cfg_valid,frame_ready,fair_ready,out_valid,done,failed;
 wire [AW-1:0] out_index,winner_index;
 wire [31:0] issued,committed,consumed,holds,switches,fair_words,fair_bits,rank_retries;
 ac_winner #(.N(N),.GROUP(GROUP),.PREP_STAGES(PREP_STAGES),.STREAM(STREAM),
             .WINNER_ONEHOT(WINNER_ONEHOT),.RANK_CAP(RANK_CAP),.EARLY_HOLD(EARLY_HOLD)) dut(.*);
 reg [4095:0] vector_path,vcd_path;integer fd,rc,cycle=0;
 initial begin
  if($value$plusargs("VCD=%s",vcd_path))begin $dumpfile(vcd_path);$dumpvars(0,tb_winner.dut);end
  if(!$value$plusargs("VECTORS=%s",vector_path))$fatal(1,"vectors");
  fd=$fopen(vector_path,"r");if(!fd)$fatal(1,"open vectors");
  while(!$feof(fd))begin
   @(negedge clk);
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h\n",rst_n,start,candidate_mask,initial_index,
       requested_samples,burn_updates,cfg_ready,frame_valid,frame_bits,fair_valid,fair_word,out_ready);
   if(rc!=12)$fatal(1,"fields %d",rc);
   #1;
   $display("P %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,start_ready,busy,cfg_valid,
       frame_ready,fair_ready,out_valid,out_index,done,failed,winner_index);
   @(posedge clk);#1;
   $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,
       busy,out_valid,out_index,done,failed,winner_index,issued,committed,consumed,holds,switches,
       fair_words,fair_bits,rank_retries);
   cycle=cycle+1;
  end
  $fclose(fd);$finish;
 end
endmodule
