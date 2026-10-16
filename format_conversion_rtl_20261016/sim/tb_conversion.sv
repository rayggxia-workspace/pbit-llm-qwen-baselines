`timescale 1ns/1ps
module tb_conversion;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,in_valid=0;
 reg [63:0] data=0;reg [31:0] aux=0;reg [23:0] coef=0;
 reg signed [15:0] ea=0,eb=0;
 wire [63:0] result[0:17],presult[0:17];
 wire [3:0] flags[0:17],pflags[0:17];wire pv[0:17];
 genvar k;
 generate for(k=0;k<18;k=k+1) begin:dut
  wire selected=(kind==k);
  wire [63:0] di=selected?data:64'b0;
  wire [31:0] ai=selected?aux:32'b0;
  wire [23:0] ci=selected?coef:24'b0;
  wire signed [15:0] eai=selected?ea:16'sb0,ebi=selected?eb:16'sb0;
  fc_comb_case #(.KIND(k)) u(di,ai,ci,eai,ebi,result[k],flags[k]);
  fc_conversion_probe #(.KIND(k)) p(clk,rst_n,in_valid&&selected,di,ai,ci,eai,ebi,pv[k],presult[k],pflags[k]);
 end endgenerate
 integer f,rc,kind,n=0;reg [63:0] expected;reg [3:0] expected_flags;
 initial begin
  f=$fopen("vectors/conversions.hex","r");if(!f)$fatal(1,"no conversion vectors");
  while(!$feof(f)) begin
   rc=$fscanf(f,"%h %h %h %h %h %h %h %h\n",kind,data,aux,coef,ea,eb,expected,expected_flags);
   if(rc==8) begin
    #1;
    if(result[kind]!==expected||flags[kind]!==expected_flags)
     $fatal(1,"conversion n=%0d kind=%0d data=%h ea=%0d eb=%0d coef=%h got=%h/%h exp=%h/%h",n,kind,data,ea,eb,coef,result[kind],flags[kind],expected,expected_flags);
    n=n+1;
   end
  end
  $fclose(f);$display("COMB_PASS %0d vectors",n);
  @(negedge clk);rst_n=1;
  f=$fopen("vectors/pipeline.hex","r");n=0;
  while(!$feof(f)) begin
   @(negedge clk);
   rc=$fscanf(f,"%h %h %h %h %h %h %h %h\n",kind,data,aux,coef,ea,eb,expected,expected_flags);
   if(rc==8) begin
    in_valid=1;@(negedge clk);in_valid=0;
    @(posedge clk);#1;
    if(!pv[kind]||presult[kind]!==expected||pflags[kind]!==expected_flags)
     $fatal(1,"pipeline kind=%0d",kind);
    @(posedge clk);#1;if(pv[kind])$fatal(1,"valid did not drain");n=n+1;
   end
  end
  $fclose(f);$display("PIPELINE_PASS %0d vectors",n);$finish;
 end
endmodule
