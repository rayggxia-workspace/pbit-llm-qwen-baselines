module screen_norm4 #(parameter L=4)(input clk,rst_n,start,in_valid,first_head,input [11:0] n_items,input [11*L-1:0] scores,input [19*L-1:0] group_previous,output req_valid,output [11:0] req_base,output [1:0] req_phase,output out_valid,output [11:0] out_base,output [19*L-1:0] group_result,output done);
 screen_norm #(.L(L)) impl(.*);
endmodule
