`timescale 1ns/1ps
// GATE_MODE 0: ungated baseline; 1: portable FUNCTIONAL model only;
// 2: user-bound library ICG. Reset/wake are included by the caller in en.
module pbit_icg #(parameter integer GATE_MODE=0)(
 input wire clk, input wire en, input wire test_en, output wire gclk
);
 generate
  if (GATE_MODE==0) begin:g_off
   assign gclk=clk;
  end else if (GATE_MODE==1) begin:g_model
`ifdef SYNTHESIS
   ERROR_FUNCTIONAL_ICG_IS_NOT_A_TECHNOLOGY_CELL must_bind_real_icg();
`else
   reg enable_latched;
   always @* if (!clk) enable_latched <= en | test_en;
   assign gclk=clk & enable_latched;
`endif
  end else if (GATE_MODE==2) begin:g_library
`ifdef PB_ICG_TECH_MAPPED
   pbit_icg_tech cell_wrapper(.clk(clk),.en(en),.test_en(test_en),.gclk(gclk));
`else
   ERROR_REAL_ICG_MAPPING_REQUIRED missing_technology_mapping();
`endif
  end else begin:g_bad
   ERROR_INVALID_ICG_MODE invalid_parameter();
  end
 endgenerate
endmodule
