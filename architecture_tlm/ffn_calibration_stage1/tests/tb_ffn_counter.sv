`timescale 1ns/1ps
// File-driven checker. Arithmetic goldens are generated independently in Python.
module tb_ffn_counter;
    parameter integer N = 64;
    parameter integer M = 1;
    parameter integer BINS = 4;
    parameter integer T = 64;
    parameter integer CW = 1 + $clog2(N*127*T+1);
    localparam integer LEVELS = $clog2(N);
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n, frame_valid, sample_valid, out_ready;
    reg [N*M*7-1:0] w_mag7;
    reg [N*M-1:0] w_sign;
    reg [N-1:0] x_sign, sample_bits;
    reg [N*3-1:0] bin_id;
    wire frame_ready, sample_ready, out_valid;
    wire [M*BINS*CW-1:0] out_counts;
    ffn_counter #(.N(N), .M(M), .BINS(BINS), .T(T), .CW(CW)) dut (.*);

    reg next_rst, next_frame, next_sample, next_out_ready;
    reg [N*M*7-1:0] next_w_mag7;
    reg [N*M-1:0] next_w_sign;
    reg [N-1:0] next_x_sign, next_sample_bits;
    reg [N*3-1:0] next_bin_id;
    reg [2:0] expected_flags;
    reg [M*BINS*CW-1:0] expected_counts;
    reg [M*BINS*CW-1:0] held_counts;
    reg was_out, stall_at_edge, frame_active;
    integer stream, fields, cycle, frames_started, frames_completed;
    integer samples_accepted, output_stall_cycles, reset_aborts;
    integer frame_samples, last_sample_cycle;
    reg [4095:0] vectors_path;

    initial begin
        rst_n = 0; frame_valid = 0; sample_valid = 0; out_ready = 0;
        w_mag7 = 0; w_sign = 0; x_sign = 0; bin_id = 0; sample_bits = 0;
        cycle = 0; frames_started = 0; frames_completed = 0;
        samples_accepted = 0; output_stall_cycles = 0; reset_aborts = 0;
        frame_samples = 0; frame_active = 0; last_sample_cycle = -1;
        if (!$value$plusargs("VECTORS=%s", vectors_path))
            $fatal(1, "missing +VECTORS=<path>");
        stream = $fopen(vectors_path, "r");
        if (!stream) $fatal(1, "cannot open vectors");
        while (!$feof(stream)) begin
            fields = $fscanf(stream, "%h %h %h %h %h %h %h %h %h %h %h\n",
                next_rst, next_frame, next_sample, next_out_ready,
                next_w_mag7, next_w_sign, next_x_sign, next_bin_id,
                next_sample_bits, expected_flags, expected_counts);
            if (fields != 11) $fatal(1, "bad vector row after cycle %0d: %0d fields", cycle, fields);
            @(negedge clk);
            rst_n = next_rst; frame_valid = next_frame;
            sample_valid = next_sample; out_ready = next_out_ready;
            w_mag7 = next_w_mag7; w_sign = next_w_sign; x_sign = next_x_sign;
            bin_id = next_bin_id; sample_bits = next_sample_bits;
            @(posedge clk);
            cycle = cycle + 1;
            was_out = out_valid;
            held_counts = out_counts;
            stall_at_edge = rst_n && out_valid && !out_ready;
            if (!rst_n) begin
                if (frame_active) reset_aborts = reset_aborts + 1;
                frame_active = 0;
                frame_samples = 0;
            end else begin
                if (frame_valid && frame_ready) begin
                    if (frame_active) $fatal(1, "overlapping frame at cycle %0d", cycle);
                    if (sample_ready) $fatal(1, "sample ready on frame-start edge");
                    frames_started = frames_started + 1;
                    frame_samples = 0;
                    frame_active = 1;
                end
                if (sample_valid && sample_ready) begin
                    if (!frame_active || frame_samples >= T)
                        $fatal(1, "unexpected sample acceptance at cycle %0d", cycle);
                    samples_accepted = samples_accepted + 1;
                    frame_samples = frame_samples + 1;
                    last_sample_cycle = cycle;
                end
                if (out_valid && out_ready) begin
                    if (!frame_active) $fatal(1, "output without an active frame");
                    frames_completed = frames_completed + 1;
                    frame_active = 0;
                end
                if (stall_at_edge) output_stall_cycles = output_stall_cycles + 1;
            end
            #1;
            if ({frame_ready, sample_ready, out_valid} !== expected_flags)
                $fatal(1, "flags cycle=%0d actual=%b expected=%b", cycle,
                    {frame_ready, sample_ready, out_valid}, expected_flags);
            if (out_valid && out_counts !== expected_counts)
                $fatal(1, "counts cycle=%0d actual=%h expected=%h", cycle, out_counts, expected_counts);
            if (stall_at_edge && (!out_valid || out_counts !== held_counts))
                $fatal(1, "output changed under backpressure at cycle %0d", cycle);
            if (rst_n && out_valid && !was_out) begin
                if (frame_samples != T || cycle-last_sample_cycle != LEVELS)
                    $fatal(1, "latency/count mismatch cycle=%0d last=%0d samples=%0d", cycle, last_sample_cycle, frame_samples);
            end
        end
        $fclose(stream);
        if (frame_active) $fatal(1, "unfinished frame at EOF");
        $display("COUNTER_PASS cycles=%0d frames_started=%0d frames_completed=%0d samples_accepted=%0d output_stall_cycles=%0d reset_aborts=%0d",
            cycle, frames_started, frames_completed, samples_accepted, output_stall_cycles, reset_aborts);
        $finish;
    end
    initial begin
        #10000000;
        $fatal(1, "watchdog timeout");
    end
endmodule
