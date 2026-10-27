`timescale 1ns/1ps
`ifndef DUT_TOP
`define DUT_TOP counter_b4_t64_m1_p1_g0
`endif
`ifndef DUT_M
`define DUT_M 1
`endif
`ifndef DUT_BINS
`define DUT_BINS 4
`endif
`ifndef DUT_T
`define DUT_T 64
`endif
`ifndef DUT_AW
`define DUT_AW 26
`endif
// Fixed-top DUT: the same bench accepts a mapped netlist named DUT_TOP.
// Test fixture RNG and integer oracle are OUTSIDE the dumped DUT hierarchy.
module tb_counter_power;
 localparam N=64,M=`DUT_M,BINS=`DUT_BINS,T=`DUT_T,AW=`DUT_AW;
 real period_ns=10.0, window_start,window_end;
 integer seed=17,frames_to_run=8,p8=128,frame,step,n,lane,rv,tmp,wait_cycles;
 integer accepted_frames=0,accepted_samples=0,completed_frames=0;
 reg clk=0,rst_n=0,test_en=0,frame_valid=0,sample_valid=0,out_ready=0;
 reg [N*M*7-1:0] w_mag7=0;reg [N*M-1:0] w_sign=0;
 reg [N-1:0] x_sign=0,sample_bits=0;reg [N*3-1:0] bin_id=0;
 wire frame_ready,sample_ready,out_valid;wire [M*AW-1:0] out_sum;
 reg [1023:0] vcd_path;reg [127:0] mode;
 reg signed [63:0] expected[0:M-1];reg signed [63:0] term,observed;
 reg counting=0;
 `DUT_TOP dut(.clk(clk),.rst_n(rst_n),.test_en(test_en),.frame_valid(frame_valid),
   .frame_ready(frame_ready),.w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),
   .bin_id(bin_id),.sample_bits(sample_bits),.sample_valid(sample_valid),
   .sample_ready(sample_ready),.out_valid(out_valid),.out_ready(out_ready),.out_sum(out_sum));
 initial begin #0;forever #(period_ns/2.0) clk=~clk;end
 always @(posedge clk) begin
   if(!rst_n) begin
     for(lane=0;lane<M;lane=lane+1) expected[lane]=0;
   end else begin
     if(frame_valid && frame_ready) begin
       for(lane=0;lane<M;lane=lane+1) expected[lane]=0;
       if(counting)accepted_frames=accepted_frames+1;
     end
     if(sample_valid && sample_ready) begin
       if(counting)accepted_samples=accepted_samples+1;
       for(lane=0;lane<M;lane=lane+1) begin
         for(n=0;n<N;n=n+1) if(sample_bits[n] && bin_id[3*n+:3]<BINS) begin
           term=$signed({1'b0,w_mag7[(lane*N+n)*7+:7]});
           if(w_sign[lane*N+n]^x_sign[n])term=-term;
           term=term<<<(2*(BINS-1-bin_id[3*n+:3]));
           expected[lane]=expected[lane]+term;
         end
       end
     end
     if(out_valid && out_ready) begin
       for(lane=0;lane<M;lane=lane+1) begin
         observed=$signed(out_sum[lane*AW+:AW]);
         if(observed!==expected[lane])$fatal(1,"power bench integer mismatch lane=%0d got=%0d want=%0d",lane,observed,expected[lane]);
       end
       if(counting)completed_frames=completed_frames+1;
     end
   end
 end
 task neg;begin @(negedge clk);#0.001;end endtask
 task tick;begin @(posedge clk);#0.002;end endtask
 task do_frame;
 integer q,i;
 begin
   neg;while(!frame_ready)begin tick;neg;end
   // Weights/metadata stable for the WHOLE frame, including output hold.
   for(i=0;i<N*M;i=i+1)begin rv=$random(seed);w_mag7[i*7+:7]=rv[6:0];w_sign[i]=rv[7];end
   for(i=0;i<N;i=i+1)begin rv=$random(seed);x_sign[i]=rv[0];bin_id[3*i+:3]=(rv&32'h7fffffff)%BINS;end
   frame_valid=1;sample_valid=0;out_ready=0;tick;neg;frame_valid=0;
   for(q=0;q<T;q=q+1)begin
     if(mode=="sparse" && q%4==2)repeat(5)begin sample_valid=0;tick;neg;end
     if(!sample_ready)$fatal(1,"sample_ready unexpectedly low");
     rv=$random(seed);
     // Shared R8 comparator test pattern (one value per event, P8 configurable).
     sample_bits=(rv[7:0]<p8)?{N{1'b1}}:{N{1'b0}};
     sample_valid=1;tick;neg;
   end
   sample_valid=0;sample_bits=0;wait_cycles=0;
   while(!out_valid)begin tick;neg;wait_cycles=wait_cycles+1;if(wait_cycles>32)$fatal(1,"drain timeout");end
   if(mode=="stall")repeat(32)begin tick;neg;end
   out_ready=1;tick;neg;out_ready=0;
 end endtask
 initial begin
   mode="continuous";vcd_path="activity.vcd";
   tmp=$value$plusargs("MODE=%s",mode);tmp=$value$plusargs("VCD=%s",vcd_path);
   tmp=$value$plusargs("SEED=%d",seed);tmp=$value$plusargs("FRAMES=%d",frames_to_run);
   tmp=$value$plusargs("P8=%d",p8);tmp=$value$plusargs("PERIOD_NS=%f",period_ns);
   if(period_ns<=0 || frames_to_run<1 || p8<0 || p8>256)$fatal(1,"invalid plusarg");
   if(mode!="continuous" && mode!="sparse" && mode!="idle" && mode!="wake" && mode!="stall")$fatal(1,"invalid MODE");
   $dumpfile(vcd_path);$dumpvars(0,dut);
   repeat(4)tick;neg;rst_n=1;repeat(8)tick;neg;
   accepted_frames=0;accepted_samples=0;completed_frames=0;counting=1;window_start=$realtime;
   if(mode=="idle")repeat(512)tick;
   else for(frame=0;frame<frames_to_run;frame=frame+1)begin
     if(mode=="wake")repeat(64)tick;
     do_frame;
   end
   neg;window_end=$realtime;counting=0;
   if(mode!="idle" && (completed_frames!=frames_to_run || accepted_samples!=T*frames_to_run || accepted_frames!=frames_to_run))$fatal(1,"event counts mismatch");
   $display("WINDOW start_ns=%0.3f end_ns=%0.3f frames=%0d accepted_samples=%0d accepted_frames=%0d outputs=%0d mode=%0s",window_start,window_end,completed_frames,accepted_samples,accepted_frames,completed_frames,mode);
   $display("PASS counter_power integer_and_counts; DUT-only VCD; no STA/PPA claim");
   $finish;
 end
 initial begin #10000000;$fatal(1,"timeout");end
endmodule
