`timescale 1ns/1ps
// Synthetic activity patterns for PT characterization, NOT Qwen workload traces.
module tb_swiglu_power;
    parameter real HALF_PERIOD_NS = 5.0;
    reg clk = 0;
    always #(HALF_PERIOD_NS) clk = ~clk;
    reg rst = 1, ce = 1, in_valid = 0;
    reg signed [15:0] g_in = 0, u_in = 0;
    wire out_valid, saturated, inexact;
    wire signed [23:0] y_out;
    swiglu_epilogue_q10 dut (.*);
    reg [31:0] prng = 32'h13629da5;
    reg [8191:0] vcd_path;
    reg [127:0] mode;
    integer cycles = 10000;
    integer i, dummy;
    integer accepted = 0, produced = 0, expected;
    always @(posedge clk) begin
        if (rst) begin
            accepted = 0;
            produced = 0;
        end else begin
            if (ce && in_valid) accepted = accepted + 1;
            #1;
            if (ce && out_valid) produced = produced + 1;
        end
    end
    function automatic [31:0] xorshift;
        input [31:0] state;
        reg [31:0] s;
        begin
            s = state ^ (state << 13);
            s = s ^ (s >> 17);
            xorshift = s ^ (s << 5);
        end
    endfunction
    initial begin
        mode = "active";
        dummy = $value$plusargs("MODE=%s", mode);
        dummy = $value$plusargs("CYCLES=%d", cycles);
        if (cycles < 1) $fatal(1, "CYCLES must be positive");
        dummy = $value$plusargs("SEED=%d", prng);
        if (prng == 0) $fatal(1, "xorshift seed must be nonzero");
        if (mode != "active" && mode != "burst" && mode != "idle")
            $fatal(1, "MODE must be active, burst or idle");
        if (!$value$plusargs("VCD=%s", vcd_path))
            $fatal(1, "Pass +VCD=<absolute waveform path>");
        $dumpfile(vcd_path);
        $dumpvars(0, dut);
        repeat (3) @(negedge clk);
        rst = 0;
        for (i = 0; i < cycles; i = i + 1) begin
            // Deliberately toggle pins in idle intervals; DUT must isolate them.
            prng = xorshift(prng); g_in = prng[15:0];
            prng = xorshift(prng); u_in = prng[15:0];
            in_valid = (mode == "active") || ((mode == "burst") && ((i % 256) < 64));
            @(negedge clk);
        end
        in_valid = 0;
        repeat (8) @(negedge clk);
        expected = (mode == "active") ? cycles :
                   (mode == "idle") ? 0 :
                   (cycles / 256) * 64 + (((cycles % 256) < 64) ? (cycles % 256) : 64);
        if (accepted != expected || produced != expected)
            $fatal(1, "Valid count mismatch accepted=%0d produced=%0d expected=%0d",accepted,produced,expected);
        $display("PASS power activity mode=%0s cycles=%0d accepted=%0d produced=%0d half_period_ns=%0f", mode,cycles,accepted,produced,HALF_PERIOD_NS);
        $finish;
    end
endmodule
