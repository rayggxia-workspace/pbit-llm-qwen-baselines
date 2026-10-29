`timescale 1ns/1ps
module tb;
 localparam L=`LANES,MODE=`MODE,G=(MODE==2)?7:1;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,start=0,load_valid=0,out_ready=1,seed_valid=0;
 reg [32*L-1:0] score_in=0;reg [31:0] seed_data=0;
 wire start_ready,load_ready,seed_ready,front_done,out_valid,done,invalid,clipped;
 wire [6:0] out_index;wire [9*L-1:0] out_count;
 `TOP dut(.*);
 reg [31:0] scores[0:1023],seedwords[0:41];reg [8:0] expected[0:1023];reg [1:0] flags[0:7];
 string inputfile,expectfile,seedfile,flagfile;
 integer qi=-1,i,j,cycles=0,checked=0,stall=0,front_cycle=0;
 integer query_start,work_start,work_end,seed_start,seed_end,idle_start;
 reg previous_stall=0;reg [9*L-1:0] previous_data;reg [6:0] previous_index;
 always @(posedge clk) begin
  cycles<=cycles+1;
  if(rst_n) begin
   if(previous_stall && (!out_valid || out_count!==previous_data || out_index!==previous_index))$fatal(1,"backpressure stability");
   previous_stall<=out_valid&&!out_ready;previous_data<=out_count;previous_index<=out_index;
   if(out_valid && out_ready) begin
    if(qi<0 || out_index>=128)$fatal(1,"unexpected output");
    for(integer k=0;k<L;k=k+1)begin
     if(out_count[k*9+:9]!==expected[qi*128+out_index+k])begin
      $display("MISMATCH query=%0d i=%0d got=%0d expected=%0d",qi,out_index+k,out_count[k*9+:9],expected[qi*128+out_index+k]);$fatal(1,"oracle mismatch");
     end
     checked=checked+1;
    end
   end
  end
 end
 always @(negedge clk) begin
  if(front_done)front_cycle=($time-query_start)/10;
  if(stall)out_ready=((cycles%7)!=3 && (cycles%11)!=4);
 end
 initial begin
  if(!$value$plusargs("INPUT=%s",inputfile))$fatal;
  if(!$value$plusargs("EXPECT=%s",expectfile))$fatal;
  if(!$value$plusargs("SEEDS=%s",seedfile))$fatal;
  if(!$value$plusargs("FLAGS=%s",flagfile))$fatal;
  i=$value$plusargs("STALL=%d",stall);
  $readmemh(inputfile,scores);$readmemh(expectfile,expected);$readmemh(seedfile,seedwords);$readmemh(flagfile,flags);
  $dumpfile("activity.vcd");$dumpvars(0,dut);
  repeat(4)@(negedge clk);rst_n=1;
  seed_start=$time;
  if(MODE!=0)begin
   for(i=0;i<6*G;i=i+1)begin
    if(!seed_ready)$fatal(1,"seed not ready");seed_valid=1;seed_data=seedwords[i];@(negedge clk);
   end
   seed_valid=0;seed_data=0;
  end
  while(!start_ready)@(negedge clk);
  seed_end=$time;
  if(MODE!=0)$display("WINDOW seed %0d %0d",seed_start,seed_end);
  work_start=$time;
  for(qi=0;qi<8;qi=qi+1)begin
   while(!start_ready)@(negedge clk);
   query_start=$time;front_cycle=0;start=1;@(negedge clk);start=0;
   for(i=0;i<128;i=i+L)begin
    if(!load_ready)$fatal(1,"load not ready");
    for(j=0;j<L;j=j+1)score_in[j*32+:32]=scores[qi*128+i+j];
    load_valid=1;@(negedge clk);
   end
   load_valid=0;score_in=0;
   while(!done)@(negedge clk);
   if({invalid,clipped}!==flags[qi])$fatal(1,"conversion flags");
   $display("QUERY %0d front_cycles=%0d full_cycles=%0d",qi,front_cycle,($time-query_start)/10);
   if(qi==7)work_end=$time;
   @(negedge clk);
  end
  $display("WINDOW work %0d %0d",work_start,work_end);
  idle_start=$time;repeat(64)@(negedge clk);
  $display("WINDOW idle %0d %0d",idle_start,$time);
  if(checked!=1024)$fatal(1,"wrong response count");
  $display("PASS checked=%0d queries=8",checked);$finish;
 end
 initial begin #5000000;$fatal(1,"timeout");end
endmodule
