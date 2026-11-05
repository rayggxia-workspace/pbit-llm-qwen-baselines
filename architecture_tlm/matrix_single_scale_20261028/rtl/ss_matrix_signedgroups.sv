`timescale 1ns/1ps
// All x8 lanes share one external scale; W and X are true signed INT8.
// No per-lane bins, RNG, input encoder, weight storage or final scale converter.
module ssg_sum #(parameter N=64,LW=9,TW=LW+$clog2(N))(
 input wire [N*LW-1:0] leaves,output wire signed [TW-1:0] total);
 genvar l,k;
 generate for(l=0;l<$clog2(N);l=l+1) begin:level
  wire signed [LW+l:0] v[0:(N>>(l+1))-1];
  for(k=0;k<(N>>(l+1));k=k+1) begin:node
   wire signed [LW+l-1:0] a,b;
   if(l==0) begin
    assign a=leaves[2*k*LW+:LW];assign b=leaves[(2*k+1)*LW+:LW];
   end else begin assign a=level[l-1].v[2*k];assign b=level[l-1].v[2*k+1];end
   assign v[k]=$signed({a[LW+l-1],a})+$signed({b[LW+l-1],b});
  end
 end endgenerate
 assign total=level[$clog2(N)-1].v[0];
endmodule

module ss_matrix_signed #(parameter N=64,M=1,T=32,MODE=0)(
 input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [N*M*8-1:0] w8,input wire [N*8-1:0] x8,
 input wire [N-1:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [M*32-1:0] out_sum);
 localparam IDLE=0,RUN=1,DRAIN=2,BACKEND=3,RECOVER=4,OUTPUT=5;
 localparam SCW=20,DW=22,CW=6,PL=8;
 reg [2:0] state;reg [4:0] accepted;reg [3:0] bit_index;
 wire ff=frame_valid&&frame_ready,sf=sample_valid&&sample_ready;
 assign frame_ready=(state==IDLE);
 assign sample_ready=(state==RUN)&&(MODE!=4)&&(MODE!=5);
 assign out_valid=(state==OUTPUT);
 wire signed [8:0] weight[0:M*N-1];
 wire [7:0] magnitude[0:M*N-1];wire negative[0:M*N-1];
 wire [7:0] xmag[0:N-1];
 genvar m,n,p,g,l,k;
 generate for(n=0;n<N;n=n+1) begin:input_abs
  wire signed [8:0] a=$signed({x8[n*8+7],x8[n*8+:8]});
  assign xmag[n]=a[8] ? -a : a;
 end
 for(m=0;m<M;m=m+1) begin:weight_m
  for(n=0;n<N;n=n+1) begin:weight_n
   wire signed [8:0] a=$signed({w8[(m*N+n)*8+7],w8[(m*N+n)*8+:8]});
   assign weight[m*N+n]=x8[n*8+7] ? -a : a;
   assign magnitude[m*N+n]=a[8] ? -a : a;
   assign negative[m*N+n]=a[8]^x8[n*8+7];
  end
 end endgenerate
 wire [CW-1:0] input_count[0:N-1];
 generate if(MODE==2) begin:shared_counts
  for(n=0;n<N;n=n+1) begin:lane
   reg [CW-1:0] c;
   always @(posedge clk) begin
    if(!rst_n || ff) c<=0;
    else if(sf) c<=c+sample_bits[n];
   end
   assign input_count[n]=c;
  end
 end else begin:no_counts
  for(n=0;n<N;n=n+1) assign input_count[n]=0;
 end endgenerate
 wire pipe_done;
 generate if(MODE==0) begin:precise_pipeline
  reg [2:0] valid,last;
  always @(posedge clk) begin
   if(!rst_n || ff) begin valid<=0;last<=0;end
   else begin valid<={valid[1:0],sf};last<={last[1:0],sf&&(accepted==T-1)};end
  end
  assign pipe_done=valid[2]&&last[2];
  wire [N*M*9-1:0] leaves;
  for(m=0;m<M;m=m+1) begin:lm
   for(n=0;n<N;n=n+1) assign leaves[(m*N+n)*9+:9]=(sf&&sample_bits[n])?weight[m*N+n]:9'b0;
  end
  for(l=0;l<6;l=l+1) begin:level
   localparam NUM=N>>(l+1),SW=10+l,STAGE=l/2;
   wire signed [SW-1:0] value[0:M*NUM-1];
   for(m=0;m<M;m=m+1) begin:channel
    for(k=0;k<NUM;k=k+1) begin:node
     wire signed [SW-2:0] a,b;
     if(l==0) begin assign a=leaves[(m*N+2*k)*9+:9];assign b=leaves[(m*N+2*k+1)*9+:9];end
     else begin assign a=level[l-1].value[m*2*NUM+2*k];assign b=level[l-1].value[m*2*NUM+2*k+1];end
     wire signed [SW-1:0] sum=$signed({a[SW-2],a})+$signed({b[SW-2],b});
     if((l%2)==1) begin:cut
      reg signed [SW-1:0] q;
      wire en;
      if(STAGE==0) assign en=sf;else assign en=valid[STAGE-1];
      always @(posedge clk) begin if(!rst_n) q<=0;else if(en) q<=sum;end
      assign value[m*NUM+k]=q;
     end else assign value[m*NUM+k]=sum;
    end
   end
  end
  for(m=0;m<M;m=m+1) begin:acc
   reg signed [SCW-1:0] c;
   wire signed [14:0] reduced=level[5].value[m];
   always @(posedge clk) begin
    if(!rst_n || ff) c<=0;
    else if(valid[2]) c<=c+{{(SCW-15){reduced[14]}},reduced};
   end
   assign out_sum[m*32+:32]={{(32-SCW){c[SCW-1]}},c};
  end
 end else begin:other_modes
  assign pipe_done=0;
  for(m=0;m<M;m=m+1) begin:channel
   localparam RW=(MODE>=4 && MODE<=5)?DW:SCW;
   reg signed [RW-1:0] result;
   assign out_sum[m*32+:32]={{(32-RW){result[RW-1]}},result};
   if(MODE==1 || MODE==3 || MODE==6) begin:planes
    localparam PCW=(MODE==1)?13:11;
    wire signed [PCW-1:0] cplane[0:PL-1];
    for(p=0;p<PL;p=p+1) begin:plane
     wire [N-1:0] pos,neg;
     for(n=0;n<N;n=n+1) begin:select
      assign pos[n]=sample_bits[n]&magnitude[m*N+n][p]&!negative[m*N+n];
      assign neg[n]=sample_bits[n]&magnitude[m*N+n][p]&negative[m*N+n];
     end
     wire [15:0] gp,gn;
     for(g=0;g<16;g=g+1) begin:or4
      assign gp[g]=|pos[4*g+:4];assign gn[g]=|neg[4*g+:4];
     end
     if(MODE==6) begin:lane_temporal
      // One signed7 counter per group replaces separate positive/negative6 counters.
      // gp and gn remain separate ORs; only their TIME accumulation is combined.
      wire [16*7-1:0] counters;
      for(g=0;g<16;g=g+1) begin:counter
       wire signed [1:0] delta=$signed({1'b0,gp[g]})-$signed({1'b0,gn[g]});
       reg signed [6:0] c;
       always @(posedge clk) begin
        if(!rst_n || ff) c<=0;
        else if(sf) c<=c+{{5{delta[1]}},delta};
       end
       assign counters[g*7+:7]=c;
      end
      wire signed [10:0] count_sum;
      ssg_sum #(.N(16),.LW(7)) sum(counters,count_sum);
      assign cplane[p]=count_sum;
     end else begin:pop_temporal
      localparam PNUM=(MODE==1)?N:16;
      localparam PW=$clog2(PNUM)+2;
      wire [PNUM*2-1:0] pl,nl;
      wire signed [PW-1:0] ps,ns;
      for(g=0;g<PNUM;g=g+1) begin:extend
       if(MODE==1) begin assign pl[g*2+:2]={1'b0,pos[g]};assign nl[g*2+:2]={1'b0,neg[g]};end
       else begin assign pl[g*2+:2]={1'b0,gp[g]};assign nl[g*2+:2]={1'b0,gn[g]};end
      end
      ssg_sum #(.N(PNUM),.LW(2)) pt(pl,ps),nt(nl,ns);
      wire signed [PW:0] delta=$signed({ps[PW-1],ps})-$signed({ns[PW-1],ns});
      reg signed [PCW-1:0] c;
      always @(posedge clk) begin
       if(!rst_n || ff) c<=0;
       else if(sf) c<=c+{{(PCW-PW-1){delta[PW]}},delta};
      end
      assign cplane[p]=c;
     end
    end
    wire [PL*SCW-1:0] leaves;wire signed [SCW+2:0] recovered;
    for(p=0;p<PL;p=p+1) assign leaves[p*SCW+:SCW]=$signed({{(SCW-PCW){cplane[p][PCW-1]}},cplane[p]}) <<< p;
    ssg_sum #(.N(PL),.LW(SCW)) restore(leaves,recovered);
    always @(posedge clk) begin if(!rst_n) result<=0;else if(state==RECOVER) result<=recovered;end
   end else begin:weighted_backend
    localparam LW=(MODE==4)?16:9,TW=LW+6;
    wire [N*LW-1:0] leaves;wire signed [TW-1:0] sum;
    for(n=0;n<N;n=n+1) begin:lane
     if(MODE==4) begin:direct
      wire signed [7:0] a=w8[(m*N+n)*8+:8],b=x8[n*8+:8];
      assign leaves[n*LW+:LW]=a*b;
     end else begin:bitserial
      wire selected;
      if(MODE==2) assign selected=(state==BACKEND)&&input_count[n][bit_index];
      else assign selected=(state==BACKEND)&&xmag[n][bit_index];
      assign leaves[n*LW+:LW]=selected?weight[m*N+n]:9'b0;
     end
    end
    ssg_sum #(.N(N),.LW(LW)) tree(leaves,sum);
    wire signed [RW-1:0] extended={{(RW-TW){sum[TW-1]}},sum};
    always @(posedge clk) begin
     if(!rst_n || ff) begin if(MODE==4 && rst_n && ff) result<=extended;else result<=0;end
     else if(state==BACKEND) result<=(result <<< 1)+extended;
    end
   end
  end
 end endgenerate
 always @(posedge clk) begin
  if(!rst_n) begin state<=IDLE;accepted<=0;bit_index<=0;end
  else begin
   if(ff) begin
    accepted<=0;
    if(MODE==4) state<=OUTPUT;
    else if(MODE==5) begin state<=BACKEND;bit_index<=7;end
    else state<=RUN;
   end
   if(sf) begin
    if(accepted==T-1) begin
     if(MODE==0) state<=DRAIN;
     else if(MODE==2) begin state<=BACKEND;bit_index<=5;end
     else state<=RECOVER;
    end else accepted<=accepted+1'b1;
   end
   if(state==BACKEND) begin if(bit_index==0) state<=OUTPUT;else bit_index<=bit_index-1'b1;end
   if(state==RECOVER || pipe_done) state<=OUTPUT;
   if(out_valid&&out_ready) state<=IDLE;
  end
 end
`ifndef SYNTHESIS
 initial if(N!=64 || T!=32 || M<1 || MODE<0 || MODE>6) $fatal(1,"unsupported single-scale geometry");
`endif
endmodule
