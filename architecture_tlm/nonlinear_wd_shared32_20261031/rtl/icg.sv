`timescale 1ns/1ps
module ns_icg(input wire clk,enable,output wire gclk);
`ifdef SYNTHESIS
 CKGTX8_9TSVT technology_gate(.CK(clk),.E(enable),.TE(1'b0),.Q(gclk));
`else
 reg held_enable;
 always @(*)if(!clk)held_enable=enable;
 assign gclk=clk&held_enable;
`endif
endmodule
