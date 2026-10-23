// Functional fallback is a wire. PPA MUST define CIM_TECH_BUFFER and bind a
// real non-inverting library cell; see flow/generate_buffer_binding.tcl.
module cim_buffer(input wire a, output wire y);
`ifdef CIM_TECH_BUFFER
  cim_technology_buffer impl(.a(a),.y(y));
`else
  buf (y,a);
`endif
endmodule

// One root and COPIES leaves per input bit. Real buffers remain observable
// under synthesis; downstream fanout/load must be present in the PPA boundary.
module cim_fanout #(parameter integer WIDTH=64,COPIES=8)(
 input wire [WIDTH-1:0] din, output wire [WIDTH*COPIES-1:0] dout);
 wire [WIDTH-1:0] root;
 genvar i,j;
 generate for(i=0;i<WIDTH;i=i+1) begin: bit_lane
  cim_buffer root_buffer(.a(din[i]),.y(root[i]));
  for(j=0;j<COPIES;j=j+1) begin: branch
   cim_buffer leaf_buffer(.a(root[i]),.y(dout[j*WIDTH+i]));
  end
 end endgenerate
endmodule
