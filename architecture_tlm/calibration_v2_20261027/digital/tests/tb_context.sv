`timescale 1ns/1ps
module tb_context;
 reg clk=0,rst_n=0,clear=0,in_valid=0,out_ready=0;
 reg [3:0] in_context=0;reg [15:0] a=0,b=0;
 wire in_ready,out_valid;wire [3:0] out_context;wire [31:0] y;wire [4:0] status,occupancy;wire [15:0] busy_mask;
`ifdef SINGLE_CONTEXT
 dig_bf16_accum dut(.clk(clk),.rst_n(rst_n),.clear(clear),.in_valid(in_valid),.in_ready(in_ready),.a(a),.b(b),.out_valid(out_valid),.out_ready(out_ready),.y(y),.status(status));
 assign out_context=0;assign occupancy=0;assign busy_mask=0;
`else
 dig_bf16_context16 dut(.clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(in_ready),.in_context(in_context),.a(a),.b(b),.out_valid(out_valid),.out_ready(out_ready),.out_context(out_context),.y(y),.status(status),.busy_mask(busy_mask),.occupancy(occupancy));
`endif
 real period_ns=10.0;
 integer input_file,output_file,ret,cycles,cycle,rv,cl,iv,orr,ct;
 integer window_start=3,window_end=-1,window_frames=0,window_accepted=0;
 reg [15:0] av,bv;reg [4095:0] vector_file,output_path,vcd_file;
 initial begin ret=$value$plusargs("PERIOD_NS=%f",period_ns);forever #(period_ns/2.0)clk=~clk;end
 initial begin
  if(!$value$plusargs("VECTORS=%s",vector_file))$fatal(1,"VECTORS required");
  if(!$value$plusargs("OUTPUT=%s",output_path))$fatal(1,"OUTPUT required");
  if($value$plusargs("VCD=%s",vcd_file))begin $dumpfile(vcd_file);$dumpvars(0,tb_context);end
  input_file=$fopen(vector_file,"r");output_file=$fopen(output_path,"w");
  if(input_file==0||output_file==0)$fatal(1,"file failure");ret=$fscanf(input_file,"%d\n",cycles);
  ret=$value$plusargs("WSTART_CYCLE=%d",window_start);ret=$value$plusargs("WEND_CYCLE=%d",window_end);if(window_end<0)window_end=cycles;
  for(cycle=0;cycle<cycles;cycle=cycle+1)begin
   @(negedge clk);ret=$fscanf(input_file,"%d %d %d %d %d %h %h\n",rv,cl,iv,orr,ct,av,bv);
   if(ret!=7)$fatal(1,"bad vector");rst_n=rv;clear=cl;in_valid=iv;out_ready=orr;in_context=ct;a=av;b=bv;
   @(posedge clk);$fdisplay(output_file,"%0d %b %b %b %b %h %h %h %h %h",cycle,rst_n,in_ready,out_valid,out_ready,out_context,y,status,busy_mask,occupancy);
   if(cycle>=window_start&&cycle<window_end&&rst_n)begin if(in_valid&&in_ready)window_accepted=window_accepted+1;if(out_valid&&out_ready)window_frames=window_frames+1;end
  end
  @(negedge clk);$fclose(input_file);$fclose(output_file);$display("DIGITAL_DONE %0d",cycles);
  $display("WINDOW start_ns=%0.3f end_ns=%0.3f frames=%0d accepted_samples=%0d",(window_start+1)*period_ns,(window_end+1)*period_ns,window_frames,window_accepted);$finish;
 end
endmodule
