`timescale 1ns/1ps
// Control-only model sequence. Embedding visits all prompt blocks, layers
// visit those same blocks, final norm/head visits the last prompt row once.
// svc opcode: 0 embedding,1 decoder-layer,2 final-norm/head.
module plpu_prefill_prompt(
 input wire clk,rst_n,cancel,
 input wire cmd_valid,output wire cmd_ready,
 input wire [15:0] cmd_length,cmd_past,input wire [7:0] cmd_layers,
 input wire [5:0] cmd_block_rows,
 output wire svc_valid,input wire svc_ready,
 output wire [1:0] svc_opcode,output wire [7:0] svc_layer,
 output wire [15:0] svc_row_base,svc_position,output wire [5:0] svc_rows,
 input wire svc_done_valid,output wire svc_done_ready,
 output wire done_valid,input wire done_ready,output wire [15:0] decode_position
);
 localparam IDLE=0,OFFER=1,WAIT=2,DONE=3;
 reg [1:0] state,op;reg [15:0] length,past,row_base;
 reg [7:0] layers,layer_id;reg [5:0] block_rows;
 wire [16:0] remain={1'b0,length}-{1'b0,row_base};
 wire [5:0] nr=remain>block_rows?block_rows:6'(remain);
 assign cmd_ready=rst_n&&state==IDLE&&!cancel;
 assign svc_valid=rst_n&&state==OFFER&&!cancel;
 assign svc_opcode=op;assign svc_layer=layer_id;
 assign svc_row_base=row_base;assign svc_position=past+row_base;
 assign svc_rows=op==2?6'd1:nr;
 // Cancellation drains an already accepted service before returning idle.
 reg cancelled;
 assign svc_done_ready=rst_n&&state==WAIT;
 assign done_valid=rst_n&&state==DONE&&!cancelled;
 assign decode_position=past+length;
 always @(posedge clk)begin
  if(!rst_n)begin state<=IDLE;cancelled<=0;end
  else begin
   if(cmd_valid&&cmd_ready)begin length<=cmd_length;past<=cmd_past;layers<=cmd_layers;
    block_rows<=cmd_block_rows;row_base<=0;layer_id<=0;op<=0;state<=OFFER;cancelled<=0;end
   if(svc_valid&&svc_ready)state<=WAIT;
   if(svc_done_valid&&svc_done_ready)begin
    if(cancelled||cancel)begin state<=IDLE;cancelled<=0;end
    else if(op==2)state<=DONE;
    else if(row_base+nr<length)begin row_base<=row_base+nr;state<=OFFER;end
    else if(op==0)begin op<=1;row_base<=0;state<=OFFER;end
    else if(layer_id+1<layers)begin layer_id<=layer_id+1;row_base<=0;state<=OFFER;end
    else begin op<=2;row_base<=length-1;state<=OFFER;end
   end
   if(done_valid&&done_ready)state<=IDLE;
   if(cancel)begin if(state==WAIT)cancelled<=1;else begin state<=IDLE;cancelled<=0;end end
  end
 end
`ifndef SYNTHESIS
 always @(posedge clk)if(rst_n)begin
  if(cmd_valid&&cmd_ready)assert(cmd_length>0&&cmd_layers>0&&cmd_block_rows>0&&cmd_block_rows<=32&&{1'b0,cmd_past}+cmd_length<65536)else $fatal(1,"prompt shape");
  if(svc_valid)assert(svc_rows>0&&svc_row_base+svc_rows<=length)else $fatal(1,"prompt block range");
 end
`endif
endmodule
