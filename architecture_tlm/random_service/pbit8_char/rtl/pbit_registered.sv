// One sampled transaction per enabled edge, no output backpressure.
// En=0 holds DATA, clears valid; en is a register CE, not a physical clock gate.
module pbit_sigmoid8_reg(input wire clk, rst_n, en,
                        input wire signed [7:0] drive8,
                        output reg [8:0] q9, output reg valid);
  wire [8:0] q;
  pbit_sigmoid8_lut u_lut(.drive8(drive8),.q9(q));
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin q9<=0; valid<=0; end
    else begin valid<=en; if(en) q9<=q; end
endmodule

// Characterization of LUT+comparator+output register. No PRNG, input conversion,
// Ising field MAC, probability cache, or CDC is included.
module pbit_sample8_reg(input wire clk, rst_n, en,
                       input wire signed [7:0] drive8,
                       input wire [7:0] r8,
                       output reg bit_o, output reg valid);
  wire [8:0] q;
  wire sample;
  pbit_sigmoid8_lut u_lut(.drive8(drive8),.q9(q));
  pbit_compare8_q256 u_compare(.r8(r8),.q9(q),.bit_o(sample));
  always @(posedge clk or negedge rst_n)
    if (!rst_n) begin bit_o<=0; valid<=0; end
    else begin valid<=en; if(en) bit_o<=sample; end
endmodule
