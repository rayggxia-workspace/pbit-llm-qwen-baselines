module smx_sys_l16(input wire clk,rst_n,start,load_valid,out_ready,seed_valid,
 input wire [511:0] score_in,input wire [31:0] seed_data,
 output wire start_ready,load_ready,seed_ready,front_done,out_valid,done,invalid,clipped,
 output wire [6:0] out_index,output wire [143:0] out_count);
 digital_sampler #(.L(16),.MODE(1)) core(.*);
endmodule
