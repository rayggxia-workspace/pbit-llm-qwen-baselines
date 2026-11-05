`timescale 1ns/1ps
`ifndef DIG_TOP
 `define DIG_TOP dig_fp32_add
`endif
module tb_digital;
 reg clk=0,rst_n=0,in_valid=0,out_ready=0;
 reg [31:0] a=0,b=0;
 wire in_ready,out_valid;wire [31:0] y;wire [4:0] status;
 `DIG_TOP dut(.*);
 real period_ns=10.0;
 integer input_file,output_file,ret,cycles,cycle;
 integer rv,iv,orr,window_start=3,window_end=-1,window_frames=0,window_accepted=0;
 reg [31:0] av,bv;
 reg [4095:0] vector_file,output_path,vcd_file;
 initial begin
  ret=$value$plusargs("PERIOD_NS=%f",period_ns);
  forever #(period_ns/2.0) clk=~clk;
 end
 initial begin
  if(!$value$plusargs("VECTORS=%s",vector_file)) $fatal(1,"VECTORS required");
  if(!$value$plusargs("OUTPUT=%s",output_path)) $fatal(1,"OUTPUT required");
  if($value$plusargs("VCD=%s",vcd_file)) begin $dumpfile(vcd_file);$dumpvars(0,tb_digital);end
  input_file=$fopen(vector_file,"r");output_file=$fopen(output_path,"w");
  if(input_file==0||output_file==0)$fatal(1,"file open failure");
  ret=$fscanf(input_file,"%d\n",cycles);
  ret=$value$plusargs("WSTART_CYCLE=%d",window_start);ret=$value$plusargs("WEND_CYCLE=%d",window_end);
  if(window_end<0)window_end=cycles;
  for(cycle=0;cycle<cycles;cycle=cycle+1)begin
   @(negedge clk);
   ret=$fscanf(input_file,"%d %d %d %h %h\n",rv,iv,orr,av,bv);
   if(ret!=5)$fatal(1,"bad vector");
   rst_n=rv;in_valid=iv;out_ready=orr;a=av;b=bv;
   @(posedge clk);
   $fdisplay(output_file,"%0d %b %b %b %b %08h %02h",cycle,rst_n,in_ready,out_valid,out_ready,y,status);
   if(cycle>=window_start&&cycle<window_end&&rst_n)begin
    if(in_valid&&in_ready)window_accepted=window_accepted+1;
    if(out_valid&&out_ready)window_frames=window_frames+1;
   end
  end
  @(negedge clk);$fclose(input_file);$fclose(output_file);$display("DIGITAL_DONE %0d",cycles);
  $display("WINDOW start_ns=%0.3f end_ns=%0.3f frames=%0d accepted_samples=%0d",(window_start+1)*period_ns,(window_end+1)*period_ns,window_frames,window_accepted);$finish;
 end
endmodule
