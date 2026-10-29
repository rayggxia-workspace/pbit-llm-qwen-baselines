`timescale 1ns/1ps
module tb;
reg clk=0;always #5 clk=~clk;reg rst_n=0,en=0;reg[511:0]a=0,b=0;wire valid;wire[31:0]dout;
i8_par64_a32 dut(.*);reg[1023:0]stim[0:163];reg[31:0]expect_mem[0:163];integer i,got=0,sent=0;time begin_window;
task tick;begin @(negedge clk);end endtask
task send;input integer idx;begin en=1;{a,b}=stim[idx];sent=sent+1;tick;end endtask
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expect_mem);$dumpfile("activity.vcd");$dumpvars(0,tb);
 repeat(2)tick;rst_n=1;repeat(2)tick;
 for(i=0;i<4;i=i+1)begin send(i);en=0;repeat(2)tick;end
 // Assert actual reset with input-enable high; this input is not a transaction.
 rst_n=0;en=1;tick;en=0;tick;rst_n=1;repeat(2)tick;
 begin_window=$time;
 for(i=4;i<132;i=i+1)send(i);
 en=0;$display("WINDOW peak %0d %0d 128",begin_window,$time);repeat(2)tick;
 begin_window=$time;
 for(i=132;i<148;i=i+1)begin send(i);en=0;repeat(34)tick;end
 $display("WINDOW paced %0d %0d 16",begin_window,$time);
 begin_window=$time;
 for(i=148;i<164;i=i+1)send(i);
 en=0;$display("WINDOW fullrange %0d %0d 16",begin_window,$time);repeat(2)tick;
 begin_window=$time;repeat(256)tick;$display("WINDOW idle %0d %0d 0",begin_window,$time);
 if(got!=164||sent!=164)$fatal(1,"count got=%0d sent=%0d",got,sent);
 $display("FUNCTION_PASS transactions=%0d",got);$finish;
end
always @(posedge clk)begin #1;
 if(rst_n)begin
  if(valid!==en)$fatal(1,"valid/X mismatch");
  if(valid)begin
   if(got>=164||dout!==expect_mem[got])$fatal(1,"result idx=%0d actual=%h expected=%h",got,dout,expect_mem[got]);
   got=got+1;
  end
 end else if(valid!==1'b0)$fatal(1,"reset valid");
end
initial begin #1000000;$fatal(1,"Timeout");end
endmodule
