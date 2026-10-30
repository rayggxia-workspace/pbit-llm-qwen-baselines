module screen_top16 #(parameter L=16)(input clk,rst_n,start,in_valid,input [11:0] n_items,input [7:0] keep_k,input [5:0] first_shift,input [32*L-1:0] scores,output req_valid,output [11:0] req_base,output out_valid,output [11:0] out_base,output [L-1:0] out_mask,output [12*L-1:0] packed_indices,output [4:0] out_count,output done);
 radix_select #(.L(L)) impl(.*);
endmodule
