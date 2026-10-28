`timescale 1ns/1ps
module tb_ffn_accumulator;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0,in_valid=0,out_ready=0,clear=0;
    reg signed [63:0] in_delta=0;
    wire in_ready,out_valid,out_overflow,out_sticky;
    wire signed [63:0] out_sum;
    ffn_accumulator dut(.clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(in_ready),
        .in_delta(in_delta),.clear(clear),.out_valid(out_valid),.out_ready(out_ready),
        .out_sum(out_sum),.out_overflow(out_overflow),.out_sticky(out_sticky));
    string trace_path;
    integer fd,rc,line_no=0;
    integer nr,nv,no,nc,expected_in_ready,expected_out_valid,expected_overflow,expected_sticky;
    reg [63:0] nd,expected_sum;
    initial begin
        if (!$value$plusargs("TRACE=%s",trace_path)) $fatal(1,"TRACE required");
        fd=$fopen(trace_path,"r");
        if (!fd) $fatal(1,"cannot open trace");
        while (!$feof(fd)) begin
            rc=$fscanf(fd,"%d %d %d %h %d %d %d %h %d %d\n",
                nr,nv,no,nd,nc,expected_in_ready,expected_out_valid,
                expected_sum,expected_overflow,expected_sticky);
            if (rc!=10) $fatal(1,"trace parse at line %0d fields=%0d",line_no,rc);
            @(negedge clk);
            rst_n=nr;in_valid=nv;out_ready=no;in_delta=nd;clear=nc;
            @(posedge clk);
            if (in_ready !== (expected_in_ready!=0) || out_valid !== (expected_out_valid!=0))
                $fatal(1,"handshake line=%0d",line_no);
            // State and status are specified even when no output is pending.
            if (out_sum !== expected_sum || out_overflow !== (expected_overflow!=0) ||
                out_sticky !== (expected_sticky!=0))
                $fatal(1,"state line=%0d got=%h/%b/%b expected=%h/%0d/%0d",
                       line_no,out_sum,out_overflow,out_sticky,expected_sum,expected_overflow,expected_sticky);
            line_no=line_no+1;
        end
        $fclose(fd);
        $display("PASS accumulator64 trace_cycles=%0d",line_no);
        $finish;
    end
endmodule
