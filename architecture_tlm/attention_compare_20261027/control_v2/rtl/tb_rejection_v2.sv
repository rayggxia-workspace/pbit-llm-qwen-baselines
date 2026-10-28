`timescale 1ns/1ps
module tb_rejection_v2;
 parameter integer N=64,PREFETCH_FAIR=0,LEVELS_PER_STAGE=2;
 localparam AW=$clog2(N);
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,start=0,cfg_ready=0,proposal_valid=0,fair_valid=0,out_ready=0;
 reg [AW-1:0] reference_index=0;
 reg [31:0] requested_samples=0,proposal_cap=0;
 reg [N-1:0] proposal_bits=0;
 reg [23:0] fair_bits_input=0;
 wire start_ready,busy,cfg_valid,proposal_ready,fair_ready,out_valid,done,failed;
 wire [4:0] shift_m;wire [AW-1:0] out_index;
 wire [31:0] proposals,accepted,consumed,rejected_multi,rejected_empty,fair_words,fair_bits;
 ac_rejection #(.N(N),.PREFETCH_FAIR(PREFETCH_FAIR),.LEVELS_PER_STAGE(LEVELS_PER_STAGE)) dut(.*);
 integer fd,rc,cycle=0;reg [4095:0] vectors,vcd_path;
 initial begin
  if($value$plusargs("VCD=%s",vcd_path))begin $dumpfile(vcd_path);$dumpvars(0,tb_rejection_v2.dut);end
  if(!$value$plusargs("VECTORS=%s",vectors))$fatal(1,"vectors");
  fd=$fopen(vectors,"r");if(!fd)$fatal(1,"open vectors");
  while(!$feof(fd))begin
   @(negedge clk);
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h\n",rst_n,start,reference_index,
        requested_samples,proposal_cap,cfg_ready,proposal_valid,proposal_bits,fair_valid,fair_bits_input,out_ready);
   if(rc!=11)$fatal(1,"fields");
   @(posedge clk);#1;
   $display("C %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
      cycle,dut.state,shift_m,start_ready,busy,cfg_valid,proposal_ready,fair_ready,out_valid,out_index,
      done,failed,proposals,accepted,consumed,rejected_multi,rejected_empty,fair_words,fair_bits);
   cycle=cycle+1;
  end
  $fclose(fd);$finish;
 end
endmodule
