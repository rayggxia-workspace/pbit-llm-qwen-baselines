`timescale 1ns/1ps
`ifndef KIND
`define KIND 0
`endif
module tb_power;
 parameter real HALF_PERIOD_NS=5.0;
 reg clk=0;always #(HALF_PERIOD_NS)clk=~clk;
 reg rst_n=0,in_valid=0,first=0,last=0;
 reg [2047:0] data_a=0,data_b=0;reg [31:0] aux0=32'h3d800000,aux1=32'h358637bd;
 reg signed [15:0] scale_exp=0;reg [7:0] mean_log2=4;
 wire out_valid;wire [2047:0] result;
`ifdef GATE
 nr_digital_probe_mapped dut(clk,rst_n,in_valid,first,last,data_a,data_b,aux0,aux1,scale_exp,mean_log2,out_valid,result);
`else
 nr_digital_probe #(.KIND(`KIND)) dut(clk,rst_n,in_valid,first,last,data_a,data_b,aux0,aux1,scale_exp,mean_log2,out_valid,result);
`endif
 integer mode=1,cycles=4096,seed=20261022,i,j,inputs=0,outputs=0,logical_input=0,fd;
 reg measuring=0;reg [31:0] state=20261022,word;reg [4095:0] vcd_name;
 real start_ns,end_ns;
 function automatic [31:0] advance(input [31:0] value);
  reg [31:0] t;begin t=value^(value<<13);t=t^(t>>17);advance=t^(t<<5);end
 endfunction
 function automatic [31:0] finite_value(input [31:0] value);
  reg [7:0] exponent;begin exponent=125+value[3:2];finite_value={value[31],exponent,value[22:0]};end
 endfunction
 always @(posedge clk)begin
  if(rst_n&&measuring&&in_valid)inputs=inputs+1;
  #1;
  if(rst_n&&measuring&&out_valid)begin
   if(^result===1'bx)$fatal(1,"valid output X");outputs=outputs+1;
  end
 end
 initial begin
  if($value$plusargs("MODE=%d",mode))begin end
  if($value$plusargs("CYCLES=%d",cycles))begin end
  if($value$plusargs("SEED=%d",seed))begin end
  if(!$value$plusargs("VCD=%s",vcd_name))vcd_name="power.vcd";
  if(mode<0||mode>2||cycles<128||cycles%128!=0)$fatal(1,"MODE0/1/2 and CYCLES positive multiple128 required");
  state=seed;if(state==0)state=1;
  $dumpfile(vcd_name);$dumpvars(0,tb_power);
  repeat(3)@(negedge clk);rst_n=1;
  for(i=0;i<cycles;i=i+1)begin
   @(negedge clk);
   if(i==0)begin start_ns=$realtime;measuring=1;end
   in_valid=(mode==1)||(mode==2&&i%64<16);
   first=logical_input%16==0;last=logical_input%16==15;
   data_a=0;data_b=0;
   for(j=0;j<64;j=j+1)begin
    state=advance(state);word=finite_value(state);
    if(`KIND==4)data_a[j*16+:16]=word[31:16];else data_a[j*32+:32]=word;
    state=advance(state);data_b[j*32+:32]=finite_value(state);
   end
   if(`KIND==2||`KIND==3||`KIND==8||`KIND==9||`KIND==10)begin
    data_a[15:0]=finite_value(state)>>16;state=advance(state);data_b[15:0]=finite_value(state)>>16;
   end
   if(`KIND==6||`KIND==22)begin
    data_a=0;for(j=0;j<64;j=j+1)begin state=advance(state);data_a[j*12+:12]=state%2049;end
    aux0=32'h3c800000|state[18:0];scale_exp=(logical_input%12)-6;
   end
   if(`KIND==11)data_a[31]=1;
   if(`KIND==16)begin
    first=logical_input%32==0;last=logical_input%32==31;data_a=33'h008000000;
    aux0=32'h04567890;
   end
   if(`KIND==17)begin
    data_a=0;data_b={2048{1'b1}};
    if(logical_input%4!=0)data_a[state%512]=1;
    if(logical_input%4==2)data_a[(state+31)%512]=1;
   end
   if(`KIND==20)begin data_a[31:0]={16'h3f00,16'hbf00};aux0=32'h3f3504f3;aux1=32'h3f3504f3;end
   if(in_valid)logical_input=logical_input+1;
  end
  @(negedge clk);in_valid=0;first=0;last=0;
  repeat(32)@(negedge clk);end_ns=$realtime;measuring=0;
  if(mode==0&&(inputs!=0||outputs!=0))$fatal(1,"idle activity");
  if(mode!=0&&outputs==0)$fatal(1,"no completed output");
  fd=$fopen("window.txt","w");
  $fdisplay(fd,"start_ns=%0.3f",start_ns);$fdisplay(fd,"end_ns=%0.3f",end_ns);
  $fdisplay(fd,"inputs=%0d",inputs);$fdisplay(fd,"outputs=%0d",outputs);$fdisplay(fd,"mode=%0d",mode);
  $fclose(fd);
  $display("PASS power KIND=%0d MODE=%0d inputs=%0d outputs=%0d window_ns=%0.3f",`KIND,mode,inputs,outputs,end_ns-start_ns);$finish;
 end
endmodule
