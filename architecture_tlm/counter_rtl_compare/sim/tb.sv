`timescale 1ns/1ps
`ifndef ARCH
 `define ARCH 0
`endif
`ifndef N
 `define N 64
`endif
`ifndef M
 `define M 1
`endif
`ifndef T
 `define T 32
`endif
`ifndef PIPE
 `define PIPE 1
`endif
module tb_counter;
 localparam N=`N,M=`M,T=`T,SW=$clog2(N*T*128+1)+1,MAXF=160;
 reg clk=0;real period=10.0;
 initial begin if($value$plusargs("PERIOD=%f",period))begin end forever #(period/2)clk=~clk;end
 reg rst_n=0,cfg_start=0,in_valid=0,out_ready=0;
 reg [N*M*8-1:0] weights=0;
 reg [N-1:0] input_sign=0,true_one=0,sample_bits=0;
 reg [N*2-1:0] input_bin=0;
 wire cfg_ready,in_ready,out_valid;
 wire [M*4*SW-1:0] result;
`ifdef GATE
 sc_counter_tile_mapped dut(.*);
`else
 sc_counter_tile #(.ARCH(`ARCH),.N(N),.M(M),.T(T),.PIPE(`PIPE)) dut(.*);
`endif
 reg [N*M*8-1:0] wmem[0:MAXF-1];
 reg [N-1:0] smem[0:MAXF-1],omem[0:MAXF-1],bmem[0:MAXF*T-1];
 reg [2*N-1:0] dmem[0:MAXF-1];
 reg [M*4*SW-1:0] gold[0:MAXF-1];
 string dir,vcd;
 integer frames,mode,reset_test,f,k,j,cycles=0,accepts=0,done=0,timeout=0,start_cycle;
 reg [M*4*SW-1:0] held;
 always @(posedge clk) begin
  cycles=cycles+1;
  if(rst_n && in_ready && in_valid) accepts=accepts+1;
  if(cycles>200000)$fatal(1,"Timeout");
 end
 task tick;begin @(negedge clk);end endtask
 task wait_idle;begin
  timeout=0;
  while(cfg_ready!==1'b1)begin tick();timeout=timeout+1;if(timeout>100)$fatal(1,"idle timeout");end
 end endtask
 initial begin
  if(!$value$plusargs("DIR=%s",dir))$fatal(1,"DIR required");
  if(!$value$plusargs("FRAMES=%d",frames))$fatal(1,"FRAMES required");
  mode=0;reset_test=0;
  if($value$plusargs("MODE=%d",mode))begin end
  if($value$plusargs("RESET_TEST=%d",reset_test))begin end
  if(frames>MAXF)$fatal(1,"too many frames");
  $readmemh({dir,"/weights.hex"},wmem,0,frames-1);
  $readmemh({dir,"/sign.hex"},smem,0,frames-1);
  $readmemh({dir,"/ones.hex"},omem,0,frames-1);
  $readmemh({dir,"/bins.hex"},dmem,0,frames-1);
  $readmemh({dir,"/samples.hex"},bmem,0,frames*T-1);
  $readmemh({dir,"/gold.hex"},gold,0,frames-1);
  if($value$plusargs("VCD=%s",vcd))begin $dumpfile(vcd);$dumpvars(0,tb_counter.dut);end
  repeat(3)tick();rst_n=1;tick();
  // Abort one nonempty frame, then require a clean new frame.
  if(reset_test!=0)begin
   weights=wmem[0];input_sign=smem[0];input_bin=dmem[0];true_one=omem[0];cfg_start=1;tick();cfg_start=0;
   sample_bits={N{1'b1}};in_valid=1;tick();tick();rst_n=0;in_valid=0;tick();tick();rst_n=1;tick();
   if(out_valid!==0)$fatal(1,"reset did not flush output");
  end
  $display("WINDOW_BEGIN time_ns=%0.3f cycle=%0d",$realtime,cycles);start_cycle=cycles;
  for(f=0;f<frames;f=f+1)begin
   wait_idle();weights=wmem[f];input_sign=smem[f];input_bin=dmem[f];true_one=omem[f];
   cfg_start=1;tick();cfg_start=0;
   for(k=0;k<T;k=k+1)begin
    if(mode!=0 && (k+f)%5==0)begin
     in_valid=0;sample_bits=~bmem[f*T+k];tick();
     if(out_valid!==0)$fatal(1,"early output during sample gap");
    end
    if(in_ready!==1)$fatal(1,"unexpected sample backpressure");
    sample_bits=bmem[f*T+k];in_valid=1;tick();
   end
   in_valid=0;
   timeout=0;
   while(out_valid!==1)begin tick();timeout=timeout+1;if(timeout>10)$fatal(1,"output timeout");end
   if(result!==gold[f])begin
    $display("MISMATCH frame=%0d got=%h expected=%h",f,result,gold[f]);$fatal(1,"integer mismatch");
   end
   held=result;
   // Attempted input and cfg while output stalled must not alter the frame.
   if(mode!=0)begin
    repeat(3)begin
     in_valid=1;cfg_start=1;sample_bits=~sample_bits;tick();
     if(out_valid!==1 || result!==held || in_ready!==0 || cfg_ready!==0)$fatal(1,"output hold violated");
    end
    in_valid=0;cfg_start=0;
   end
   out_ready=1;tick();out_ready=0;done=done+1;
   $display("FRAME_PASS frame=%0d result=%h",f,held);
  end
  $display("WINDOW_END time_ns=%0.3f cycle=%0d frames=%0d active_cycles=%0d",$realtime,cycles,done,cycles-start_cycle);
  $display("IDLE_BEGIN time_ns=%0.3f",$realtime);repeat(64)tick();$display("IDLE_END time_ns=%0.3f",$realtime);
  if(done!=frames)$fatal(1,"frame count mismatch");
  $display("COUNTER_PASS arch=%0d n=%0d m=%0d t=%0d pipe=%0d frames=%0d outputs=%0d accepted=%0d",`ARCH,N,M,T,`PIPE,done,done*M*4,accepts);
  $finish;
 end
endmodule
