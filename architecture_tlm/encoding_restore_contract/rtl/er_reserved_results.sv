`timescale 1ns/1ps
// One reserved slot per accepted operation, including unfinished operations.
// Results must arrive in acceptance order, at most one per edge, after accept.
// No fall-through: a completed result is visible after the registering edge.
module er_reserved_results #(
 parameter integer DATA_W=32, DEPTH=3,
 parameter integer CW=(DEPTH<2?1:$clog2(DEPTH+1)),
 parameter integer PW=(DEPTH<2?1:$clog2(DEPTH))
)(
 input wire clk,rst_n,in_valid,
 output wire in_ready,
 input wire result_valid,
 input wire [DATA_W-1:0] result_data,
 output wire out_valid,
 input wire out_ready,
 output wire [DATA_W-1:0] out_data,
 output reg [CW-1:0] reserved_count,queued_count
);
 reg [DATA_W-1:0] storage[0:DEPTH-1];
 reg [PW-1:0] read_ptr,write_ptr;
 wire pop=out_valid&&out_ready;
 wire accept=in_valid&&in_ready;
 assign out_valid=rst_n&&(queued_count!=0);
 assign out_data=out_valid?storage[read_ptr]:{DATA_W{1'b0}};
 // A real output handshake may release one slot on this same edge.
 assign in_ready=rst_n&&((reserved_count<DEPTH)||pop);
 always @(posedge clk)begin
  if(!rst_n)begin
   reserved_count<=0;queued_count<=0;read_ptr<=0;write_ptr<=0;
  end else begin
   case({accept,pop})
    2'b10:reserved_count<=reserved_count+1'b1;
    2'b01:reserved_count<=reserved_count-1'b1;
    default:reserved_count<=reserved_count;
   endcase
   case({result_valid,pop})
    2'b10:queued_count<=queued_count+1'b1;
    2'b01:queued_count<=queued_count-1'b1;
    default:queued_count<=queued_count;
   endcase
   if(result_valid)begin
    storage[write_ptr]<=result_data;
    write_ptr<=(write_ptr==DEPTH-1)?0:write_ptr+1'b1;
   end
   if(pop)read_ptr<=(read_ptr==DEPTH-1)?0:read_ptr+1'b1;
  end
 end
`ifndef SYNTHESIS
 initial if(DEPTH<1||DATA_W<1)$fatal(1,"invalid reserved-results geometry");
 always @(posedge clk)if(rst_n)begin
  if(reserved_count>DEPTH||queued_count>reserved_count)
   $fatal(1,"result slot accounting overflow");
  if(result_valid&&reserved_count==queued_count)
   $fatal(1,"completion without an outstanding reserved operation");
 end
`endif
endmodule
