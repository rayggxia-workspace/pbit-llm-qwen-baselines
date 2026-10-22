`timescale 1ns/1ps
// Conventional single-clock SRAM bank wrapper only. SRAM macro data are external.
// No DFF weight array, no full tensor storage, no PRNG. One pending/response per
// requester; fixed-priority bank arbitration. WORD_BYTES,BANKS powers of2.
// Macro accepts bank_enable on rising edge, read data stable before next edge.
// Requesters must hold a blocked request; responses are held until ready.
module nr_sram_router #(parameter integer PORTS=16,BANKS=16,DATA_W=128,ROW_W=12)(
 input wire clk,rst_n,
 input wire [PORTS-1:0] req_valid,req_write,input wire [PORTS*32-1:0] req_address,
 input wire [PORTS*DATA_W-1:0] req_data,output reg [PORTS-1:0] req_ready,
 output reg [PORTS-1:0] rsp_valid,input wire [PORTS-1:0] rsp_ready,
 output reg [PORTS*DATA_W-1:0] rsp_data,
 input wire [BANKS-1:0] bank_ready,
 output reg [BANKS-1:0] bank_enable,bank_write,
 output reg [BANKS*ROW_W-1:0] bank_address,
 output reg [BANKS*DATA_W-1:0] bank_wdata,
 input wire [BANKS*DATA_W-1:0] bank_rdata
);
 localparam integer BYTE_BITS=$clog2(DATA_W/8),BANK_BITS=$clog2(BANKS),PW=$clog2(PORTS);
 reg [PORTS-1:0] busy;reg [BANKS-1:0] pending,pending_write;
 reg [PW-1:0] pending_owner[0:BANKS-1];integer owner[0:BANKS-1];
 integer b,p,address_bank;reg found;
 always @* begin
  req_ready=0;bank_enable=0;bank_write=0;bank_address=0;bank_wdata=0;found=0;address_bank=0;
  for(b=0;b<BANKS;b=b+1)begin
   owner[b]=0;found=0;
   for(p=0;p<PORTS;p=p+1)begin
    address_bank=(req_address[p*32+:32]>>BYTE_BITS)&(BANKS-1);
    if(!found&&req_valid[p]&&!busy[p]&&address_bank==b)begin
     found=1;owner[b]=p;req_ready[p]=bank_ready[b];bank_enable[b]=bank_ready[b];bank_write[b]=req_write[p];
     bank_address[b*ROW_W+:ROW_W]=req_address[p*32+:32]>>(BYTE_BITS+BANK_BITS);
     bank_wdata[b*DATA_W+:DATA_W]=req_data[p*DATA_W+:DATA_W];
    end
   end
  end
 end
 integer i,j;
 always @(posedge clk)begin
  if(!rst_n)begin
   busy<=0;pending<=0;pending_write<=0;rsp_valid<=0;rsp_data<=0;
   for(i=0;i<BANKS;i=i+1)pending_owner[i]<=0;
  end else begin
   for(j=0;j<PORTS;j=j+1)if(rsp_valid[j]&&rsp_ready[j])begin rsp_valid[j]<=0;busy[j]<=0;end
   for(i=0;i<BANKS;i=i+1)begin
    if(pending[i])begin
     rsp_valid[pending_owner[i]]<=1;
     rsp_data[pending_owner[i]*DATA_W+:DATA_W]<=pending_write[i]?{DATA_W{1'b0}}:bank_rdata[i*DATA_W+:DATA_W];
    end
    pending[i]<=bank_enable[i];pending_write[i]<=bank_write[i];
    if(bank_enable[i])begin pending_owner[i]<=owner[i];busy[owner[i]]<=1;end
   end
  end
 end
endmodule

// One DMA burst issue port, bounded window then drain; supplied memory completion.
// No DRAM PHY/controller or latency generator is hidden in this module.
// Mirrors the Link model's WINDOW boundary, not its assumed16GB/s throughput.
module nr_dma_window #(parameter integer WINDOW=32,BURST_BYTES=64)(
 input wire clk,rst_n,start,input wire [63:0] base,input wire [31:0] burst_count,
 output wire cmd_valid,input wire cmd_ready,output wire [63:0] cmd_address,
 input wire complete_valid,output wire complete_ready,
 output reg busy,done,output reg protocol_error
);
 reg [63:0] pointer;reg [31:0] remaining;
 reg [$clog2(WINDOW+1)-1:0] issued,outstanding;reg draining;
 wire issue=cmd_valid&&cmd_ready,retire=complete_valid&&complete_ready;
 assign cmd_valid=busy&&!draining&&remaining!=0;
 assign cmd_address=pointer;assign complete_ready=busy&&outstanding!=0;
 always @(posedge clk)begin
  if(!rst_n)begin pointer<=0;remaining<=0;issued<=0;outstanding<=0;draining<=0;busy<=0;done<=0;protocol_error<=0;end
  else begin
   done<=0;
   if(start&&!busy)begin
    pointer<=base;remaining<=burst_count;issued<=0;outstanding<=0;draining<=0;
    busy<=burst_count!=0;done<=burst_count==0;protocol_error<=0;
   end else if(busy)begin
    if(complete_valid&&!complete_ready)protocol_error<=1;
    case({issue,retire})2'b10:outstanding<=outstanding+1'b1;2'b01:outstanding<=outstanding-1'b1;default:begin end endcase
    if(issue)begin
     pointer<=pointer+BURST_BYTES;remaining<=remaining-1'b1;issued<=issued+1'b1;
     if(issued==WINDOW-1||remaining==1)draining<=1;
    end
    if(draining&&retire&&outstanding==1)begin
     if(remaining==0)begin busy<=0;done<=1;end
     else begin draining<=0;issued<=0;end
    end
   end
  end
 end
endmodule
