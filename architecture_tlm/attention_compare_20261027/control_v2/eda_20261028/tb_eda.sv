`timescale 1ns/1ps
module tb_eda;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,start=0,cfg_ready=0,fair_valid=0,out_ready=0;
 wire start_ready,busy,cfg_valid,fair_ready,out_valid,done,failed;
 wire [8:0] out_index;
`ifdef AC_WINNER
 reg frame_valid=0;
 reg [511:0] candidate_mask=0,frame_bits=0;
 reg [8:0] initial_index=0,fair_word=0;
 reg [31:0] requested_samples=0,burn_updates=0;
 wire frame_ready;
`else
 reg proposal_valid=0;
 reg [8:0] reference_index=0;
 reg [31:0] requested_samples=0,proposal_cap=0;
 reg [511:0] proposal_bits=0;
 reg [23:0] fair_bits_input=0;
 wire proposal_ready;wire [4:0] shift_m;
`endif
 `AC_TOP dut(.*);
 reg [4095:0] vectors,vcd_path;integer fd,rc,cycle=0;
 initial begin
  if($value$plusargs("VCD=%s",vcd_path))begin $dumpfile(vcd_path);$dumpvars(0,tb_eda.dut);end
  if(!$value$plusargs("VECTORS=%s",vectors))$fatal(1,"missing vectors");
  fd=$fopen(vectors,"r");if(!fd)$fatal(1,"cannot open vectors");
  while(!$feof(fd))begin
   @(negedge clk);
`ifdef AC_WINNER
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h\n",rst_n,start,candidate_mask,initial_index,
       requested_samples,burn_updates,cfg_ready,frame_valid,frame_bits,fair_valid,fair_word,out_ready);
   if(rc!=12)$fatal(1,"winner vector fields");
   #1;$display("P %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,start_ready,busy,cfg_valid,
       frame_ready,fair_ready,out_valid,out_index,done,failed);
   @(posedge clk);#1;$display("C %0d %0d %0d %0d %0d %0d",cycle,busy,out_valid,out_index,done,failed);
`else
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h\n",rst_n,start,reference_index,
       requested_samples,proposal_cap,cfg_ready,proposal_valid,proposal_bits,fair_valid,fair_bits_input,out_ready);
   if(rc!=11)$fatal(1,"rejection vector fields");
   #1;$display("P %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",cycle,start_ready,busy,cfg_valid,
       proposal_ready,fair_ready,out_valid,out_index,done,failed,shift_m);
   @(posedge clk);#1;$display("C %0d %0d %0d %0d %0d %0d %0d",cycle,busy,out_valid,out_index,done,failed,shift_m);
`endif
   cycle=cycle+1;
  end
  $fclose(fd);$finish;
 end
endmodule
