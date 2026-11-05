`timescale 1ns/1ps
// Common fixed-frame interface. Configuration is externally resident and stable
// from frame acceptance until output acceptance. q9 encodes magnitude 0..256.
// S0/S1/S2 are same-event exact. S3 is a different, lossy OR4 algorithm.
module mv_popcount #(parameter N=64, W=$clog2(N)+1)(
 input wire [N-1:0] bits, output wire [W-1:0] count);
 genvar l,k;
 generate for(l=0;l<$clog2(N);l=l+1) begin:level
  wire [l+1:0] v[0:(N>>(l+1))-1];
  for(k=0;k<(N>>(l+1));k=k+1) begin:node
   if(l==0) assign v[k]={1'b0,bits[2*k]}+{1'b0,bits[2*k+1]};
   else assign v[k]={1'b0,level[l-1].v[2*k]}+{1'b0,level[l-1].v[2*k+1]};
  end
 end endgenerate
 assign count=level[$clog2(N)-1].v[0];
endmodule

module mv_sumtree #(parameter N=64, LW=14, TW=LW+$clog2(N))(
 input wire [N*LW-1:0] leaves,output wire signed [TW-1:0] total);
 genvar l,k;
 generate for(l=0;l<$clog2(N);l=l+1) begin:level
  wire signed [LW+l:0] v[0:(N>>(l+1))-1];
  for(k=0;k<(N>>(l+1));k=k+1) begin:node
   wire signed [LW+l-1:0] a,b;
   if(l==0) begin
    assign a=leaves[(2*k)*LW+:LW]; assign b=leaves[(2*k+1)*LW+:LW];
   end else begin
    assign a=level[l-1].v[2*k]; assign b=level[l-1].v[2*k+1];
   end
   assign v[k]=$signed({a[LW+l-1],a})+$signed({b[LW+l-1],b});
  end
 end endgenerate
 assign total=level[$clog2(N)-1].v[0];
endmodule

module matrix_variant #(parameter N=64,M=1,T=32,MODE=1,AW=32)(
 input wire clk,rst_n,
 input wire frame_valid,output wire frame_ready,
 input wire [N*M*7-1:0] w_mag7,input wire [N*M-1:0] w_sign,
 input wire [N-1:0] x_sign,input wire [N*3-1:0] bin_id,
 input wire [N*9-1:0] q9,
 input wire [N-1:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [M*AW-1:0] out_sum);
 localparam IDLE=0,RUN=1,BACKEND=2,RECOVER=3,OUTPUT=4;
 localparam CW=$clog2(T+1), PCW=(MODE==3)?11:13;
 reg [2:0] state;
 reg [CW-1:0] accepted;
 reg [3:0] bit_index;
 wire ff=frame_valid&&frame_ready, sf=sample_valid&&sample_ready;
 assign frame_ready=state==IDLE;
 assign sample_ready=(state==RUN)&&(MODE!=4)&&(MODE!=5);
 assign out_valid=state==OUTPUT;
 wire [12:0] aligned[0:M*N-1];
 wire neg[0:M*N-1];
 genvar m,n,p,g,k;
 generate for(m=0;m<M;m=m+1) begin:weights_m
  for(n=0;n<N;n=n+1) begin:weights_n
   wire [2:0] b=bin_id[3*n+:3];
   assign aligned[m*N+n]=(b<4)?({6'b0,w_mag7[(m*N+n)*7+:7]} << (2*(3-b))):13'b0;
   assign neg[m*N+n]=w_sign[m*N+n]^x_sign[n];
  end
 end endgenerate
 // MODE2 shares the input event counts across every output column.
 wire [CW-1:0] counts[0:N-1];
 generate if(MODE==2) begin:input_counts
  for(n=0;n<N;n=n+1) begin:lane
   reg [CW-1:0] c;
   always @(posedge clk) begin
    if(!rst_n || ff) c<=0;
    else if(sf) c<=c+sample_bits[n];
   end
   assign counts[n]=c;
  end
 end else begin:no_input_counts
  for(n=0;n<N;n=n+1) assign counts[n]=0;
 end endgenerate

 generate for(m=0;m<M;m=m+1) begin:outputs
  reg signed [AW-1:0] result;
  assign out_sum[m*AW+:AW]=result;
  if(MODE==1 || MODE==3) begin:plane_backend
   wire signed [PCW-1:0] plane[0:12];
   for(p=0;p<13;p=p+1) begin:planes
    wire [N-1:0] pos,minus;
    for(n=0;n<N;n=n+1) begin:events
     assign pos[n]=sample_bits[n] & aligned[m*N+n][p] & !neg[m*N+n];
     assign minus[n]=sample_bits[n] & aligned[m*N+n][p] & neg[m*N+n];
    end
    wire [6:0] positive_count,negative_count;
    if(MODE==3) begin:or4
     wire [N/4-1:0] gp,gn;
     wire [$clog2(N/4):0] cp,cn;
     for(g=0;g<N/4;g=g+1) begin:groups
      assign gp[g]=|pos[4*g+:4]; assign gn[g]=|minus[4*g+:4];
     end
     mv_popcount #(.N(N/4)) pp(gp,cp),pn(gn,cn);
     assign positive_count=cp; assign negative_count=cn;
    end else begin:exact
     mv_popcount #(.N(N)) pp(pos,positive_count),pn(minus,negative_count);
    end
    wire signed [7:0] delta=$signed({1'b0,positive_count})-$signed({1'b0,negative_count});
    reg signed [PCW-1:0] c;
    always @(posedge clk) begin
     if(!rst_n || ff) c<=0;
     else if(sf) c<=c+{{(PCW-8){delta[7]}},delta};
    end
    assign plane[p]=c;
   end
   wire [16*AW-1:0] recovered_leaves;
   wire signed [AW+3:0] recovered;
   for(k=0;k<16;k=k+1) begin:restore_leaves
    if(k<13) assign recovered_leaves[k*AW+:AW]=$signed({{(AW-PCW){plane[k][PCW-1]}},plane[k]}) <<< k;
    else assign recovered_leaves[k*AW+:AW]=0;
   end
   mv_sumtree #(.N(16),.LW(AW)) recovery_tree(recovered_leaves,recovered);
   always @(posedge clk) begin
    if(!rst_n) result<=0;
    else if(state==RECOVER) result<=recovered;
   end
  end else begin:weighted_backend
   localparam LW=(MODE==4)?23:14;
   localparam TW=LW+$clog2(N);
   wire [N*LW-1:0] leaves;
   wire signed [TW-1:0] sum;
   for(n=0;n<N;n=n+1) begin:lane
    wire selected;
    // Operand isolation: do not exercise the wide backend while collecting events.
    if(MODE==2) assign selected=(state==BACKEND) && counts[n][bit_index];
    else if(MODE==5) assign selected=(state==BACKEND) && q9[n*9+bit_index];
    else assign selected=1'b1;
    wire signed [13:0] a=neg[m*N+n] ? -$signed({1'b0,aligned[m*N+n]}) : $signed({1'b0,aligned[m*N+n]});
    if(MODE==4) begin:product
     // Extend positive q9 to signed10; product fits signed23 over q<=256.
     wire signed [23:0] prod=a*$signed({1'b0,q9[n*9+:9]});
     assign leaves[n*LW+:LW]=prod[22:0];
    end else assign leaves[n*LW+:LW]=selected?a:14'b0;
   end
   mv_sumtree #(.N(N),.LW(LW)) tree(leaves,sum);
   wire signed [AW-1:0] extended={{(AW-TW){sum[TW-1]}},sum};
   always @(posedge clk) begin
    if(!rst_n || ff) begin
     if(MODE==4 && rst_n && ff) result<=extended;
     else result<=0;
    end else if(state==BACKEND) result<=(result <<< 1)+extended;
   end
  end
 end endgenerate
 always @(posedge clk) begin
  if(!rst_n) begin state<=IDLE;accepted<=0;bit_index<=0;end
  else begin
   if(ff) begin
    accepted<=0;
    if(MODE==4) state<=OUTPUT;
    else if(MODE==5) begin state<=BACKEND;bit_index<=8;end
    else state<=RUN;
   end
   if(sf) begin
    if(accepted==T-1) begin
     if(MODE==2) begin state<=BACKEND;bit_index<=CW-1;end
     else state<=RECOVER;
    end else accepted<=accepted+1'b1;
   end
   if(state==BACKEND) begin
    if(bit_index==0) state<=OUTPUT;
    else bit_index<=bit_index-1'b1;
   end
   if(state==RECOVER) state<=OUTPUT;
   if(out_valid&&out_ready) state<=IDLE;
  end
 end
`ifndef SYNTHESIS
 initial if(N!=64 || T!=32 || AW!=32 || M<1 || MODE<1 || MODE>5) $fatal(1,"unsupported geometry");
`endif
endmodule
