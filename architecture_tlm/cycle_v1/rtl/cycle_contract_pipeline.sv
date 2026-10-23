// Synthesizable protocol reference, not an FFN/Attention datapath or STA result.
// All handshakes use pre-edge ready/valid. No same-edge capacity bypass.
module cycle_contract_pipeline #(
    parameter integer LATENCY = 3,
    parameter integer II = 1,
    parameter integer CAPACITY = 4,
    parameter integer OUTPUT_II = 1,
    parameter integer ID_WIDTH = 16
) (
    input wire clk, input wire rst,
    input wire in_valid, output wire in_ready,
    input wire [ID_WIDTH-1:0] in_id,
    output wire out_valid, input wire out_ready,
    output wire [ID_WIDTH-1:0] out_id,
    output reg [31:0] cycle_count,
    output reg [31:0] used
);
    reg [ID_WIDTH-1:0] ids [0:CAPACITY-1];
    reg [31:0] remaining [0:CAPACITY-1];
    reg [31:0] input_cooldown, output_cooldown;
    integer head, tail, index;
    wire take_in = in_valid && in_ready;
    wire take_out = out_valid && out_ready;
    assign in_ready = (used < CAPACITY) && (input_cooldown == 0);
    assign out_valid = (used != 0) && (remaining[head] == 0) && (output_cooldown == 0);
    assign out_id = ids[head];
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            cycle_count <= 0; used <= 0; head <= 0; tail <= 0;
            input_cooldown <= 0; output_cooldown <= 0;
            for (index = 0; index < CAPACITY; index = index + 1) begin
                remaining[index] <= 0; ids[index] <= 0;
            end
        end else begin
            cycle_count <= cycle_count + 1;
            if (input_cooldown != 0) input_cooldown <= input_cooldown - 1;
            if (output_cooldown != 0) output_cooldown <= output_cooldown - 1;
            for (index = 0; index < CAPACITY; index = index + 1)
                if (remaining[index] != 0) remaining[index] <= remaining[index] - 1;
            case ({take_in, take_out})
                2'b10: used <= used + 1;
                2'b01: used <= used - 1;
                default: used <= used;
            endcase
            if (take_in) begin
                ids[tail] <= in_id;
                // The next edge sees LATENCY-1, so first completion is exactly
                // LATENCY edges after acceptance (never on acceptance itself).
                remaining[tail] <= LATENCY - 1;
                tail <= (tail == CAPACITY - 1) ? 0 : tail + 1;
                input_cooldown <= II - 1;
            end
            if (take_out) begin
                head <= (head == CAPACITY - 1) ? 0 : head + 1;
                output_cooldown <= OUTPUT_II - 1;
            end
        end
    end
endmodule


module cycle_contract_fifo #(
    parameter integer CAPACITY = 3,
    parameter integer INITIAL_FILL = 0,
    parameter integer ID_WIDTH = 16
) (
    input wire clk, input wire rst,
    input wire in_valid, output wire in_ready,
    input wire [ID_WIDTH-1:0] in_id,
    output wire out_valid, input wire out_ready,
    output wire [ID_WIDTH-1:0] out_id,
    output reg [31:0] used
);
    reg [ID_WIDTH-1:0] ids [0:CAPACITY-1];
    integer head, tail, index;
    wire take_in = in_valid && in_ready;
    wire take_out = out_valid && out_ready;
    assign in_ready = used < CAPACITY;
    assign out_valid = used != 0;
    assign out_id = ids[head];
    always @(posedge clk or posedge rst) begin
        if (rst) begin
            used <= INITIAL_FILL; head <= 0;
            tail <= (INITIAL_FILL == CAPACITY) ? 0 : INITIAL_FILL;
            for (index = 0; index < CAPACITY; index = index + 1) ids[index] <= {ID_WIDTH{1'b1}};
        end else begin
            case ({take_in, take_out})
                2'b10: used <= used + 1;
                2'b01: used <= used - 1;
                default: used <= used;
            endcase
            if (take_in) begin
                ids[tail] <= in_id;
                tail <= (tail == CAPACITY - 1) ? 0 : tail + 1;
            end
            if (take_out) head <= (head == CAPACITY - 1) ? 0 : head + 1;
        end
    end
endmodule
