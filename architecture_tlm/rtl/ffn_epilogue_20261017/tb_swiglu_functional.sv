`timescale 1ns/1ps
module tb_swiglu_functional;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst = 1, ce = 0, in_valid = 0;
    reg signed [15:0] g_in = 0, u_in = 0;
    wire valid24, valid16, sat24, sat16, inex24, inex16;
    wire signed [23:0] y24;
    wire signed [15:0] y16;
    swiglu_epilogue_q10 #(.OUT_W(24)) dut24 (
        .clk(clk), .rst(rst), .ce(ce), .in_valid(in_valid), .g_in(g_in), .u_in(u_in),
        .out_valid(valid24), .y_out(y24), .saturated(sat24), .inexact(inex24));
    swiglu_epilogue_q10 #(.OUT_W(16)) dut16 (
        .clk(clk), .rst(rst), .ce(ce), .in_valid(in_valid), .g_in(g_in), .u_in(u_in),
        .out_valid(valid16), .y_out(y16), .saturated(sat16), .inexact(inex16));
    reg [8191:0] vectors_path;
    integer fd, count, rc;
    integer r, c, v, g, u, ev, ey24, es24, ei24, ey16, es16, ei16;
    reg [15:0] old_g, old_u;
    reg [31:0] old_gu;
    reg [16:0] old_sigma;
    reg [49:0] old_product;
    reg [2:0] old_valid;
    initial begin
        if (!$value$plusargs("VECTORS=%s", vectors_path))
            $fatal(1, "Pass +VECTORS=<absolute cycle_vectors.txt>");
        fd = $fopen(vectors_path, "r");
        if (!fd) $fatal(1, "Cannot read vectors");
        count = 0;
        while (!$feof(fd)) begin
            rc = $fscanf(fd, "%d %d %d %d %d %d %d %d %d %d %d %d\n",
                         r, c, v, g, u, ev, ey24, es24, ei24, ey16, es16, ei16);
            if (rc != 12) $fatal(1, "Malformed row %0d, rc=%0d", count, rc);
            @(negedge clk);
            rst = r; ce = c; in_valid = v; g_in = g; u_in = u;
            old_g = dut24.g_q; old_u = dut24.u_q;
            old_gu = dut24.gu_q; old_sigma = dut24.sigma_q;
            old_product = dut24.product_q;
            old_valid = {dut24.v2, dut24.v1, dut24.v0};
            @(posedge clk); #1;
            if (valid24 !== (ev != 0) || valid16 !== (ev != 0) ||
                $signed(y24) !== ey24 || sat24 !== (es24 != 0) || inex24 !== (ei24 != 0) ||
                $signed(y16) !== ey16 || sat16 !== (es16 != 0) || inex16 !== (ei16 != 0)) begin
                $display("row=%0d g=%0d u=%0d ce=%0d rst=%0d valid=%0d expected=%0d", count,g,u,c,r,valid24,ev);
                $display("24 got=%0d/%0d/%0d expected=%0d/%0d/%0d", y24,sat24,inex24,ey24,es24,ei24);
                $display("16 got=%0d/%0d/%0d expected=%0d/%0d/%0d", y16,sat16,inex16,ey16,es16,ei16);
                $fatal(1, "Golden mismatch");
            end
            if (!r) begin
                if ((!c || !v) && {dut24.g_q,dut24.u_q} !== {old_g,old_u})
                    $fatal(1, "Input isolation/CE failure");
                if ((!c || !old_valid[0]) && {dut24.gu_q,dut24.sigma_q} !== {old_gu,old_sigma})
                    $fatal(1, "Product/sigmoid valid gating failure");
                if ((!c || !old_valid[1]) && dut24.product_q !== old_product)
                    $fatal(1, "Wide product valid gating failure");
                if (!c && {dut24.v2,dut24.v1,dut24.v0} !== old_valid)
                    $fatal(1, "CE did not freeze valid state");
            end
            count = count + 1;
        end
        $fclose(fd);
        $display("PASS functional cycles=%0d OUT_W=24,16", count);
        $finish;
    end
endmodule
