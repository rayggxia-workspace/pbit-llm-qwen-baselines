// 128 independent logical 128x1 banks, realized with 64x2 SRAM macros.
// Bit address maps to {physical word address[5:0], selected bit[0]}.
// Read select is registered alongside the synchronous SRAM request.
module banks(input wire clk, input wire write_en,
             input wire [895:0] bit_addr, input wire [255:0] write_data,
             output wire [127:0] sample);
  genvar b;
  generate for (b=0;b<128;b=b+1) begin: bank
    wire [1:0] q;
    reg select_bit;
    always @(posedge clk) select_bit <= bit_addr[b*7];
    SB_D64_W2 mem(.CLK(clk), .CEB(1'b0), .GWEB(!write_en),
      .WEB(2'b00), .MARE(1'b0), .MAR(4'b0),
      .A(bit_addr[b*7+1 +: 6]), .D(write_data[b*2 +: 2]), .Q(q));
    assign sample[b]=q[select_bit];
  end endgenerate
endmodule
