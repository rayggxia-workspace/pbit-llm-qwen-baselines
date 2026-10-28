`timescale 1ns/1ps
// Exact uniform-rank arbitration with bounded elastic preprocessing.
// Source bitmaps are independent of winner when drives are fixed. We may
// preselect an active address before the previous frame commits. At commit,
// use the ACTUAL previous winner bit, never a speculative winner.
// This spends fair bits even on some hold frames; counters expose that cost.
module ac_winner128 #(
 parameter integer COUNT_W=32,N=128,GROUP=16,PREP_STAGES=2,STREAM=1,WINNER_ONEHOT=0,RANK_CAP=64,EARLY_HOLD=0,
 parameter integer AW=$clog2(N),CW=AW+1,GL=$clog2(GROUP),GROUPS=N/GROUP
)(
 input wire clk,rst_n,start,
 output wire start_ready,busy,cfg_valid,input wire cfg_ready,
 input wire [N-1:0] candidate_mask,input wire [AW-1:0] initial_index,
 input wire [COUNT_W-1:0] requested_samples,burn_updates,
 input wire frame_valid,output wire frame_ready,input wire [N-1:0] frame_bits,
 input wire fair_valid,output wire fair_ready,input wire [AW-1:0] fair_word,
 output reg out_valid,input wire out_ready,output reg [AW-1:0] out_index,
 output reg done,failed,
 output reg [COUNT_W-1:0] issued,committed,
 output reg [31:0] consumed,holds,switches,fair_words,fair_bits,rank_retries,
 output wire [AW-1:0] winner_index
);
 reg active,configured,finishing;
 reg [N-1:0] mask_r;reg [AW-1:0] winner;
 localparam integer RW=$clog2(RANK_CAP+1)>0?$clog2(RANK_CAP+1):1;
 reg [COUNT_W-1:0] target_frames,burn_r;reg [RW-1:0] retries;
 wire [AW-1:0] next_winner;
 wire v0,v1,v2,r0,r1,r2,pop1,pop2,abort_rank;
 wire [N-1:0] bits0,bits1,bits2;
 wire [GROUPS*CW-1:0] counts0,prefix1;
 wire [CW-1:0] count1;
 wire [GROUP-1:0] group2;wire [GL-1:0] rank2;wire [AW-1:0] base2;
 wire empty2;
 assign start_ready=!active;assign busy=active;assign cfg_valid=active&&!configured;
 assign winner_index=winner;
 assign frame_ready=active&&configured&&!finishing&&issued<target_frames&&r0&&(STREAM!=0||issued==committed);
 wire accept_frame=frame_valid&&frame_ready;
 wire clear_pipe=!rst_n||(start&&start_ready)||abort_rank;
 wire [N-1:0] masked=frame_bits&mask_r;
 wire [GROUPS*CW-1:0] group_counts;
 genvar g,j;
 generate for(g=0;g<GROUPS;g=g+1)begin:g_count
  wire [GL:0] ct[1:2*GROUP-1];
  for(j=0;j<GROUP;j=j+1)begin:leaf assign ct[GROUP+j]=masked[g*GROUP+j];end
  for(j=1;j<GROUP;j=j+1)begin:node assign ct[j]=ct[2*j]+ct[2*j+1];end
  assign group_counts[g*CW+:CW]=ct[1];
 end
 if(PREP_STAGES==2)begin:prep_register
  reg valid;reg [N-1:0] bitmap;reg [GROUPS*CW-1:0] counts;
  assign v0=valid;assign bits0=bitmap;assign counts0=counts;
  assign r0=!valid||r1;
  always @(posedge clk)begin
   if(clear_pipe)begin valid<=0;bitmap<=0;counts<=0;end
   else if(r0)begin valid<=accept_frame;if(accept_frame)begin bitmap<=masked;counts<=group_counts;end end
  end
 end else begin:fused_prepare
  assign v0=accept_frame;assign bits0=masked;assign counts0=group_counts;assign r0=r1;
 end endgenerate
 wire [GROUPS*CW-1:0] prefix_comb;wire [CW-1:0] total_comb;
 ac_scan #(.N(GROUPS),.W(CW)) global_scan(.values(counts0),.prefix(prefix_comb),.total(total_comb));
 reg valid1;reg [N-1:0] bitmap1;reg [GROUPS*CW-1:0] prefixes1;reg [CW-1:0] total1;
 assign v1=valid1;assign bits1=bitmap1;assign prefix1=prefixes1;assign count1=total1;
 assign r1=!v1||pop1;
 always @(posedge clk)begin
  if(clear_pipe)begin valid1<=0;bitmap1<=0;prefixes1<=0;total1<=0;end
  else if(r1)begin valid1<=v0;if(v0)begin bitmap1<=bits0;prefixes1<=prefix_comb;total1<=total_comb;end end
 end
 // ceil(log2(M)), including M=N, and M=0/1 entropy bypass.
 reg [AW-1:0] rank_mask;reg [AW:0] width;integer b;
 always @* begin
  rank_mask=0;width=0;
  for(b=0;b<AW;b=b+1)if(count1>(1<<b))begin rank_mask=(1<<(b+1))-1;width=b+1;end
 end
 // Serial mode knows the old winner. Optional exact look-ahead also knows
 // the preceding frame's commit result when r2 allows a transfer. It saves
 // fair words at the cost of a longer combinational dependency across stages.
 wire [AW-1:0] guard_winner=(EARLY_HOLD!=0&&pop2)?next_winner:winner;
 wire guarded_hold=(EARLY_HOLD!=0||STREAM==0)&&bits1[guard_winner];
 wire needs_rank=count1>1&&!guarded_hold;
 wire [AW-1:0] rank_value=!needs_rank?0:(fair_word&rank_mask);
 wire rank_ok=!needs_rank || rank_value<count1;
 assign fair_ready=active&&v1&&r2&&needs_rank;
 wire fair_fire=fair_ready&&fair_valid;
 assign abort_rank=fair_fire&&!rank_ok&&retries+1>=RANK_CAP;
 assign pop1=active&&v1&&r2&&(!needs_rank||(fair_valid&&rank_ok));
 localparam integer PAY=GROUP+AW+GL;
 wire [PAY-1:0] select_tree[1:2*GROUPS-1];
 generate for(g=0;g<GROUPS;g=g+1)begin:group_selection
  wire [CW-1:0] lo=prefix1[g*CW+:CW];wire [CW-1:0] hi;
  if(g==GROUPS-1)assign hi=count1;else assign hi=prefix1[(g+1)*CW+:CW];
  wire hit=rank_value>=lo&&rank_value<hi;
  wire [GL-1:0] local_rank=rank_value-lo;
  wire [AW-1:0] base_index=g*GROUP;
  assign select_tree[GROUPS+g]=hit?{bits1[g*GROUP+:GROUP],base_index,local_rank}:{PAY{1'b0}};
 end
 for(g=1;g<GROUPS;g=g+1)begin:select_or assign select_tree[g]=select_tree[2*g]|select_tree[2*g+1];end endgenerate
 reg valid2;reg [N-1:0] bitmap2;reg [GROUP-1:0] chosen_group2;
 reg [GL-1:0] chosen_rank2;reg [AW-1:0] chosen_base2;reg zero2;
 assign v2=valid2;assign bits2=bitmap2;assign group2=chosen_group2;
 assign rank2=chosen_rank2;assign base2=chosen_base2;assign empty2=zero2;
 assign r2=!v2||pop2;
 always @(posedge clk)begin
  if(clear_pipe)begin valid2<=0;bitmap2<=0;chosen_group2<=0;chosen_rank2<=0;chosen_base2<=0;zero2<=0;end
  else if(r2)begin valid2<=pop1;if(pop1)begin
   bitmap2<=bits1;{chosen_group2,chosen_base2,chosen_rank2}<=select_tree[1];zero2<=count1==0;
  end end
 end
 wire [GROUP*(GL+1)-1:0] local_values,local_prefix;wire [GL:0] unused_total;
 generate for(j=0;j<GROUP;j=j+1)begin:local_leaf
  assign local_values[j*(GL+1)+:(GL+1)]=group2[j];
 end endgenerate
 ac_scan #(.N(GROUP),.W(GL+1)) local_scan(.values(local_values),.prefix(local_prefix),.total(unused_total));
 wire [GL-1:0] index_tree[1:2*GROUP-1];
 generate for(j=0;j<GROUP;j=j+1)begin:local_pick
  assign index_tree[GROUP+j]=(group2[j]&&local_prefix[j*(GL+1)+:(GL+1)]==rank2)?j:0;
 end
 for(j=1;j<GROUP;j=j+1)begin:local_or assign index_tree[j]=index_tree[2*j]|index_tree[2*j+1];end endgenerate
 wire [AW-1:0] selected=base2|index_tree[1];
 wire old_active;
 generate if(WINNER_ONEHOT!=0)begin:onehot_feedback
  reg [N-1:0] winner_hot;
  assign old_active=|(bits2&winner_hot);
  always @(posedge clk)begin
   if(!rst_n)winner_hot<=0;
   else if(start&&start_ready)winner_hot<=({{(N-1){1'b0}},1'b1}<<initial_index);
   else if(pop2&&!empty2&&!old_active)winner_hot<=({{(N-1){1'b0}},1'b1}<<selected);
  end
 end else begin:binary_feedback assign old_active=bits2[winner];end endgenerate
 assign next_winner=empty2||old_active?winner:selected;
 assign pop2=active&&v2&&(committed<burn_r||!out_valid||out_ready);
 always @(posedge clk)begin
  if(!rst_n)begin
   active<=0;configured<=0;finishing<=0;mask_r<=0;winner<=0;target_frames<=0;burn_r<=0;
   out_valid<=0;out_index<=0;done<=0;failed<=0;issued<=0;committed<=0;consumed<=0;
   holds<=0;switches<=0;fair_words<=0;fair_bits<=0;rank_retries<=0;retries<=0;
  end else begin
   done<=0;
   if(out_valid&&out_ready)begin out_valid<=0;consumed<=consumed+1'b1;end
   if(start&&start_ready)begin
    mask_r<=candidate_mask;winner<=initial_index;burn_r<=burn_updates;
    target_frames<=requested_samples+burn_updates;active<=1;configured<=0;finishing<=0;
    out_valid<=0;failed<=0;issued<=0;committed<=0;consumed<=0;holds<=0;switches<=0;
    fair_words<=0;fair_bits<=0;rank_retries<=0;retries<=0;
    if(requested_samples==0||!candidate_mask[initial_index]||
       ({1'b0,requested_samples}+{1'b0,burn_updates})>{1'b0,{COUNT_W{1'b1}}})begin active<=0;failed<=1;done<=1;end
   end
   if(cfg_valid&&cfg_ready)configured<=1;
   if(accept_frame)issued<=issued+1'b1;
   if(fair_fire)begin
    fair_words<=fair_words+1'b1;fair_bits<=fair_bits+width;
    if(!rank_ok)begin rank_retries<=rank_retries+1'b1;retries<=retries+1'b1;end
   end
   if(pop1)retries<=0;
   if(pop2)begin
    winner<=next_winner;committed<=committed+1'b1;
    if(next_winner==winner)holds<=holds+1'b1;else switches<=switches+1'b1;
    if(committed>=burn_r)begin out_valid<=1;out_index<=next_winner;end
    if(committed+1>=target_frames)finishing<=1;
   end
   if(active&&finishing&&(!out_valid||out_ready))begin active<=0;finishing<=0;done<=1;end
   if(abort_rank)begin active<=0;finishing<=0;out_valid<=0;failed<=1;done<=1;end
  end
 end
`ifndef SYNTHESIS
 initial if(COUNT_W<1||COUNT_W>32||N<2||(N&(N-1))!=0||GROUP<2||(GROUP&(GROUP-1))!=0||N%GROUP!=0||
            PREP_STAGES<1||PREP_STAGES>2||RANK_CAP<1)$fatal(1,"parameters");
`endif
endmodule
