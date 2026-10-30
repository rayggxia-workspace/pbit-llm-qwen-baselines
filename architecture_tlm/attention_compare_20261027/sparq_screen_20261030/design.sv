// Streaming screening primitives. All full-length arrays live in shared SRAM.
module radix_select #(parameter L=16)(
 input wire clk,rst_n,start,in_valid,
 input wire [11:0] n_items,input wire [7:0] keep_k,input wire [5:0] first_shift,
 input wire [32*L-1:0] scores,
 output wire req_valid,output reg [11:0] req_base,
 output reg out_valid,output reg [11:0] out_base,
 output reg [L-1:0] out_mask,output reg [12*L-1:0] packed_indices,
 output reg [4:0] out_count,output reg done
);
 localparam IDLE=0,HIST=1,HWAIT=2,BIN=3,EMIT=4,EWAIT=5;
 reg [2:0] state;reg [11:0] n,rank,eq_left;
 reg [5:0] shift;reg [3:0] bin;
 reg [31:0] prefix,mask;
 reg [11:0] hist[0:15];
 reg iv,ie;reg [11:0] ib;reg [32*L-1:0] data;
 reg [4:0] increments[0:15];
 reg [L-1:0] selected,equal_mask,greater_mask;reg [12*L-1:0] packed_comb;
 reg [4:0] equal_prefix[0:L];
 reg [4:0] selected_count;reg [11:0] remaining_eq;
 reg [31:0] value;integer lane,h,hseq;
 assign req_valid=(state==HIST || state==EMIT);
 always @* begin
  for(h=0;h<16;h=h+1) increments[h]=0;
  selected=0;equal_mask=0;greater_mask=0;packed_comb=0;selected_count=0;remaining_eq=eq_left;value=0;
  for(lane=0;lane<=L;lane=lane+1) equal_prefix[lane]=0;
  if(iv && !ie) begin
   for(lane=0;lane<L;lane=lane+1) begin
    value=data[lane*32+:32];
    if(ib+lane<n && (value&mask)==prefix)
     for(h=0;h<16;h=h+1)
      if(((value>>shift)&32'hf)==h) increments[h]=increments[h]+1'b1;
   end
  end
  if(iv && ie) begin
   for(lane=0;lane<L;lane=lane+1) begin
    value=data[lane*32+:32];
    equal_mask[lane]=(ib+lane<n && value==prefix);
    greater_mask[lane]=(ib+lane<n && value>prefix);
    equal_prefix[lane+1]=equal_prefix[lane]+equal_mask[lane];
   end
   remaining_eq=(eq_left>equal_prefix[L])?(eq_left-equal_prefix[L]):12'd0;
   for(lane=0;lane<L;lane=lane+1) begin
    if(ib+lane<n) begin
     selected[lane]=greater_mask[lane] || (equal_mask[lane] && equal_prefix[lane+1]<=eq_left);
     if(selected[lane]) begin
      packed_comb[selected_count*12+:12]=ib+lane;
      selected_count=selected_count+1'b1;
     end
    end
   end
  end
 end
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   state<=IDLE;req_base<=0;n<=0;rank<=0;eq_left<=0;shift<=0;bin<=0;
   prefix<=0;mask<=0;iv<=0;ie<=0;ib<=0;data<=0;
   out_valid<=0;out_base<=0;out_mask<=0;packed_indices<=0;out_count<=0;done<=0;
   for(hseq=0;hseq<16;hseq=hseq+1) hist[hseq]<=0;
  end else begin
   iv<=0;out_valid<=0;done<=0;
   if(start && state==IDLE) begin
    n<=n_items;rank<={4'b0,keep_k};shift<=first_shift;
    prefix<=0;mask<=0;eq_left<=0;req_base<=0;state<=HIST;
    for(hseq=0;hseq<16;hseq=hseq+1) hist[hseq]<=0;
   end
   if(req_valid && in_valid) begin
    iv<=1;ie<=(state==EMIT);ib<=req_base;data<=scores;
    if(req_base+L>=n) state<=(state==EMIT)?EWAIT:HWAIT;
    else req_base<=req_base+L;
   end
   if(iv && !ie) begin
    for(hseq=0;hseq<16;hseq=hseq+1) hist[hseq]<=hist[hseq]+increments[hseq];
    if(ib+L>=n) begin state<=BIN;bin<=15;end
   end
   if(state==BIN) begin
    if(rank>hist[bin]) begin rank<=rank-hist[bin];bin<=bin-1'b1;end
    else begin
     prefix<=prefix|({28'b0,bin}<<shift);
     mask<=mask|(32'hf<<shift);req_base<=0;
     if(shift==0) begin eq_left<=rank;state<=EMIT;end
     else begin
      shift<=shift-4;state<=HIST;
      for(hseq=0;hseq<16;hseq=hseq+1) hist[hseq]<=0;
     end
    end
   end
   if(iv && ie) begin
    out_valid<=1;out_base<=ib;out_mask<=selected;packed_indices<=packed_comb;
    out_count<=selected_count;eq_left<=remaining_eq;
    if(ib+L>=n) begin state<=IDLE;done<=1;end
   end
  end
 end
endmodule

// Signed11/F4 input -> Q0.16 probability (17 bits including unity) -> GQA sum19.
// Three SRAM score passes, exp recomputation, shared 41-step restoring reciprocal.
module screen_norm #(parameter L=16)(
 input wire clk,rst_n,start,in_valid,first_head,input wire [11:0] n_items,
 input wire [11*L-1:0] scores,input wire [19*L-1:0] group_previous,
 output wire req_valid,output reg [11:0] req_base,output wire [1:0] req_phase,
 output reg out_valid,output reg [11:0] out_base,
 output reg [19*L-1:0] group_result,output reg done
);
 localparam IDLE=0,MAXR=1,MAXW=2,SUMR=3,SUMW=4,DIVIDE=5,NORMR=6,NORMW=7;
 reg [2:0] state;reg [11:0] n;reg first;
 reg signed [10:0] maximum;
 reg [26:0] total;
 reg [27:0] remainder;reg [40:0] dividend,quotient;
 reg [25:0] reciprocal;reg [5:0] div_step;
 reg iv;reg [1:0] ip;reg [11:0] ib;
 reg [11*L-1:0] data;reg [19*L-1:0] prev;
 reg v0,v1;reg [11:0] tag0,tag1;
 reg [15:0] exp0[0:L-1];reg [41:0] product1[0:L-1];
 reg [19*L-1:0] prev0,prev1;
 wire signed [10:0] max_tree[1:2*L-1];
 wire [26:0] sum_tree[1:2*L-1];
 wire [15:0] exponent[0:L-1];
 wire [27:0] shifted_rem={remainder[26:0],dividend[40]};
 wire take=(shifted_rem>={1'b0,total});
 wire [40:0] q_next={quotient[39:0],take};
 integer j;
 `include "exp_function.vh"
 assign req_valid=(state==MAXR || state==SUMR || state==NORMR);
 assign req_phase=(state==MAXR)?0:(state==SUMR)?1:2;
 genvar g;
 generate
  for(g=0;g<L;g=g+1) begin:lane
   wire signed [10:0] x=$signed(data[g*11+:11]);
   wire signed [11:0] gap=(iv && ip!=0)?($signed(maximum)-x):12'sd0;
   assign exponent[g]=exp_lut((gap>255)?8'd255:gap[7:0]);
   assign max_tree[L+g]=x;
   assign sum_tree[L+g]={11'b0,exponent[g]};
  end
  for(g=1;g<L;g=g+1) begin:tree
   assign max_tree[g]=($signed(max_tree[2*g])>$signed(max_tree[2*g+1]))?max_tree[2*g]:max_tree[2*g+1];
   assign sum_tree[g]=sum_tree[2*g]+sum_tree[2*g+1];
  end
 endgenerate
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   state<=IDLE;req_base<=0;n<=0;first<=0;maximum<=-1024;total<=0;
   remainder<=0;dividend<=0;quotient<=0;reciprocal<=0;div_step<=0;
   iv<=0;ip<=0;ib<=0;data<=0;prev<=0;v0<=0;v1<=0;tag0<=0;tag1<=0;
   prev0<=0;prev1<=0;out_valid<=0;out_base<=0;group_result<=0;done<=0;
   for(j=0;j<L;j=j+1) begin exp0[j]<=0;product1[j]<=0;end
  end else begin
   iv<=0;v0<=0;v1<=v0;out_valid<=v1;done<=0;
   if(start && state==IDLE) begin
    state<=MAXR;req_base<=0;n<=n_items;first<=first_head;maximum<=-1024;total<=0;
   end
   if(req_valid && in_valid) begin
    iv<=1;ip<=req_phase;ib<=req_base;data<=scores;
    if(state==NORMR) prev<=first?{19*L{1'b0}}:group_previous;
    if(req_base+L>=n) begin
     if(state==MAXR) state<=MAXW;
     else if(state==SUMR) state<=SUMW;
     else state<=NORMW;
    end else req_base<=req_base+L;
   end
   if(iv) begin
    if(ip==0) begin
     if($signed(max_tree[1])>$signed(maximum)) maximum<=max_tree[1];
     if(ib+L>=n) begin state<=SUMR;req_base<=0;end
    end else if(ip==1) begin
     total<=total+sum_tree[1];
     if(ib+L>=n) begin
      state<=DIVIDE;remainder<=0;dividend<=41'h10000000000;quotient<=0;div_step<=0;
     end
    end else begin
     v0<=1;tag0<=ib;prev0<=prev;
     for(j=0;j<L;j=j+1) exp0[j]<=exponent[j];
    end
   end
   if(state==DIVIDE) begin
    remainder<=take?(shifted_rem-{1'b0,total}):shifted_rem;
    dividend<={dividend[39:0],1'b0};quotient<=q_next;
    if(div_step==40) begin reciprocal<=q_next[25:0];state<=NORMR;req_base<=0;end
    else div_step<=div_step+1'b1;
   end
   if(v0) begin
    tag1<=tag0;prev1<=prev0;
    for(j=0;j<L;j=j+1) product1[j]<=exp0[j]*reciprocal;
   end
   if(v1) begin
    out_base<=tag1;
    for(j=0;j<L;j=j+1)
     group_result[j*19+:19]<=prev1[j*19+:19]+((product1[j]+42'd8388608)>>24);
    if(tag1+L>=n) begin done<=1;state<=IDLE;end
   end
  end
 end
endmodule
