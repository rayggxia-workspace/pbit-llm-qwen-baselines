// B: signed per-sample W8 contribution, followed by one integer state per bin.
// Sign extension to nine bits BEFORE negation is essential for -(-128)=+128.
module sc_counter_b #(parameter integer N=64,M=1,T=32,BINS=4,PIPE=1,
 parameter integer SW=$clog2(N*T*128+1)+1)(
 input wire clk,rst_n,clear,accept,last,
 input wire [N*M*8-1:0] weights,
 input wire [N-1:0] bits,input_sign,true_one,
 input wire [N*2-1:0] input_bin,
 output wire update_valid,update_last,
 output wire [M*BINS*SW-1:0] sums);
 localparam integer PW=$clog2(N*128+1)+1;
 localparam integer NC=M*BINS;
 wire [NC*PW-1:0] partial_comb,partial_use;
 wire [N-1:0] event_bits=bits|true_one;
 genvar o,b,i;
 generate
  for(o=0;o<M;o=o+1) begin: output_lane
   wire [N*9-1:0] signed_weights;
   for(i=0;i<N;i=i+1) begin: sign_adjust
    wire signed [8:0] w=$signed({weights[(o*N+i)*8+7],weights[(o*N+i)*8+:8]});
    assign signed_weights[i*9+:9]=input_sign[i] ? -w : w;
   end
   for(b=0;b<BINS;b=b+1) begin: bin_lane
    localparam integer C=o*BINS+b;
    reg signed [SW-1:0] accumulated;
    wire [N*PW-1:0] terms;
    for(i=0;i<N;i=i+1) begin: input_lane
     wire signed [8:0] w=$signed(signed_weights[i*9+:9]);
     assign terms[i*PW+:PW]=(event_bits[i] && input_bin[2*i+:2]==b) ?
       {{(PW-9){w[8]}},w} : {PW{1'b0}};
    end
    sc_sum_tree #(.N(N),.W(PW)) reduction(.terms(terms),.total(partial_comb[C*PW+:PW]));
    wire signed [PW-1:0] part=$signed(partial_use[C*PW+:PW]);
    always @(posedge clk) begin
     if(!rst_n || clear) accumulated<=0;
     else if(update_valid) accumulated<=accumulated+{{(SW-PW){part[PW-1]}},part};
    end
    assign sums[C*SW+:SW]=accumulated;
   end
  end
  if(PIPE!=0) begin: reduce_pipeline
   reg [NC*PW-1:0] data;
   reg valid,last_tag;
   always @(posedge clk) begin
    if(!rst_n) begin valid<=0;last_tag<=0;data<=0;end
    else begin valid<=accept;last_tag<=accept&&last;if(accept)data<=partial_comb;end
   end
   assign partial_use=data;assign update_valid=valid;assign update_last=last_tag;
  end else begin: unpipelined
   assign partial_use=partial_comb;assign update_valid=accept;assign update_last=accept&&last;
  end
 endgenerate
endmodule
