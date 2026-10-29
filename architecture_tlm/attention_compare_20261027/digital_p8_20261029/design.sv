// FP32 -> signed11/F4 -> exp Q1.15 -> one reciprocal -> conserved Q0.8 mass.
// Probability256 uses an explicit singleton flag/index instead of silently saturating.
module softmax_p8 #(parameter L=4)(
 input wire clk,rst_n,start,load_valid,
 input wire [32*L-1:0] score_in,
 output wire load_ready,output reg ready,
 output wire [1023:0] probability,output reg full_mass,output reg [6:0] full_index,
 output reg invalid,clipped
);
 localparam IDLE=0,LOAD=1,EXP=2,RECIP=3,NORM=4;
 reg [2:0] state;
 reg [7:0] ix,issue_ix;
 reg signed [10:0] score_mem[0:127];
 reg [15:0] exp_mem[0:127];
 reg [7:0] q_mem[0:127];
 reg signed [10:0] maximum;
 reg [22:0] sum,prefix;
 reg [23:0] remainder;
 reg [17:0] reciprocal;
 reg [5:0] reciprocal_step;
 reg [2:0] valid_pipe;
 reg [6:0] tag0,tag1,tag2;
 reg [22:0] cumulative0[0:L-1],cumulative1[0:L-1];
 reg [40:0] product1[0:L-1];
 reg [8:0] cdf2[0:L-1],previous_cdf;
 wire [12:0] converted[0:L-1];
 wire [L-1:0] conversion_invalid,conversion_clipped;
 wire signed [10:0] max_tree[1:2*L-1];
 wire [15:0] exponent[0:L-1];
 wire [22:0] exp_sum_tree[1:2*L-1];
 wire [22:0] cumulative[0:L];
 wire [9:0] candidate[0:L-1];
 wire [32:0] correction_product[0:L-1];
 wire [8:0] quantized[0:L-1];
 wire [24:0] shifted_remainder={remainder,1'b0};
 wire reciprocal_bit=(shifted_remainder>={2'b0,sum});
 integer j;

 // Return {invalid, clipped, signed11}; round-to-nearest-even, saturation.
 function [12:0] convert;
  input [31:0] f;
  reg [7:0] e;reg [23:0] m;
  reg [24:0] whole,mask;reg guard,sticky,clip;
  reg signed [11:0] v;integer shift;
  begin
   e=f[30:23];m={1'b1,f[22:0]};whole=0;mask=0;guard=0;sticky=0;clip=0;v=0;shift=0;
   if(e==255) convert={1'b1,1'b0,11'b0};
   else begin
    if(e>132) begin
     whole=f[31]?25'd1024:25'd1023;
     clip=!(f[31] && e==133 && f[22:0]==0);
    end else if(e>=122) begin
     shift=146-e;
     whole={1'b0,m}>>shift;
     guard=(m>>(shift-1))&1;
     mask=(25'd1<<(shift-1))-1;
     sticky=|(m&mask);
     whole=whole+(guard&&(sticky||whole[0]));
     if(!f[31] && whole>1023) begin whole=1023;clip=1;end
     if(f[31] && whole>1024) begin whole=1024;clip=1;end
    end
    v=f[31]?-$signed({1'b0,whole[10:0]}):$signed({1'b0,whole[10:0]});
    convert={1'b0,clip,v[10:0]};
   end
  end
 endfunction
 `include "exp_function.vh"
 genvar g;
 generate
  for(g=0;g<128;g=g+1) begin:pack
   assign probability[g*8+:8]=q_mem[g];
  end
  for(g=0;g<L;g=g+1) begin:lanes
   wire signed [11:0] gap=$signed(maximum)-$signed(score_mem[ix+g]);
   assign converted[g]=convert(score_in[g*32+:32]);
   assign max_tree[L+g]=$signed(converted[g][10:0]);
   assign exponent[g]=exp_lut((gap>255)?8'd255:gap[7:0]);
   assign exp_sum_tree[L+g]={7'b0,exponent[g]};
   assign cumulative[g+1]=cumulative[g]+exp_mem[issue_ix[6:0]+g];
   assign candidate[g]={1'b0,product1[g][32:24]}+10'd1;
   assign correction_product[g]=candidate[g]*sum;
   if(g==0) assign quantized[g]=cdf2[g]-previous_cdf;
   else assign quantized[g]=cdf2[g]-cdf2[g-1];
  end
  for(g=1;g<L;g=g+1) begin:trees
   assign max_tree[g]=($signed(max_tree[2*g])>$signed(max_tree[2*g+1]))?max_tree[2*g]:max_tree[2*g+1];
   assign exp_sum_tree[g]=exp_sum_tree[2*g]+exp_sum_tree[2*g+1];
  end
 endgenerate
 assign cumulative[0]=prefix;
 assign load_ready=(state==LOAD);
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin
   state<=IDLE;ix<=0;issue_ix<=0;maximum<=-1024;sum<=0;prefix<=0;
   remainder<=0;reciprocal<=0;reciprocal_step<=0;valid_pipe<=0;
   tag0<=0;tag1<=0;tag2<=0;previous_cdf<=0;ready<=0;full_mass<=0;full_index<=0;invalid<=0;clipped<=0;
   for(j=0;j<128;j=j+1) begin score_mem[j]<=0;exp_mem[j]<=0;q_mem[j]<=0;end
   for(j=0;j<L;j=j+1) begin cumulative0[j]<=0;cumulative1[j]<=0;product1[j]<=0;cdf2[j]<=0;end
  end else begin
   ready<=0;
   case(state)
    IDLE:if(start) begin state<=LOAD;ix<=0;maximum<=-1024;full_mass<=0;invalid<=0;clipped<=0;end
    LOAD:if(load_valid) begin
     for(j=0;j<L;j=j+1) begin
      score_mem[ix+j]<=$signed(converted[j][10:0]);
     end
     // Explicit OR reductions; no last-lane nonblocking-assignment overwrite.
     if(|conversion_invalid) invalid<=1;
     if(|conversion_clipped) clipped<=1;
     if($signed(max_tree[1])>$signed(maximum)) maximum<=max_tree[1];
     if(ix==128-L) begin ix<=0;sum<=0;state<=EXP;end else ix<=ix+L;
    end
    EXP:begin
     for(j=0;j<L;j=j+1) exp_mem[ix+j]<=exponent[j];
     sum<=sum+exp_sum_tree[1];
     if(ix==128-L) begin state<=RECIP;remainder<=1;reciprocal<=0;reciprocal_step<=0;end else ix<=ix+L;
    end
    RECIP:begin
     remainder<=reciprocal_bit?(shifted_remainder-{2'b0,sum}):shifted_remainder;
     reciprocal<={reciprocal[16:0],reciprocal_bit};
     if(reciprocal_step==31) begin state<=NORM;issue_ix<=0;prefix<=0;valid_pipe<=0;previous_cdf<=0;end
     else reciprocal_step<=reciprocal_step+1;
    end
    NORM:begin
     valid_pipe<={valid_pipe[1:0],(issue_ix<128)};
     if(issue_ix<128) begin
      for(j=0;j<L;j=j+1) cumulative0[j]<=cumulative[j+1];
      prefix<=cumulative[L];tag0<=issue_ix[6:0];issue_ix<=issue_ix+L;
     end
     if(valid_pipe[0]) begin
      for(j=0;j<L;j=j+1) begin product1[j]<=cumulative0[j]*reciprocal;cumulative1[j]<=cumulative0[j];end
      tag1<=tag0;
     end
     if(valid_pipe[1]) begin
      for(j=0;j<L;j=j+1) cdf2[j]<=product1[j][32:24]+(correction_product[j]<={2'b0,cumulative1[j],8'b0});
      tag2<=tag1;
     end
     if(valid_pipe[2]) begin
      for(j=0;j<L;j=j+1) begin
       q_mem[tag2+j]<=quantized[j][7:0];
       if(quantized[j]==256) begin full_mass<=1;full_index<=tag2+j;end
      end
      previous_cdf<=cdf2[L-1];
      if(tag2==128-L) begin state<=IDLE;ready<=1;end
     end
    end
   endcase
  end
 end
 generate for(g=0;g<L;g=g+1) begin:flags
  assign conversion_invalid[g]=converted[g][12];
  assign conversion_clipped[g]=converted[g][11];
 end endgenerate
endmodule

// Compact continuous-state Bivium wrapper: no endpoint checkpoint/epoch service.
// Explicit177-bit states supplied in6 big-endian32-bit beats/core, then5*160 warm bits.
module random_farm #(parameter G=7)(
 input wire clk,rst_n,seed_valid,step,input wire [31:0] seed_data,
 output wire seed_ready,output wire ready,output wire [G*160-1:0] words
);
 reg [176:0] state[0:G-1];wire [176:0] next_state[0:G-1];
 reg [5:0] loaded;reg [2:0] warm;integer k;genvar g;
 assign seed_ready=(loaded<6*G);
 assign ready=(loaded==6*G && warm==5);
 generate for(g=0;g<G;g=g+1) begin:cores
  rng_bivium_map map(.state(state[g]),.random_word(words[g*160+:160]),.next_state(next_state[g]));
 end endgenerate
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin loaded<=0;warm<=0;for(k=0;k<G;k=k+1)state[k]<=0;end
  else if(seed_valid && seed_ready) begin
   for(k=0;k<G;k=k+1) if(loaded>=6*k && loaded<6*(k+1)) state[k]<={state[k][144:0],seed_data};
   loaded<=loaded+1;
  end else if(loaded==6*G && warm<5) begin
   for(k=0;k<G;k=k+1) state[k]<=next_state[k];warm<=warm+1;
  end else if(ready && step) begin
   for(k=0;k<G;k=k+1) state[k]<=next_state[k];
  end
 end
endmodule

// MODE0 frontend probability stream; MODE1 systematic counts; MODE2 Bernoulli128 rounds.
module digital_sampler #(parameter L=4,MODE=1)(
 input wire clk,rst_n,start,load_valid,out_ready,seed_valid,
 input wire [32*L-1:0] score_in,input wire [31:0] seed_data,
 output wire start_ready,load_ready,seed_ready,front_done,
 output wire out_valid,output wire [6:0] out_index,output wire [9*L-1:0] out_count,
 output wire done,invalid,clipped
);
 localparam WAIT=0,FRONT=1,KICK=2,SAMPLE=3,EMIT=4,FINISH=5;
 reg [2:0] state;reg [6:0] emit_index;reg [7:0] round,phase;
 reg [7:0] histogram[0:127];
 wire [1023:0] q8;wire full_mass;wire [6:0] full_index;
 localparam G=(MODE==2)?7:1;
 wire [G*160-1:0] random_words;wire rng_ready,rng_step;
 wire [1119:0] padded_random={{(1120-G*160){1'b0}},random_words};
 wire core_start=start && start_ready;
 softmax_p8 #(L) front(.clk(clk),.rst_n(rst_n),.start(core_start),.load_valid(load_valid),.score_in(score_in),
  .load_ready(load_ready),.ready(front_done),.probability(q8),.full_mass(full_mass),.full_index(full_index),.invalid(invalid),.clipped(clipped));
 generate if(MODE!=0) begin:rng
  random_farm #(G) farm(.clk(clk),.rst_n(rst_n),.seed_valid(seed_valid),.seed_data(seed_data),.seed_ready(seed_ready),
   .step(rng_step),.ready(rng_ready),.words(random_words));
 end else begin:no_rng
  assign seed_ready=0;assign rng_ready=1;assign random_words=0;
 end endgenerate
 assign rng_step=(MODE==1 && state==KICK)||(MODE==2 && state==SAMPLE);
 assign start_ready=(state==WAIT && rng_ready);
 assign out_valid=(state==EMIT);
 assign out_index=emit_index;
 assign done=(state==FINISH);
 wire [7:0] fraction[0:L];wire [15:0] phase_sum[0:L-1];wire [8:0] emit_probability[0:L-1];
 assign fraction[0]=phase;
 genvar g;
 generate for(g=0;g<L;g=g+1) begin:emit_lanes
  assign emit_probability[g]=(full_mass && full_index==emit_index+g)?9'd256:{1'b0,q8[(emit_index+g)*8+:8]};
  assign phase_sum[g]={8'b0,fraction[g]}+{emit_probability[g],7'b0};
  assign fraction[g+1]=phase_sum[g][7:0];
  if(MODE==0) assign out_count[g*9+:9]=emit_probability[g];
  else if(MODE==1) assign out_count[g*9+:9]={1'b0,phase_sum[g][15:8]};
  else assign out_count[g*9+:9]={1'b0,histogram[emit_index+g]};
 end endgenerate
 integer j;
 always @(posedge clk or negedge rst_n) begin
  if(!rst_n) begin state<=WAIT;emit_index<=0;round<=0;phase<=0;for(j=0;j<128;j=j+1)histogram[j]<=0;end
  else begin
   case(state)
    WAIT:if(core_start) begin state<=FRONT;emit_index<=0;round<=0;for(j=0;j<128;j=j+1)histogram[j]<=0;end
    FRONT:if(front_done)state<=KICK;
    KICK:begin
     emit_index<=0;
     if(MODE==2) begin round<=0;state<=SAMPLE;end
     else begin phase<=random_words[7:0];state<=EMIT;end
    end
    SAMPLE:begin
     for(j=0;j<128;j=j+1)
      if((full_mass && full_index==j) || (padded_random[j*8+:8]<q8[j*8+:8])) histogram[j]<=histogram[j]+1;
     if(round==127)state<=EMIT;else round<=round+1;
    end
    EMIT:if(out_ready) begin
     phase<=fraction[L];
     if(emit_index==128-L)state<=FINISH;else emit_index<=emit_index+L;
    end
    FINISH:state<=WAIT;
   endcase
  end
 end
endmodule
