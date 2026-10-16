`timescale 1ns/1ps
module tb_accum;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,valid=0,first=0,last=0;
 reg signed [31:0] count=0;reg [23:0] coef=0;
 reg signed [15:0] ce=0,common=0;
 wire [31:0] result[0:3];wire [3:0] flags[0:3];wire ov[0:3];
 fc_accum_probe #(.FIXED(0)) f(clk,rst_n,valid,first,last,count,coef,ce,common,ov[0],result[0],flags[0]);
 fc_accum_probe #(.ACC_W(32)) a(clk,rst_n,valid,first,last,count,coef,ce,common,ov[1],result[1],flags[1]);
 fc_accum_probe #(.ACC_W(40)) b(clk,rst_n,valid,first,last,count,coef,ce,common,ov[2],result[2],flags[2]);
 fc_accum_probe #(.ACC_W(64)) c(clk,rst_n,valid,first,last,count,coef,ce,common,ov[3],result[3],flags[3]);
 reg [31:0] expected[0:3];reg [3:0] ef[0:3];
 integer fd,rc,j,n=0,frames=0;
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  fd=$fopen("vectors/accum.hex","r");if(!fd)$fatal(1,"no accum vectors");
  while(!$feof(fd)) begin
   @(negedge clk);
   rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
    first,last,count,coef,ce,common,expected[0],ef[0],expected[1],ef[1],expected[2],ef[2],expected[3],ef[3]);
   if(rc==14) begin
    valid=1;@(negedge clk);valid=0;
    @(posedge clk);#1;
    for(j=0;j<4;j=j+1) begin
     if(ov[j]!==last)$fatal(1,"accum valid mismatch");
     if(last&&(result[j]!==expected[j]||flags[j]!==ef[j]))
      $fatal(1,"accum frame=%0d impl=%0d got=%h/%h expected=%h/%h",frames,j,result[j],flags[j],expected[j],ef[j]);
    end
    if(last)frames=frames+1;n=n+1;
   end
  end
  $fclose(fd);$display("ACCUM_PASS %0d frames %0d partials",frames,n);$finish;
 end
endmodule
