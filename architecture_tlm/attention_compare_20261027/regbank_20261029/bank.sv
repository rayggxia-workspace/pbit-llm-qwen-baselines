// 128 words, sixteen-word write port, all words locally visible in parallel.
// No data reset: the consumer must wait for all eight groups to be loaded.
module threshold_bank #(parameter W=12, GATED=1, COMPARE=0,
                        parameter OW=COMPARE ? 128 : 128*W)(
 input wire clk,wr_en,input wire [2:0] wr_group,
 input wire [16*W-1:0] wr_data,input wire [128*W-1:0] random_words,
 output wire [OW-1:0] result);
 wire [128*W-1:0] stored;
 genvar b,j;
 generate for(b=0;b<32;b=b+1) begin:banks
   wire en=wr_en && (wr_group==b/4);
   wire bc;
   if(GATED) begin:gated
     // Real library ICG, 48/64 clock loads per gate; not a free clock enable.
     CKGTX8_9TSVT cg(.CK(clk),.E(en),.TE(1'b0),.Q(bc));
   end else begin:ungated
     assign bc=clk;
   end
   for(j=0;j<4;j=j+1) begin:words
     reg [W-1:0] q;
     if(GATED) begin:g
       always @(posedge bc) q <= wr_data[((b%4)*4+j)*W +: W];
     end else begin:u
       always @(posedge bc) if(en) q <= wr_data[((b%4)*4+j)*W +: W];
     end
     assign stored[(b*4+j)*W +: W]=q;
   end
 end endgenerate
 generate if(COMPARE) begin:cmp
   for(j=0;j<128;j=j+1) begin:lanes
     assign result[j]=random_words[j*W +: W] < stored[j*W +: W];
   end
 end else begin:observe
   assign result=stored;
 end endgenerate
endmodule
