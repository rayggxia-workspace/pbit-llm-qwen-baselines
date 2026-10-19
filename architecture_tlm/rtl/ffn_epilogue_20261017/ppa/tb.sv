`timescale 1ns/1ps
module tb_epilogue_power;
    reg clk=0, rst=1, ce=1, in_valid=0;
    reg signed [15:0] g_in=0, u_in=0;
    wire out_valid, saturated, inexact;
    wire signed [23:0] y_out;
    swiglu_epilogue_q10 dut(.*);
    always #5 clk=~clk;
    integer fd, rc, row, rows, warmup, expected_count, count;
    integer vi, g, u, ev, ey, es, ei;
    reg [2047:0] vectors, wave;
    initial begin
        if (!$value$plusargs("VECTORS=%s", vectors) ||
            !$value$plusargs("WAVE=%s", wave) ||
            !$value$plusargs("ROWS=%d", rows) ||
            !$value$plusargs("WARMUP=%d", warmup) ||
            !$value$plusargs("EXPECTED=%d", expected_count))
            $fatal(1,"Missing arguments");
        $dumpfile(wave);
        $dumpvars(0,dut);
        fd=$fopen(vectors,"r");
        if (!fd) $fatal(1,"Cannot read vectors");
        repeat(4) @(negedge clk);
        rst=0; count=0;
        for (row=0;row<rows;row=row+1) begin
            rc=$fscanf(fd,"%d %d %d %d %d %d %d\n",vi,g,u,ev,ey,es,ei);
            if (rc!=7) $fatal(1,"Truncated vectors row=%0d",row);
            in_valid=vi; g_in=g; u_in=u;
            @(negedge clk);
            if (out_valid !== ev[0] || y_out !== ey[23:0] ||
                saturated !== es[0] || inexact !== ei[0])
                $fatal(1,"Mismatch/X row=%0d got=%b,%h,%b,%b expected=%d,%h,%d,%d",
                       row,out_valid,y_out,saturated,inexact,ev,ey[23:0],es,ei);
            if (row>=warmup && out_valid) count=count+1;
        end
        if (count!=expected_count) $fatal(1,"Count mismatch %0d != %0d",count,expected_count);
        $fclose(fd);
        #1;
        $display("EPILOGUE_PASS rows=%0d outputs=%0d",rows,count);
        $finish;
    end
    initial begin #10000000; $fatal(1,"Timeout"); end
endmodule
