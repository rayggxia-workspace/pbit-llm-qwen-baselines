`timescale 1ns/1ps
// Uniform r8; q8/256. Pure unsigned 8-bit comparator (p=1 not representable).
module pbit_compare8_lt(input wire [7:0] r8, q8, output wire bit_o);
  assign bit_o = r8 < q8;
endmodule

// Existing random-service contract: q9=0..256, p=q9/256.
// Out-of-contract 257..511 saturate to 1 (never wrap to zero).
module pbit_compare8_q256(input wire [7:0] r8,
                        input wire [8:0] q9, output wire bit_o);
  wire lt;
  pbit_compare8_lt u_lt(.r8(r8),.q8(q9[7:0]),.bit_o(lt));
  assign bit_o = q9[8] | lt;
endmodule
