module bank_w11_g1_c0(input wire clk,wr_en,input wire[2:0] wr_group,input wire[175:0] wr_data,input wire[1407:0] random_words,output wire[1407:0] result);
threshold_bank #(.W(11),.GATED(1),.COMPARE(0)) u(clk,wr_en,wr_group,wr_data,random_words,result);
endmodule
