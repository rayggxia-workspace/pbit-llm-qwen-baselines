`timescale 1ns/1ps
// Two workers x two interleaved bank sets x sixteen128b banks =64 single1RW banks.
// Consecutive beats read alternating bank sets; writeback is three cycles later.
// A conflicting write/read or an in-flight same-address update stalls the read.
module plpu_prefill_state #(parameter AW=21,ROWS=256)(
 input wire clk,rst_n,flush,
 input wire [1:0] in_valid,output wire [1:0] in_ready,
 input wire [2*32*AW-1:0] in_count,input wire [191:0] in_meta,
 input wire [15:0] in_slot,input wire [3:0] in_beat,
 input wire signed [7:0] base_exp,
 output wire [1:0] out_valid,input wire [1:0] out_ready,
 output wire [4095:0] out_data,output wire [191:0] out_meta,
 output wire [3:0] out_beat,output wire [1:0] out_error,
 output wire [1:0] idle,output wire [1:0] bank_conflict,
 output wire [1:0] read_fire,write_fire
);
 genvar p,b,l;
 generate for(p=0;p<2;p=p+1)begin:worker
   reg v1,v2,v3;reg [95:0] m1,m2,m3;reg [1:0] beat1,beat2,beat3;
   reg [7:0] slot1,slot2,slot3;reg err1,err2,err3;
   reg [32*AW-1:0] count1;reg signed [8:0] delta1;
   reg [2047:0] prior1,prior2,aligned2,total3;
   wire [95:0] meta=in_meta[p*96+:96];wire [7:0] slot=in_slot[p*8+:8];
   wire [1:0] beat=in_beat[p*2+:2];
   wire [31:0] address=((32'(slot)>>1)<<1)+(beat>>1);
   wire [31:0] wa=((32'(slot3)>>1)<<1)+(beat3>>1);
   wire first=meta[31:16]==0;
   wire signed [7:0] ex=beat<2?$signed(meta[39:32]):$signed(meta[47:40]);
   wire signed [8:0] delta=$signed({ex[7],ex})-$signed({base_exp[7],base_exp});
   wire advance=!v3||out_ready[p];
   wire hazard=(v1&&slot1==slot&&beat1==beat)||(v2&&slot2==slot&&beat2==beat)||(v3&&slot3==slot&&beat3==beat);
   wire bank_busy=v3&&out_ready[p]&&beat3[0]==beat[0];
   assign bank_conflict[p]=in_valid[p]&&advance&&(bank_busy||hazard);
   assign in_ready[p]=rst_n&&!flush&&advance&&!bank_busy&&!hazard;
   wire take=in_valid[p]&&in_ready[p];wire put=v3&&out_ready[p]&&rst_n&&!flush;
   assign read_fire[p]=take&&!first;assign write_fire[p]=put;
   assign out_valid[p]=rst_n&&!flush&&v3;assign out_data[p*2048+:2048]=total3;
   assign out_meta[p*96+:96]=m3;assign out_beat[p*2+:2]=beat3;assign out_error[p]=err3;
   assign idle[p]=!v1&&!v2&&!v3;
   wire [4095:0] rd;
   for(b=0;b<2;b=b+1)begin:bankset
     for(l=0;l<16;l=l+1)begin:bank
       wire en=(take&&!first&&beat[0]==b)||(put&&beat3[0]==b);
       wire we=put&&beat3[0]==b;
       plpu_pf_state_bank #(.ROWS(ROWS)) mem(.clk(clk),.en(en),.we(we),
         .addr(we?wa:address),.wdata(total3[l*128+:128]),.rdata(rd[b*2048+l*128+:128]));
     end
   end
   integer j;reg signed [95:0] ext;reg signed [64:0] sum;
   // SRAM read is synchronous. rd is consumed in the following ALIGN stage.
   always @(posedge clk)begin
     if(!rst_n||flush)begin v1<=0;v2<=0;v3<=0;end
     else if(advance)begin
       v3<=v2;v2<=v1;v1<=take;
       if(take)begin count1<=in_count[p*32*AW+:32*AW];delta1<=delta;
         m1<=meta;slot1<=slot;beat1<=beat;
         err1<=delta<0||delta>31||slot[0]!=p||address>=ROWS;end
       if(v1)begin
         m2<=m1;slot2<=slot1;beat2<=beat1;err2<=err1;
         prior2<=m1[31:16]==0?2048'd0:(beat1[0]?rd[2048+:2048]:rd[0+:2048]);
         for(j=0;j<32;j=j+1)begin
           ext={{(96-AW){count1[j*AW+AW-1]}},count1[j*AW+:AW]};
           ext=ext<<<delta1;aligned2[j*64+:64]<=ext[63:0];
           if(delta1>=0&&delta1<=31&&ext!=$signed({{32{ext[63]}},ext[63:0]}))err2<=1;
         end
       end
       if(v2)begin
         m3<=m2;slot3<=slot2;beat3<=beat2;err3<=err2;
         for(j=0;j<32;j=j+1)begin
           sum=$signed({prior2[j*64+63],prior2[j*64+:64]})+$signed({aligned2[j*64+63],aligned2[j*64+:64]});
           total3[j*64+:64]<=sum[63:0];if(sum[64]!=sum[63])err3<=1;
         end
       end
     end
   end
`ifndef SYNTHESIS
   always @(posedge clk)if(rst_n&&!flush)begin
     if(take)assert(slot[0]==p&&address<ROWS) else $fatal(1,"state address");
     assert(!(put&&take&&!first&&beat3[0]==beat[0])) else $fatal(1,"single-port conflict");
   end
`endif
 end endgenerate
endmodule

module plpu_pf_state_bank #(parameter ROWS=256)(input wire clk,en,we,
 input wire [31:0] addr,input wire [127:0] wdata,output reg [127:0] rdata);
`ifndef SYNTHESIS
 reg [127:0] cells[0:ROWS-1];
 always @(posedge clk)if(en)begin
   assert(addr<ROWS) else $fatal(1,"bank range");
   if(we)cells[addr]<=wdata;else rdata<=cells[addr];
 end
`endif
endmodule
