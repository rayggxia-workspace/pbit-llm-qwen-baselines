module rej512_pref1(input wire clk,rst_n,start,output wire start_ready,busy,cfg_valid,input wire cfg_ready,
 input wire [8:0] reference_index,input wire [31:0] requested_samples,proposal_cap,
 input wire proposal_valid,output wire proposal_ready,input wire [511:0] proposal_bits,
 output wire fair_ready,input wire fair_valid,input wire [23:0] fair_bits_input,
 output wire [4:0] shift_m,output wire out_valid,input wire out_ready,output wire [8:0] out_index,output wire done,failed);
ac_rejection #(.N(512),.PREFETCH_FAIR(1)) dut(.clk(clk),.rst_n(rst_n),.start(start),.start_ready(start_ready),.busy(busy),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
 .reference_index(reference_index),.requested_samples(requested_samples),.proposal_cap(proposal_cap),.proposal_valid(proposal_valid),
 .proposal_ready(proposal_ready),.proposal_bits(proposal_bits),.fair_ready(fair_ready),.fair_valid(fair_valid),.fair_bits_input(fair_bits_input),
 .shift_m(shift_m),.out_valid(out_valid),.out_ready(out_ready),.out_index(out_index),.done(done),.failed(failed),
 .proposals(),.accepted(),.consumed(),.rejected_multi(),.rejected_empty(),.fair_words(),.fair_bits());
endmodule
