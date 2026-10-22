`timescale 1ps/1ps
module tb_cycle_contract;
    parameter integer LATENCY = 3;
    parameter integer II = 1;
    parameter integer CAPACITY = 4;
    parameter integer OUTPUT_II = 2;
    parameter integer N = 8;
    parameter integer FIFO_CAPACITY = 3;
    parameter integer INITIAL_FILL = 3;
    parameter integer DRAIN_START = 12;
    parameter integer DRAIN_II = 2;
    reg clk = 0, rst = 0;
    integer sent = 0, consumed = 0;
    wire [31:0] cycle, pipe_used, fifo_used;
    wire pipe_in_ready, pipe_out_valid, pipe_out_ready;
    wire [15:0] pipe_out_id, fifo_out_id;
    wire fifo_out_valid;
    wire sink_ready = (cycle >= DRAIN_START) && ((cycle - DRAIN_START) % DRAIN_II == 0);
    initial begin #1 rst = 1; #49 rst = 0; end
    initial begin #100; forever begin clk = 1; #5000 clk = 0; #5000; end end
    cycle_contract_pipeline #(.LATENCY(LATENCY), .II(II), .CAPACITY(CAPACITY), .OUTPUT_II(OUTPUT_II)) p (
        .clk(clk), .rst(rst), .in_valid(sent < N), .in_ready(pipe_in_ready), .in_id(sent[15:0]),
        .out_valid(pipe_out_valid), .out_ready(pipe_out_ready), .out_id(pipe_out_id),
        .cycle_count(cycle), .used(pipe_used));
    cycle_contract_fifo #(.CAPACITY(FIFO_CAPACITY), .INITIAL_FILL(INITIAL_FILL)) q (
        .clk(clk), .rst(rst), .in_valid(pipe_out_valid), .in_ready(pipe_out_ready), .in_id(pipe_out_id),
        .out_valid(fifo_out_valid), .out_ready(sink_ready), .out_id(fifo_out_id), .used(fifo_used));
    always @(posedge clk) if (!rst) begin
        $display("STATE %0d %0d %0d", cycle * 10000, pipe_used, fifo_used);
        if ((sent < N) && pipe_in_ready) begin
            $display("P_ACCEPT %0d %0d", cycle * 10000, sent);
            sent <= sent + 1;
        end
        if (pipe_out_valid && pipe_out_ready)
            $display("P_COMPLETE %0d %0d", cycle * 10000, pipe_out_id);
        if (fifo_out_valid && sink_ready) begin
            $display("Q_CONSUME %0d %0d", cycle * 10000, fifo_out_id);
            consumed <= consumed + 1;
            if (consumed + 1 == N + INITIAL_FILL) begin
                #1 $display("PASS pipeline"); $finish;
            end
        end
        if (pipe_used > CAPACITY || fifo_used > FIFO_CAPACITY) $fatal(1, "capacity overflow");
    end
    initial begin #10000000; $fatal(1, "watchdog"); end
endmodule
