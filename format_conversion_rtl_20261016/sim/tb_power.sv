`timescale 1ns/1ps
`ifndef KIND
 `define KIND 0
`endif
`ifndef FIXED
 `define FIXED 1
`endif
`ifndef ACC_W
 `define ACC_W 64
`endif
module tb_power;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,in_valid=0,first=0,last=0;
 reg [63:0] data=0;reg [31:0] aux=0;reg [23:0] coefficient=0;
 reg signed [15:0] ea=0,eb=0;
 wire out_valid;wire [3:0] flags;wire [63:0] result;
`ifdef ACCUM
 wire [31:0] result32;
 fc_accum_probe
 `ifndef GATE
 #(.FIXED(`FIXED),.ACC_W(`ACC_W))
 `endif
 dut(clk,rst_n,in_valid,first,last,data[31:0],coefficient,ea,eb,out_valid,result32,flags);
 assign result={32'b0,result32};
`else
 fc_conversion_probe
 `ifndef GATE
 #(.KIND(`KIND))
 `endif
 dut(clk,rst_n,in_valid,data,aux,coefficient,ea,eb,out_valid,result,flags);
`endif
 integer fd,window_file,rc,mode=1,cycles=10000,i,wp=0,rp=0,accepted=0,completed=0;
 reg [1023:0] vector_path;
 reg [63:0] exp_value,other_value[0:2],queue_data[0:15];
 reg [3:0] exp_flags,other_flags[0:2],queue_flags[0:15];
 reg measuring=0;
 time start_time,end_time;
 always @(posedge clk) begin
  #2;
  if(rst_n&&out_valid) begin
   if(rp>=wp)$fatal(1,"unexpected output");
   if(result!==queue_data[rp%16]||flags!==queue_flags[rp%16])
    $fatal(1,"power bench mismatch n=%0d got=%h/%h expected=%h/%h",rp,result,flags,queue_data[rp%16],queue_flags[rp%16]);
   rp=rp+1;if(measuring)completed=completed+1;
  end
 end
 initial begin
  if($value$plusargs("MODE=%d",mode)) begin end
  if($value$plusargs("CYCLES=%d",cycles)) begin end
  if(!$value$plusargs("VECTORS=%s",vector_path))$fatal(1,"pass +VECTORS=...");
  fd=$fopen(vector_path,"r");if(!fd)$fatal(1,"no power vectors");
  $dumpfile("power.vcd");$dumpvars(0,dut);
  repeat(4)@(negedge clk);rst_n=1;repeat(4)@(negedge clk);
  start_time=$time;measuring=1;
  for(i=0;i<cycles;i=i+1) begin
   in_valid=(mode==1)||((mode==2)&&(i%16==0));
   if(in_valid) begin
    if($feof(fd))begin $fclose(fd);fd=$fopen(vector_path,"r");end
`ifdef ACCUM
    rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",first,last,data,aux,coefficient,ea,eb,
     exp_value,exp_flags,other_value[0],other_flags[0],other_value[1],other_flags[1],other_value[2],other_flags[2]);
    if(rc!=15)$fatal(1,"malformed accum power vector rc=%0d",rc);
    if(`FIXED) begin
     if(`ACC_W==32)begin exp_value=other_value[0];exp_flags=other_flags[0];end
     else if(`ACC_W==40)begin exp_value=other_value[1];exp_flags=other_flags[1];end
     else begin exp_value=other_value[2];exp_flags=other_flags[2];end
    end
    if(last)begin queue_data[wp%16]=exp_value;queue_flags[wp%16]=exp_flags;wp=wp+1;end
`else
    rc=$fscanf(fd,"%h %h %h %h %h %h %h %h %h\n",first,last,data,aux,coefficient,ea,eb,exp_value,exp_flags);
    if(rc!=9)$fatal(1,"malformed conversion power vector");
    queue_data[wp%16]=exp_value;queue_flags[wp%16]=exp_flags;wp=wp+1;
`endif
    accepted=accepted+1;
   end
   @(negedge clk);
  end
  in_valid=0;repeat(4)@(negedge clk);end_time=$time;measuring=0;
  if(wp!=rp)$fatal(1,"undrained output queue");
  window_file=$fopen("window.txt","w");$fdisplay(window_file,"%0d %0d",start_time,end_time);$fclose(window_file);
  $display("POWER_STIMULUS_PASS mode=%0d accepted=%0d outputs=%0d start_ns=%0d end_ns=%0d",mode,accepted,completed,start_time,end_time);
  $fclose(fd);$finish;
 end
endmodule
