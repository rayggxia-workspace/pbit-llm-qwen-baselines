`timescale 1ns/1ps
module tb;
 localparam W=`RB_W, CMP=`RB_CMP, OW=CMP ? 128 : 128*W;
 reg clk=0,wr_en=0;reg[2:0] wr_group=0;
 reg[16*W-1:0] wr_data=0;reg[128*W-1:0] random_words=0;
 wire[OW-1:0] result;
 `RB_TOP dut(clk,wr_en,wr_group,wr_data,random_words,result);
 integer fd,rc,n,checkit;reg[OW-1:0] expected;
 reg[4095:0] path,wave;
 initial begin
   if(!$value$plusargs("VECTORS=%s",path)) $fatal(1,"missing vectors");
   if($value$plusargs("VCD=%s",wave)) begin $dumpfile(wave);$dumpvars(0,tb);end
   fd=$fopen(path,"r");if(fd==0)$fatal(1,"cannot open vectors");n=0;
   while(!$feof(fd)) begin
     rc=$fscanf(fd,"%h %h %h %h %h %h\n",wr_en,wr_group,wr_data,random_words,checkit,expected);
     if(rc!=6)$fatal(1,"bad vector row");
     #5;clk=1;#1;
     if(checkit && result!==expected)$fatal(1,"Mismatch or X cycle %0d expected=%h got=%h",n,expected,result);
     #4;clk=0;n=n+1;
   end
   $display("PASS cycles=%0d",n);$finish;
 end
endmodule
