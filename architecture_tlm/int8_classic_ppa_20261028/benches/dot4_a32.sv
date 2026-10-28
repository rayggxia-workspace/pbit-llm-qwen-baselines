`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,start=0,en=0;reg[31:0]a=0,b=0;wire ready,valid;wire[31:0]dout;
i8_dot4_a32 dut(.*);reg[63:0]stim[0:575];reg[31:0]expect_mem[0:35];integer frame,g,watch,got=0;time begin_window,begin_frame;
task tick;begin @(negedge clk);end endtask
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expect_mem);$dumpfile("activity.vcd");$dumpvars(0,tb);
 repeat(2)tick;rst_n=1;repeat(4)tick;
 // Abort one partial frame by reset. Stale products must never leak a result.
 start=1;en=1;a=32'h80808080;b=a;tick;start=0;
 repeat(4)begin en=1;tick;end
 rst_n=0;en=0;repeat(2)tick;rst_n=1;repeat(4)begin tick;if(valid!==1'b0)$fatal(1,"aborted frame produced result");end
 for(frame=0;frame<36;frame=frame+1)begin
  if(frame==4||frame==20)begin_window=$time;
  begin_frame=$time;start=1;en=1;tick;start=0;en=0;
  if(ready!==1'b1)$fatal(1,"not ready after start");
  for(g=0;g<16;g=g+1)begin
   if(frame<4 && g%3==0)begin en=0;tick;end
   if(frame<4 && g==7)start=1;else start=0;
   if(ready!==1'b1)$fatal(1,"input not ready");en=1;{a,b}=stim[frame*16+g];tick;
  end
  start=0;en=1;watch=0;
  while(valid!==1'b1)begin tick;watch=watch+1;if(watch>100)$fatal(1,"timeout");end
  if(ready!==1'b0)$fatal(1,"unexpected readiness at final result");
  if(dout!==expect_mem[frame])$fatal(1,"frame=%0d actual=%h expected=%h",frame,dout,expect_mem[frame]);
  got=got+1;$display("FRAME_CYCLES %0d %0d",frame,($time-begin_frame)/10);en=0;tick;
  if(valid!==1'b0)$fatal(1,"duplicate valid");
  if(frame==19)$display("WINDOW matched %0d %0d 16",begin_window,$time);
  if(frame==35)$display("WINDOW fullrange %0d %0d 16",begin_window,$time);
 end
 begin_window=$time;repeat(256)begin tick;if(valid!==1'b0)$fatal(1,"idle result");end
 $display("WINDOW idle %0d %0d 0",begin_window,$time);
 if(got!=36)$fatal(1,"wrong frame count");$display("FUNCTION_PASS transactions=%0d",got);$finish;
end
initial begin #1000000;$fatal(1,"Timeout");end
endmodule
