// One 8-bit word from the pre-update state; 16 Galois steps per accepted frame.
module rng_lfsr32_map(input wire [31:0] state,
 output wire [7:0] random_word, output reg [31:0] next_state);
 integer i;
 assign random_word = state[7:0];
 always @* begin
   next_state = state;
   for (i=0; i<16; i=i+1)
     next_state = (next_state >> 1) ^ (next_state[0] ? 32'h80200003 : 32'b0);
 end
endmodule

