`timescale 1ns/1ps
`ifndef TEST_BINS
`define TEST_BINS 4
`endif
`ifndef TEST_CW
`define TEST_CW 20
`endif
module tb_ffn_restore;
    localparam integer BINS=`TEST_BINS, CW=`TEST_CW;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0,in_valid=0,out_ready=0;
    reg [BINS*CW-1:0] counts=0;
    reg [15:0] coeff=0;
    reg [5:0] rshift=0;
    wire in_ready,out_valid;
    wire signed [63:0] out_delta;
    ffn_restore #(.BINS(BINS),.CW(CW)) dut(
        .clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(in_ready),
        .counts(counts),.coeff(coeff),.rshift(rshift),
        .out_valid(out_valid),.out_ready(out_ready),.out_delta(out_delta));
    string trace_path;
    integer fd,rc,line_no=0;
    integer nr,nv,no,expected_in_ready,expected_out_valid;
    reg [BINS*CW-1:0] nc;
    reg [15:0] nk;
    reg [5:0] ns;
    reg [63:0] expected_delta;
    initial begin
        if (!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"TRACE required");
        fd=$fopen(trace_path,"r");
        if (!fd) $fatal(1,"cannot open trace");
        while (!$feof(fd)) begin
            rc=$fscanf(fd,"%d %d %d %h %h %h %d %d %h\n",
                nr,nv,no,nc,nk,ns,expected_in_ready,expected_out_valid,expected_delta);
            if (rc!=9) $fatal(1,"trace parse at line %0d, fields=%0d",line_no,rc);
            @(negedge clk);
            rst_n=nr;in_valid=nv;out_ready=no;counts=nc;coeff=nk;rshift=ns;
            @(posedge clk);
            // Compare before NBA updates: this is the accepting clock edge.
            if (in_ready !== (expected_in_ready!=0) || out_valid !== (expected_out_valid!=0))
                $fatal(1,"handshake line=%0d got ready/valid=%b/%b expected=%0d/%0d",
                       line_no,in_ready,out_valid,expected_in_ready,expected_out_valid);
            if (out_valid && out_delta !== expected_delta)
                $fatal(1,"value line=%0d got=%h expected=%h",line_no,out_delta,expected_delta);
            line_no=line_no+1;
        end
        $fclose(fd);
        $display("PASS restore BINS=%0d CW=%0d trace_cycles=%0d",BINS,CW,line_no);
        $finish;
    end
endmodule
