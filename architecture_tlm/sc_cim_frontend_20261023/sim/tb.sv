`timescale 1ns/1ps
`ifndef N
`define N 64
`endif
`ifndef M
`define M 64
`endif
`ifndef T
`define T 32
`endif
`ifndef K
`define K 32
`endif
`ifndef EXT
`define EXT 0
`endif
`ifndef KIND
`define KIND 0
`endif
module tb;
 localparam integer N=`N,M=`M,T=`T,K=`K,EXT=`EXT,KIND=`KIND;
 localparam integer IW=1+1+32+1+1+8*N+N+8*N*M+1+8+N;
 localparam integer OW=1+1+1+1+1+N+8+8*N*M+1;
 reg clk=0,rst_n=0,seed_valid=0,frame_start=0,sample_ready=0,ext_valid=0;
 reg [31:0] seed_data=0;
 reg [N*8-1:0] q8=0;
 reg [N-1:0] one=0,input_bits=0;
 reg [N*M*8-1:0] weights=0;
 reg [7:0] ext_word=0;
 wire seed_ready,seed_error,frame_ready,ext_ready,sample_valid,done;
 wire [N-1:0] sample_bits;
 wire [7:0] threshold;
 wire [N*M*8-1:0] products;
 wire [OW-1:0] actual={seed_ready,seed_error,frame_ready,ext_ready,sample_valid,sample_bits,threshold,products,done};
 reg [IW-1:0] stimuli[0:8191];reg [OW-1:0] expected[0:8191];
 reg [4095:0] dir,wave;integer cycles,i,fd;reg dump;
 always #5 clk=~clk;
 generate
 if(KIND==0)begin: full
`ifdef MAPPED
  cim_probe_mapped dut(
`else
  cim_frontend #(.N(N),.M(M),.T(T),.K(K),.EXTERNAL_RNG(EXT)) dut(
`endif
   .clk(clk),.rst_n(rst_n),.seed_valid(seed_valid),.seed_data(seed_data),.seed_ready(seed_ready),.seed_error(seed_error),
   .frame_start(frame_start),.frame_ready(frame_ready),.q8(q8),.one(one),.weights(weights),.ext_valid(ext_valid),
   .ext_word(ext_word),.ext_ready(ext_ready),.sample_valid(sample_valid),.sample_ready(sample_ready),
   .sample_bits(sample_bits),.threshold(threshold),.products(products),.done(done));
  initial begin if($value$plusargs("VCD=%s",wave))begin $dumpfile(wave);$dumpvars(0,dut);end end
 end else if(KIND==1)begin: source
`ifdef MAPPED
  cim_probe_mapped dut(
`else
  cim_sng #(.N(N),.T(T),.K(K),.EXTERNAL_RNG(EXT)) dut(
`endif
   .clk(clk),.rst_n(rst_n),.seed_valid(seed_valid),.seed_data(seed_data),.seed_ready(seed_ready),.seed_error(seed_error),
   .frame_start(frame_start),.frame_ready(frame_ready),.q8(q8),.one(one),.ext_valid(ext_valid),
   .ext_word(ext_word),.ext_ready(ext_ready),.sample_valid(sample_valid),.sample_ready(sample_ready),
   .sample_bits(sample_bits),.threshold(threshold),.done(done));
  assign products=0;
  initial begin if($value$plusargs("VCD=%s",wave))begin $dumpfile(wave);$dumpvars(0,dut);end end
 end else if(KIND==2)begin: gates
`ifdef MAPPED
  cim_probe_mapped dut(
`else
  cim_w8_gate #(.N(N),.M(M)) dut(
`endif
   .bits(input_bits),.weights(weights),.products(products));
  assign {seed_ready,seed_error,frame_ready,ext_ready,sample_valid,done}=0;
  assign sample_bits=input_bits;assign threshold=0;
  initial begin if($value$plusargs("VCD=%s",wave))begin $dumpfile(wave);$dumpvars(0,dut);end end
 end else begin: qprobe
`ifdef MAPPED
  cim_probe_mapped dut(
`else
  cim_sram_q_probe #(.WIDTH(N*M*8),.COPIES(1)) dut(
`endif
   .sram_q(weights),.local_q(products));
  assign {seed_ready,seed_error,frame_ready,ext_ready,sample_valid,done}=0;
  assign sample_bits=0;assign threshold=0;
  initial begin if($value$plusargs("VCD=%s",wave))begin $dumpfile(wave);$dumpvars(0,dut);end end
 end
 endgenerate
 initial begin
  if(!$value$plusargs("DIR=%s",dir))$fatal(1,"DIR required");
  if(!$value$plusargs("CYCLES=%d",cycles))$fatal(1,"CYCLES required");
  if(cycles<1||cycles>8192)$fatal(1,"bad cycle count");
  $readmemh({dir,"/input.hex"},stimuli,0,cycles-1);
  $readmemh({dir,"/expected.hex"},expected,0,cycles-1);
  repeat(2)@(posedge clk);#1;
  for(i=0;i<cycles;i=i+1)begin
   @(negedge clk);
   {rst_n,seed_valid,seed_data,frame_start,sample_ready,q8,one,weights,ext_valid,ext_word,input_bits}=stimuli[i];
   #1;
   if(actual!==expected[i])begin
    $display("MISMATCH cycle=%0d actual=%h expected=%h",i,actual,expected[i]);$fatal(1,"functional mismatch");
   end
  end
  @(posedge clk);#2;
  $display("CIM_PASS kind=%0d N=%0d M=%0d T=%0d K=%0d EXT=%0d cycles=%0d",KIND,N,M,T,K,EXT,cycles);
  $finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
