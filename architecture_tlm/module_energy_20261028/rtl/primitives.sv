`timescale 1ns/1ps
module me_pop #(parameter N=16,W=$clog2(N)+1)(input wire [N-1:0] bits,output wire [W-1:0] count);
genvar l,k;generate for(l=0;l<$clog2(N);l=l+1) begin:level
 wire [l+1:0] v[0:(N>>(l+1))-1];
 for(k=0;k<(N>>(l+1));k=k+1) begin:node
  if(l==0) assign v[k]={1'b0,bits[2*k]}+{1'b0,bits[2*k+1]};
  else assign v[k]={1'b0,level[l-1].v[2*k]}+{1'b0,level[l-1].v[2*k+1]};
 end
end endgenerate
assign count=level[$clog2(N)-1].v[0];endmodule
module me_diff #(parameter N=16,W=$clog2(N)+1)(input wire [2*N-1:0] bits,output wire signed [W:0] delta);
wire [W-1:0] p,n;me_pop #(.N(N)) pt(bits[N-1:0],p),nt(bits[2*N-1:N],n);
assign delta=$signed({1'b0,p})-$signed({1'b0,n});endmodule
module me_mask #(parameter N=64)(input wire [3*N-1:0] din,output wire [N/2-1:0] grouped);
wire [N-1:0] pos,neg;genvar i,g;generate
for(i=0;i<N;i=i+1) begin:lane
 assign pos[i]=din[i]&din[N+i]&!din[2*N+i];
 assign neg[i]=din[i]&din[N+i]&din[2*N+i];
end
for(g=0;g<N/4;g=g+1) begin:or4
 assign grouped[g]=|pos[4*g+:4];assign grouped[N/4+g]=|neg[4*g+:4];
end endgenerate endmodule
module me_acc #(parameter B=9,D=6,R=((B>D)?B:D)+1)(input wire clk,rst_n,clear,en,input wire signed [D-1:0] delta,output reg signed [B-1:0] value);
localparam signed [R-1:0] HI=(1<<(B-1))-1,LO=-(1<<(B-1));
wire signed [R-1:0] a={{(R-B){value[B-1]}},value},b={{(R-D){delta[D-1]}},delta};
wire signed [R-1:0] sum=a+b;
always @(posedge clk) begin
 if(!rst_n || clear) value<=0;
 else if(en) begin if(sum>HI) value<=HI[B-1:0];else if(sum<LO) value<=LO[B-1:0];else value<=sum[B-1:0];end
end endmodule
module me_plane #(parameter B=9)(input wire clk,rst_n,clear,en,input wire [191:0] din,output wire signed [B-1:0] value);
wire [31:0] grouped;wire signed [5:0] delta;me_mask mask(din,grouped);me_diff diff(grouped,delta);me_acc #(.B(B)) acc(clk,rst_n,clear,en,delta,value);endmodule
module me_sum #(parameter N=8,LW=16,TW=LW+$clog2(N))(input wire [N*LW-1:0] leaves,output wire signed [TW-1:0] total);
genvar l,k;generate for(l=0;l<$clog2(N);l=l+1) begin:level
 wire signed [LW+l:0] v[0:(N>>(l+1))-1];
 for(k=0;k<(N>>(l+1));k=k+1) begin:node
  wire signed [LW+l-1:0] a,b;
  if(l==0) begin assign a=leaves[2*k*LW+:LW];assign b=leaves[(2*k+1)*LW+:LW];end
  else begin assign a=level[l-1].v[2*k];assign b=level[l-1].v[2*k+1];end
  assign v[k]=$signed({a[LW+l-1],a})+$signed({b[LW+l-1],b});
 end
end endgenerate assign total=level[$clog2(N)-1].v[0];endmodule
