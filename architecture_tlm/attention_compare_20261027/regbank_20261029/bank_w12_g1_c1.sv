module bank_w12_g1_c1(input wire clk,wr_en,input wire[2:0] wr_group,input wire[191:0] wr_data,input wire[1535:0] random_words,output wire[127:0] result);
threshold_bank #(.W(12),.GATED(1),.COMPARE(1)) u(clk,wr_en,wr_group,wr_data,random_words,result);
endmodule
