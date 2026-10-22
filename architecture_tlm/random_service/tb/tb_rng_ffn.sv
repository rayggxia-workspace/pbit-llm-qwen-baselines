`timescale 1ns/1ps
module tb_rng_ffn;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,word_valid=0,req_valid=0,rsp_ready=1;
 reg [31:0] word_data=32'hb1234567;
 reg [575:0] thresholds=0;
 wire word_ready,entropy_fault,req_ready,rsp_valid,cmd_ready,seed_req,seed_error;
 wire [63:0] mask;
 rng_ffn_shared64 #(.RESEED_CYCLES(0)) dut(
 .clk(clk),.rst_n(rst_n),.word_valid(word_valid),.word_ready(word_ready),.word_data(word_data),
 .qualified(1'b1),.entropy_fault(entropy_fault),.req_valid(req_valid),.req_ready(req_ready),
 .thresholds(thresholds),.rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.mask(mask),
 .command(2'b0),.cmd_ready(cmd_ready),.seed_req(seed_req),.seed_error(seed_error));
 reg [31:0] state=0,temp;
 reg [63:0] expected=0;
 reg ev=0;
 integer i,j,k,accepted=0;
 reg [4095:0] vcd_file;
 initial begin
   if ($value$plusargs("VCD=%s",vcd_file)) begin $dumpfile(vcd_file);$dumpvars(0,dut);end
   for(i=0;i<250;i=i+1) begin
     @(negedge clk);
     rst_n=(i!=0);word_valid=(i>2);req_valid=(i%7!=0);rsp_ready=(i%23<13);
     for(j=0;j<64;j=j+1) thresholds[j*9 +: 9]=(j*4+i)%257;
     @(posedge clk);
     if(!rst_n) begin state=0;expected=0;ev=0;end
     else begin
       if(rsp_valid && rsp_ready) ev=0;
       if(dut.source.endpoint.event_seed) state=word_data;
       if(req_valid && req_ready) begin
         for(j=0;j<64;j=j+1) expected[j]=({1'b0,state[7:0]}<thresholds[j*9 +: 9]);
         temp=state;
         for(k=0;k<16;k=k+1) temp=(temp>>1)^(temp[0] ? 32'h80200003 : 32'b0);
         state=temp;ev=1;accepted=accepted+1;
       end
     end
     #1;
     if(rsp_valid!==ev || (ev && mask!==expected)) $fatal(1,"FFN mask mismatch cycle %0d",i);
     if(entropy_fault || seed_error) $fatal(1,"unexpected seed fault");
   end
   if(accepted<50) $fatal(1,"insufficient activity");
   $display("PASS FFN edges=250 frames=%0d",accepted);$finish;
 end
endmodule
