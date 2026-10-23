`timescale 1ps/1ps
module tb_cycle_cdc;
    parameter integer DST_PHASE = 0;
    parameter integer N = 5;
    parameter integer SRC_LATENCY = 2;
    parameter integer DST_LATENCY = 2;
    reg src_clk = 0, dst_clk = 0, rst = 0;
    reg src_busy = 0, dst_busy = 0;
    integer sent = 0, received = 0;
    wire src_in_ready, src_out_valid, src_out_ready;
    wire [15:0] src_out_id;
    wire [31:0] src_cycle, src_used;
    wire mb_src_ready, mb_dst_valid;
    wire [15:0] mb_dst_id;
    wire dst_in_ready, dst_out_valid;
    wire [15:0] dst_out_id;
    wire [31:0] dst_cycle, dst_used;
    wire source_valid = (sent < N) && mb_src_ready && !src_busy;
    wire destination_valid = mb_dst_valid && !dst_busy;
    initial begin #1 rst = 1; #49 rst = 0; end
    initial begin #100; forever begin src_clk = 1; #5000 src_clk = 0; #5000; end end
    initial begin #(100 + DST_PHASE); forever begin dst_clk = 1; #6250 dst_clk = 0; #6250; end end
    cycle_contract_pipeline #(.LATENCY(SRC_LATENCY), .CAPACITY(1)) src (
        .clk(src_clk), .rst(rst), .in_valid(source_valid), .in_ready(src_in_ready), .in_id(sent[15:0]),
        .out_valid(src_out_valid), .out_ready(src_out_ready), .out_id(src_out_id),
        .cycle_count(src_cycle), .used(src_used));
    assign src_out_ready = mb_src_ready;
    cycle_contract_mailbox mb (
        .src_clk(src_clk), .dst_clk(dst_clk), .rst(rst), .src_valid(src_out_valid),
        .src_ready(mb_src_ready), .src_id(src_out_id), .dst_valid(mb_dst_valid),
        .dst_complete(dst_out_valid), .dst_id(mb_dst_id));
    cycle_contract_pipeline #(.LATENCY(DST_LATENCY), .CAPACITY(1)) dst (
        .clk(dst_clk), .rst(rst), .in_valid(destination_valid), .in_ready(dst_in_ready), .in_id(mb_dst_id),
        .out_valid(dst_out_valid), .out_ready(1'b1), .out_id(dst_out_id),
        .cycle_count(dst_cycle), .used(dst_used));
    always @(posedge src_clk or posedge rst) begin
        if (rst) begin sent <= 0; src_busy <= 0; end
        else begin
            if (source_valid && src_in_ready) begin
                $display("S_ACCEPT %0d %0d", $time - 100, sent);
                sent <= sent + 1; src_busy <= 1;
            end
            if (src_out_valid && src_out_ready) begin
                $display("S_COMPLETE %0d %0d", $time - 100, src_out_id);
                src_busy <= 0;
            end
        end
    end
    always @(posedge dst_clk or posedge rst) begin
        if (rst) begin received <= 0; dst_busy <= 0; end
        else begin
            if (destination_valid && dst_in_ready) begin
                $display("D_ACCEPT %0d %0d", $time - 100, mb_dst_id);
                dst_busy <= 1;
            end
            if (dst_out_valid) begin
                $display("D_COMPLETE %0d %0d", $time - 100, dst_out_id);
                received <= received + 1; dst_busy <= 0;
                if (received + 1 == N) begin
                    #1 $display("PASS cdc"); $finish;
                end
            end
            if (dst_used > 1) $fatal(1, "mailbox consumer overflow");
        end
    end
    initial begin #10000000; $fatal(1, "watchdog"); end
endmodule
