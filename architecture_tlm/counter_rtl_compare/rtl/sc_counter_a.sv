// A: [output][bin][input sign][W8 bit] counters and exact signed reconstruction.
module sc_counter_a #(parameter integer N=64,M=1,T=32,BINS=4,PIPE=1,
 parameter integer CW=$clog2(N*T+1), SW=$clog2(N*T*128+1)+1)(
 input wire clk,rst_n,clear,accept,last,
 input wire [N*M*8-1:0] weights,
 input wire [N-1:0] bits,input_sign,true_one,
 input wire [N*2-1:0] input_bin,
 output wire update_valid,update_last,
 output wire [M*BINS*SW-1:0] sums);
 localparam integer PW=$clog2(N+1);
 localparam integer NC=M*BINS*2*8;
 wire [NC*PW-1:0] partial_comb,partial_use;
 wire [N-1:0] event_bits=bits|true_one;
 genvar o,b,s,k,i;
 generate
  for(o=0;o<M;o=o+1) begin: output_lane
   for(b=0;b<BINS;b=b+1) begin: bin_lane
    wire [16*SW-1:0] reconstruction;
    for(s=0;s<2;s=s+1) begin: sign_lane
     for(k=0;k<8;k=k+1) begin: plane
      localparam integer C=(((o*BINS+b)*2+s)*8+k);
      reg [CW-1:0] count;
      wire [N*PW-1:0] terms;
      wire [PW-1:0] population;
      for(i=0;i<N;i=i+1) begin: input_lane
       assign terms[i*PW+:PW]={{(PW-1){1'b0}},
        (event_bits[i] && input_sign[i]==s && input_bin[2*i+:2]==b && weights[(o*N+i)*8+k])};
      end
      sc_sum_tree #(.N(N),.W(PW)) popcount(.terms(terms),.total(population));
      assign partial_comb[C*PW+:PW]=population;
      wire signed [SW-1:0] extended=$signed({{(SW-CW){1'b0}},count});
      wire signed [SW-1:0] weighted=extended <<< k;
      if((s==0 && k<7)||(s==1 && k==7))
       assign reconstruction[(s*8+k)*SW+:SW]=weighted;
      else assign reconstruction[(s*8+k)*SW+:SW]=-weighted;
      always @(posedge clk) begin
       if(!rst_n || clear) count<=0;
       else if(update_valid) count<=count+partial_use[C*PW+:PW];
      end
     end
    end
    sc_sum_tree #(.N(16),.W(SW)) restore(.terms(reconstruction),.total(sums[(o*BINS+b)*SW+:SW]));
   end
  end
  if(PIPE!=0) begin: reduce_pipeline
   reg [NC*PW-1:0] data;
   reg valid,last_tag;
   always @(posedge clk) begin
    if(!rst_n) begin valid<=0;last_tag<=0;data<=0;end
    else begin
     valid<=accept;last_tag<=accept&&last;
     if(accept) data<=partial_comb;
    end
   end
   assign partial_use=data;assign update_valid=valid;assign update_last=last_tag;
  end else begin: unpipelined
   assign partial_use=partial_comb;assign update_valid=accept;assign update_last=accept&&last;
  end
 endgenerate
endmodule
