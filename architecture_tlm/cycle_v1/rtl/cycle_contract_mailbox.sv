// One-entry bundled-data mailbox with two-flop request and acknowledge sync.
// Source holds payload until destination completion acknowledges it. This
// digital protocol reference does not analyze metastability or CDC placement.
module cycle_contract_mailbox #(
    parameter integer ID_WIDTH = 16
) (
    input wire src_clk, input wire dst_clk, input wire rst,
    input wire src_valid, output wire src_ready,
    input wire [ID_WIDTH-1:0] src_id,
    output wire dst_valid, input wire dst_complete,
    output wire [ID_WIDTH-1:0] dst_id
);
    reg request, acknowledge;
    reg request_sync1, request_sync2;
    reg ack_sync1, ack_sync2;
    reg [ID_WIDTH-1:0] held_id;
    assign src_ready = request == ack_sync2;
    assign dst_valid = request_sync2 != acknowledge;
    assign dst_id = held_id;
    always @(posedge src_clk or posedge rst) begin
        if (rst) begin
            request <= 0; ack_sync1 <= 0; ack_sync2 <= 0; held_id <= 0;
        end else begin
            ack_sync1 <= acknowledge;
            ack_sync2 <= ack_sync1;
            if (src_valid && src_ready) begin
                request <= ~request;
                held_id <= src_id;
            end
        end
    end
    always @(posedge dst_clk or posedge rst) begin
        if (rst) begin
            request_sync1 <= 0; request_sync2 <= 0; acknowledge <= 0;
        end else begin
            request_sync1 <= request;
            request_sync2 <= request_sync1;
            if (dst_valid && dst_complete) acknowledge <= request_sync2;
        end
    end
endmodule
