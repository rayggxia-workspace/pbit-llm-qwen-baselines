`timescale 1ns/1ps
module tb_exhaustive;
  reg [7:0] r=0, q8=0;
  reg [8:0] q9=0;
  reg signed [7:0] d=0;
  wire b8,b9; wire [8:0] lut;
  reg [8:0] golden[0:255];
  integer i,j,ones,checks=0;
  pbit_compare8_lt a(r,q8,b8);
  pbit_compare8_q256 b(r,q9,b9);
  pbit_sigmoid8_lut c(d,lut);
  initial begin
    $readmemh("golden.hex",golden);
    for(i=0;i<512;i=i+1) begin
      q9=i;q8=i;
      ones=0;
      for(j=0;j<256;j=j+1) begin
        r=j; #1;
        if(b8 !== (j<(i%256))) $fatal(1,"LT mismatch");
        if(b9 !== (j<i)) $fatal(1,"q256 mismatch");
        ones=ones+b9;checks=checks+1;
      end
      if(ones != ((i>256)?256:i)) $fatal(1,"Bernoulli count");
    end
    for(i=0;i<256;i=i+1) begin
      d=i; #1;
      if(lut !== golden[i]) $fatal(1,"LUT mismatch %d",i);
      q9=lut;ones=0;
      for(j=0;j<256;j=j+1) begin
        r=j;#1; ones=ones+b9;
      end
      if(ones != golden[i]) $fatal(1,"LUT probability mismatch");
    end
    $display("EXHAUSTIVE_PASS compare=%0d lut=256 integrated=65536",checks);
    $finish;
  end
endmodule
