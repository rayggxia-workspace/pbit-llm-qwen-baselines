`timescale 1ns/1ps
module tb_rng_service;
 parameter integer KIND=0;
 parameter [31:0] RESEED_CYCLES=37;
 localparam integer LANES=(KIND==1 ? 64 : KIND==2 ? 20 : 1);
 localparam integer SW=(KIND==2 ? 177 : 32);
 reg clk=0;
 always #5 clk=~clk;
 reg rst_n=0,req_valid=0,rsp_ready=1,word_valid=0,qualified=1;
 reg [31:0] word_data=0;
 reg [1:0] command=0;
 reg [LANES*9-1:0] thresholds=0;
 wire req_ready,rsp_valid,word_ready,cmd_ready,seed_req,seed_error,fault;
 wire [LANES*8-1:0] words;
 wire [LANES-1:0] bits;
 rng_seeded_top #(.KIND(KIND),.RESEED_CYCLES(RESEED_CYCLES)) dut(
 .clk(clk),.rst_n(rst_n),.word_valid(word_valid),.word_ready(word_ready),.word_data(word_data),
 .qualified(qualified),.entropy_fault(fault),.req_valid(req_valid),.req_ready(req_ready),
 .thresholds(thresholds),.rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.words(words),.bits(bits),
 .command(command),.cmd_ready(cmd_ready),.seed_req(seed_req),.seed_error(seed_error));
 reg er,ec,ew,es,ev,ef,ee,el,eseeded;
 reg [LANES*8-1:0] ewords;
 reg [LANES-1:0] ebits;
 reg [31:0] eepoch,eage;
 reg [SW-1:0] estate;
 reg [3:0] ewarm;
 integer a,b,n=0,fi,fe;
 reg [4095:0] stim_file,expected_file,vcd_file;
 initial begin
   if (!$value$plusargs("STIM=%s",stim_file)) $fatal(1,"missing STIM");
   if (!$value$plusargs("EXPECTED=%s",expected_file)) $fatal(1,"missing EXPECTED");
   if ($value$plusargs("VCD=%s",vcd_file)) begin $dumpfile(vcd_file);$dumpvars(0,dut);end
   fi=$fopen(stim_file,"r");fe=$fopen(expected_file,"r");
   if (!fi || !fe) $fatal(1,"vector file not found");
   while (!$feof(fi)) begin
     @(negedge clk);
     a=$fscanf(fi,"%h %h %h %h %h %h %h %h\n",rst_n,req_valid,rsp_ready,command,
                  word_valid,word_data,qualified,thresholds);
     b=$fscanf(fe,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                  er,ec,ew,es,ev,ewords,ebits,ef,ee,eepoch,estate,ewarm,el,eage,eseeded);
     if(a!=8 || b!=15) $fatal(1,"truncated vector at %0d",n);
     #1;
     // Async reset can change combinational ready before the edge; compare only active cycles.
     if(rst_n && {req_ready,cmd_ready,word_ready,seed_req} !== {er,ec,ew,es})
       $fatal(1,"ready mismatch edge %0d got %b expected %b",n,
                 {req_ready,cmd_ready,word_ready,seed_req},{er,ec,ew,es});
     @(posedge clk);#1;
     if ({rsp_valid,words,bits,fault,seed_error} !== {ev,ewords,ebits,ef,ee})
       $fatal(1,"output mismatch edge %0d",n);
     if ({dut.endpoint.epoch,dut.endpoint.state,dut.endpoint.warm_left,dut.endpoint.epoch_locked,
          dut.endpoint.age,dut.endpoint.seeded} !== {eepoch,estate,ewarm,el,eage,eseeded})
       $fatal(1,"state mismatch edge %0d",n);
     n=n+1;
   end
   if(!$feof(fe)) $fatal(1,"unexpected extra oracle rows");
   $display("PASS edges=%0d",n);$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
