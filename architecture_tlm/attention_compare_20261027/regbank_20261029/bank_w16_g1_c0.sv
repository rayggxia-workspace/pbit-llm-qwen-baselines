module bank_w16_g1_c0(input wire clk,wr_en,input wire[2:0] wr_group,input wire[255:0] wr_data,input wire[2047:0] random_words,output wire[2047:0] result);
threshold_bank #(.W(16),.GATED(1),.COMPARE(0)) u(clk,wr_en,wr_group,wr_data,random_words,result);
endmodule
