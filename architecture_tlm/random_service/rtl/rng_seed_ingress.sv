// Upstream is already qualified AND synchronized to clk. No ADC/CDC/conditioner.
// A word is not "physical entropy" merely because qualified is asserted.
module rng_seed_ingress #(parameter integer STATE_BITS=177)(
 input wire clk, input wire rst_n, input wire seed_req,
 input wire word_valid, output wire word_ready, input wire [31:0] word_data,
 input wire qualified, output reg fault,
 output reg seed_valid, input wire seed_ready, output wire [STATE_BITS-1:0] seed_data);
 localparam integer BEATS=(STATE_BITS+31)/32;
 localparam integer CW=(BEATS<=1 ? 1 : $clog2(BEATS));
 reg [BEATS*32-1:0] packet;
 reg [CW-1:0] count;
 assign word_ready=seed_req && !seed_valid && !fault;
 assign seed_data=packet[STATE_BITS-1:0];
 always @(posedge clk or negedge rst_n) begin
   if (!rst_n) begin packet<=0; count<=0; fault<=0; seed_valid<=0; end
   else begin
     if (seed_valid && seed_ready) begin packet<=0; count<=0; seed_valid<=0; end
     if (word_valid && word_ready) begin
       if (!qualified) begin fault<=1; packet<=0; count<=0; end
       else begin
         packet[count*32 +: 32]<=word_data;
         if (count==BEATS-1) seed_valid<=1;
         else count<=count+1'b1;
       end
     end
   end
 end
endmodule

