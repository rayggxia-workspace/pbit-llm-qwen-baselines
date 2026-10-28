module win128_g16_p1_o0_e1_c10_s1(input wire clk,rst_n,start,output wire start_ready,busy,cfg_valid,input wire cfg_ready,
 input wire [127:0] candidate_mask,input wire [6:0] initial_index,
 input wire [10-1:0] requested_samples,burn_updates,
 input wire frame_valid,output wire frame_ready,input wire [127:0] frame_bits,
 input wire fair_valid,output wire fair_ready,input wire [6:0] fair_word,
 output wire out_valid,input wire out_ready,output wire [6:0] out_index,output wire done,failed);
ac_winner128 #(.N(128),.GROUP(16),.PREP_STAGES(1),.WINNER_ONEHOT(0),.EARLY_HOLD(1),.COUNT_W(10),.STREAM(1),.RANK_CAP(64)) dut(.clk(clk),.rst_n(rst_n),.start(start),.start_ready(start_ready),.busy(busy),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),.candidate_mask(candidate_mask),.initial_index(initial_index),.requested_samples(requested_samples),.burn_updates(burn_updates),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_bits(frame_bits),.fair_valid(fair_valid),.fair_ready(fair_ready),.fair_word(fair_word),.out_valid(out_valid),.out_ready(out_ready),.out_index(out_index),.done(done),.failed(failed),.issued(),.committed(),.consumed(),.holds(),.switches(),.fair_words(),.fair_bits(),.rank_retries(),.winner_index());
endmodule
