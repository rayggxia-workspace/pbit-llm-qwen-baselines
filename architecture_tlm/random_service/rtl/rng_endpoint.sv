// KIND 0=LFSR32/1 byte, 1=LFSR32+GF/64 bytes, 2=Bivium/20 bytes.
// Single-entry elastic response. No output before external seed handshake.
// Thresholds are 9-bit q in [0,256], P=q/256; lane 0 in LSB.
module rng_endpoint #(
 parameter integer KIND=0,
 parameter integer LANES=(KIND==1 ? 64 : KIND==2 ? 20 : 1),
 parameter integer STATE_BITS=(KIND==2 ? 177 : 32),
 parameter [31:0] RESEED_CYCLES=32'd100000000
)(input wire clk, input wire rst_n,
 input wire req_valid, output wire req_ready,
 input wire [LANES*9-1:0] thresholds,
 output reg rsp_valid, input wire rsp_ready,
 output reg [LANES*8-1:0] words, output reg [LANES-1:0] bits,
 output wire seed_req, input wire seed_valid, output wire seed_ready,
 input wire [STATE_BITS-1:0] seed_data, output reg seed_error,
 input wire [1:0] command, output wire cmd_ready,
 output reg seeded, output reg epoch_locked,
 output reg [31:0] epoch, output reg [31:0] age,
 output reg [3:0] warm_left,
 output wire event_update, output wire event_warmup,
 output wire event_seed, output wire event_consume,
 output wire [STATE_BITS-1:0] debug_state);
 reg [STATE_BITS-1:0] state, checkpoint;
 wire [STATE_BITS-1:0] next_state;
 wire [LANES*8-1:0] random_word;
 wire due = !seeded || ((RESEED_CYCLES!=0) && age>=RESEED_CYCLES);
 wire cmd_legal = ((command==1) && !epoch_locked && !due) ||
                  (((command==2)||(command==3)) && epoch_locked);
 assign seed_req = due && !epoch_locked && (warm_left==0);
 assign seed_ready = seed_req && !rsp_valid;
 assign cmd_ready = seeded && (warm_left==0) && !rsp_valid && !seed_valid && cmd_legal;
 assign req_ready = seeded && (warm_left==0) && (!due || epoch_locked) &&
                    (!rsp_valid || rsp_ready) && !seed_valid && (command==0);
 assign event_update = rst_n && req_valid && req_ready;
 assign event_warmup = rst_n && (warm_left!=0);
 assign event_seed = rst_n && seed_valid && seed_ready && (seed_data!=0);
 assign event_consume = rst_n && rsp_valid && rsp_ready;
 assign debug_state = state;
 generate
   if (KIND==0) begin: plain
     rng_lfsr32_map core(state,random_word,next_state);
   end else if (KIND==1) begin: shared
     rng_shared64_map core(state,random_word,next_state);
   end else begin: nonlinear
     rng_bivium_map core(state,random_word,next_state);
   end
 endgenerate
 integer lane;
 always @(posedge clk or negedge rst_n) begin
   if (!rst_n) begin
     state<=0; checkpoint<=0; seeded<=0; epoch_locked<=0;
     rsp_valid<=0; words<=0; bits<=0; epoch<=0; age<=0; warm_left<=0; seed_error<=0;
   end else begin
     seed_error<=0;
     if (seeded && age!=32'hffffffff) age<=age+1'b1;
     if (event_consume) rsp_valid<=0;
     if (seed_valid && seed_ready) begin
       if (seed_data==0) seed_error<=1;
       else begin
         state<=seed_data; seeded<=1; age<=0; epoch<=epoch+1'b1;
         warm_left<=(KIND==2 ? 5 : 0);
       end
     end else if (warm_left!=0) begin
       state<=next_state; warm_left<=warm_left-1'b1;
     end else if ((command!=0) && cmd_ready) begin
       case (command)
         1: begin checkpoint<=state; epoch_locked<=1; end
         2: state<=checkpoint;
         3: epoch_locked<=0;
       endcase
     end else if (event_update) begin
       state<=next_state; words<=random_word; rsp_valid<=1;
       for (lane=0;lane<LANES;lane=lane+1)
         bits[lane]<=({1'b0,random_word[lane*8 +: 8]} < thresholds[lane*9 +: 9]);
     end
   end
 end
 // synthesis translate_off
 initial begin
   if (KIND<0 || KIND>2 || LANES!=(KIND==1 ? 64 : KIND==2 ? 20 : 1) ||
       STATE_BITS!=(KIND==2 ? 177 : 32)) $fatal(1,"invalid profile parameters");
 end
 integer j;
 always @(posedge clk) if (rst_n && event_update)
   for (j=0;j<LANES;j=j+1)
     if (thresholds[j*9 +: 9]>256) $fatal(1,"threshold out of range");
 // synthesis translate_on
endmodule

