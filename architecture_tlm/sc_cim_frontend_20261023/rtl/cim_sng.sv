// No probability storage, no weight storage. q8/one must remain stable during
// the active frame, including backpressure. T divisible by K, power-of-two K.
// K=1: natural PRNG word. K=32,T=32: {stratum[4:0], word[2:0]}.
module cim_sng #(parameter integer N=64,T=32,K=32,EXTERNAL_RNG=0,
 parameter integer COMP_PER_BRANCH=8)(
 input wire clk,rst_n,
 input wire seed_valid, input wire [31:0] seed_data,
 output wire seed_ready, output reg seed_error,
 input wire frame_start, output wire frame_ready,
 input wire [N*8-1:0] q8, input wire [N-1:0] one,
 input wire ext_valid, input wire [7:0] ext_word, output wire ext_ready,
 output wire sample_valid, input wire sample_ready,
 output wire [N-1:0] sample_bits, output wire [7:0] threshold,
 output reg done);
 localparam integer CW=(T<2)?1:$clog2(T);
 localparam integer JITTER=256/K, REPEATS=T/K;
 localparam integer BRANCHES=(N+COMP_PER_BRANCH-1)/COMP_PER_BRANCH;
 reg [31:0] rng_state;
 reg seeded,running;
 reg [CW-1:0] count;
 wire [31:0] next_state;
 wire [7:0] local_word,word;
 wire accept=sample_valid&&sample_ready;
 rng_lfsr32_map prng_map(.state(rng_state),.random_word(local_word),.next_state(next_state));
 assign word=EXTERNAL_RNG?ext_word:local_word;
 assign seed_ready=!running;
 assign frame_ready=!running&&(EXTERNAL_RNG||seeded)&&!seed_valid;
 assign sample_valid=running&&(!EXTERNAL_RNG||ext_valid);
 assign ext_ready=EXTERNAL_RNG&&running&&sample_ready;
 // Match unified_v6: all T/K draws of one stratum precede the next stratum.
 wire [7:0] raw_threshold=(count/REPEATS)*JITTER+(word&(JITTER-1));
 assign threshold=running?raw_threshold:8'd0;
 wire [BRANCHES*8-1:0] local_threshold;
 cim_fanout #(.WIDTH(8),.COPIES(BRANCHES)) threshold_drive(
  .din(threshold),.dout(local_threshold));
 genvar i;
 generate for(i=0;i<N;i=i+1) begin: comparator
  wire [7:0] r=local_threshold[(i/COMP_PER_BRANCH)*8+:8];
  assign sample_bits[i]=running&&(one[i]||(r<q8[i*8+:8]));
 end endgenerate
 always @(posedge clk) begin
  if(!rst_n) begin rng_state<=32'd1;seeded<=0;running<=0;count<=0;done<=0;seed_error<=0;end
  else begin
   done<=0;seed_error<=0;
   if(seed_valid&&seed_ready) begin
    if(seed_data==0) seed_error<=1;
    else begin rng_state<=seed_data;seeded<=1;end
   end
   if(frame_start&&frame_ready) begin running<=1;count<=0;end
   if(accept) begin
    if(!EXTERNAL_RNG)rng_state<=next_state;
    if(count==T-1) begin running<=0;count<=0;done<=1;end
    else count<=count+1'b1;
   end
  end
 end
 // synthesis translate_off
 initial begin
  if(N<1||T<1||K<1||K>256||(K&(K-1))!=0||T%K!=0||COMP_PER_BRANCH<1)
   $fatal(1,"invalid SNG geometry/T/K");
 end
 // synthesis translate_on
endmodule
