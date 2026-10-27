`timescale 1ns/1ps
// One query context, one pending proposal and one output register.
// External source owns logits/LUT/RNG/settling: cfg_valid must handshake only
// after all lanes reflect current shift_m. No new proposal while reconfiguring.
module attention_rejection_control #(
 parameter integer N=16, LEVELS_PER_STAGE=2, MAX_SHIFT=24,
 parameter integer AW=$clog2(N)
)(
 input wire clk,rst_n,start,
 input wire [AW-1:0] reference_index,
 input wire [31:0] requested_samples,proposal_cap,
 output wire start_ready,busy,
 output wire cfg_valid,input wire cfg_ready,
 output reg [4:0] shift_m,
 input wire proposal_valid,output wire proposal_ready,
 input wire [N-1:0] proposal_bits,
 output wire fair_ready,input wire fair_valid,
 input wire [MAX_SHIFT-1:0] fair_bits,
 output reg out_valid,input wire out_ready,
 output reg [AW-1:0] out_index,
 output reg done,failed,
 output reg [31:0] proposals,accepted,consumed,
 output reg [31:0] rejected_multi,rejected_empty
);
 localparam IDLE=0,CONFIG=1,DRAW=2,REDUCE=3,COIN=4,DRAIN=5;
 reg [2:0] state;
 reg [AW-1:0] ref_r;
 reg [31:0] target_r,cap_r;
 wire tree_valid; wire [1:0] cardinality; wire [AW-1:0] singleton;
 wire [N-1:0] mask = {N{1'b1}} ^ ({{(N-1){1'b0}},1'b1} << ref_r);
 assign start_ready=state==IDLE;
 assign busy=state!=IDLE;
 assign cfg_valid=state==CONFIG;
 assign proposal_ready=state==DRAW && (!out_valid || out_ready) && proposals<cap_r;
 assign fair_ready=state==COIN;
 nr_singleton_tree #(.N(N),.LEVELS_PER_STAGE(LEVELS_PER_STAGE)) reduce_tree(
  .clk(clk),.rst_n(rst_n),.in_valid(proposal_valid&&proposal_ready),
  .bits_in(proposal_bits),.mask(mask),.out_valid(tree_valid),
  .cardinality(cardinality),.first_index(singleton));
 reg decide,emit_sample,multi_reject,empty_reject;
 reg [4:0] next_m;
 reg [AW-1:0] chosen;
 wire [MAX_SHIFT-1:0] coin_mask=({MAX_SHIFT{1'b1}} >> (MAX_SHIFT-shift_m));
 always @* begin
  decide=0;emit_sample=0;multi_reject=0;empty_reject=0;next_m=shift_m;chosen=ref_r;
  if(state==REDUCE && tree_valid)begin
   if(cardinality==1)begin decide=1;emit_sample=1;chosen=singleton;end
   else if(cardinality==2)begin
    decide=1;multi_reject=1;if(shift_m<MAX_SHIFT)next_m=shift_m+1'b1;
   end else if(shift_m==0)begin decide=1;emit_sample=1;end
  end
  if(state==COIN && fair_valid)begin
   decide=1;
   if((fair_bits&coin_mask)==0)emit_sample=1;
   else begin empty_reject=1;if(shift_m!=0)next_m=shift_m-1'b1;end
  end
 end
 always @(posedge clk)begin
  if(!rst_n)begin
   state<=IDLE;ref_r<=0;target_r<=0;cap_r<=0;shift_m<=0;
   out_valid<=0;out_index<=0;done<=0;failed<=0;
   proposals<=0;accepted<=0;consumed<=0;rejected_multi<=0;rejected_empty<=0;
  end else begin
   done<=0;
   if(out_valid&&out_ready)begin out_valid<=0;consumed<=consumed+1'b1;end
   if(state==IDLE && start)begin
    ref_r<=reference_index;target_r<=requested_samples;cap_r<=proposal_cap;
    shift_m<=0;failed<=0;out_valid<=0;proposals<=0;accepted<=0;consumed<=0;
    rejected_multi<=0;rejected_empty<=0;
    if(requested_samples==0 || proposal_cap==0 || reference_index>=N)begin
     failed<=1;done<=1;
    end else state<=CONFIG;
   end
   if(state==CONFIG && cfg_ready)state<=DRAW;
   if(proposal_valid&&proposal_ready)begin proposals<=proposals+1'b1;state<=REDUCE;end
   if(state==REDUCE && tree_valid && cardinality==0 && shift_m!=0)state<=COIN;
   if(decide)begin
    shift_m<=next_m;
    if(multi_reject)rejected_multi<=rejected_multi+1'b1;
    if(empty_reject)rejected_empty<=rejected_empty+1'b1;
    if(emit_sample)begin
     out_valid<=1;out_index<=chosen;accepted<=accepted+1'b1;
     if(accepted+1>=target_r)state<=DRAIN;
     else if(proposals>=cap_r)begin failed<=1;state<=DRAIN;end
     else state<=DRAW;
    end else if(proposals>=cap_r)begin failed<=1;state<=DRAIN;end
    else if(next_m!=shift_m)state<=CONFIG;
    else state<=DRAW;
   end
   if(state==DRAIN && (!out_valid || out_ready))begin state<=IDLE;done<=1;end
  end
 end
`ifndef SYNTHESIS
 initial begin
  if(N<2 || (N&(N-1))!=0 || MAX_SHIFT<1 || MAX_SHIFT>24 || LEVELS_PER_STAGE<1)
   $fatal(1,"unsupported parameters");
 end
`endif
endmodule
