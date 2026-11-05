`timescale 1ns/1ps
// Exact fixed-W8 stochastic event reduction. No RNG, comparator or weight SRAM.
// Each lane has ONE bin. Align its signed weight before the shared tree.
// No intermediate rounding/saturation: out_sum equals old bucket restore input.
// Weights/sign/bin remain stable from frame handshake through output handshake.
// W is 7-bit magnitude + sign, hence [-127,127], not two's-complement -128.
module sc_counter_merged #(
    parameter integer N=64,
    parameter integer M=1,
    parameter integer BINS=4,
    parameter integer T=64,
    parameter integer PIPE_EVERY=1,
    parameter integer GATE_MODE=0,
    parameter integer AW=1+$clog2(N*127*T+1)+2*(BINS-1)
)(
    input wire clk, rst_n, test_en,
    input wire frame_valid,
    output wire frame_ready,
    input wire [N*M*7-1:0] w_mag7,
    input wire [N*M-1:0] w_sign,
    input wire [N-1:0] x_sign,
    input wire [N*3-1:0] bin_id,
    input wire [N-1:0] sample_bits,
    input wire sample_valid,
    output wire sample_ready,
    output wire out_valid,
    input wire out_ready,
    output wire [M*AW-1:0] out_sum
);
    localparam integer LEVELS=$clog2(N);
    localparam integer STAGES=(LEVELS+PIPE_EVERY-1)/PIPE_EVERY;
    localparam integer LW=8+2*(BINS-1);
    localparam integer TW=LW+LEVELS;
    localparam integer ACCEPT_W=(T>1)?$clog2(T):1;
    localparam [1:0] IDLE=0, RUN=1, DRAIN=2, OUTPUT=3;
    reg [1:0] state;
    reg [ACCEPT_W-1:0] accepted;
    reg [STAGES-1:0] pipe_valid, pipe_last;
    wire frame_fire=frame_valid && frame_ready;
    wire sample_fire=sample_valid && sample_ready;
    wire sample_last=sample_fire && (accepted==T-1);
    assign frame_ready=(state==IDLE);
    assign sample_ready=(state==RUN);
    assign out_valid=(state==OUTPUT);
    wire data_enable=(!rst_n) || frame_fire || sample_fire || (|pipe_valid);
    wire data_clk;
    pbit_icg #(.GATE_MODE(GATE_MODE)) gate(
        .clk(clk),.en(data_enable),.test_en(test_en),.gclk(data_clk));

    wire signed [LW-1:0] leaf[0:M*N-1];
    genvar m,n,l,c,k;
    generate
        for(m=0;m<M;m=m+1) begin:g_leaf_m
            for(n=0;n<N;n=n+1) begin:g_leaf_n
                wire [6:0] magnitude=w_mag7[(m*N+n)*7+:7];
                wire negative=w_sign[m*N+n]^x_sign[n];
                wire [2:0] bin=bin_id[3*n+:3];
                wire selected=sample_fire && sample_bits[n] && (bin<BINS);
                wire signed [7:0] signed_weight=negative ?
                    -$signed({1'b0,magnitude}) : $signed({1'b0,magnitude});
                wire signed [LW-1:0] wide_weight={{(LW-8){signed_weight[7]}},signed_weight};
                // Extend BEFORE shifting. Invalid bins contribute zero.
                assign leaf[m*N+n]=selected ?
                    (wide_weight <<< (2*(BINS-1-bin))) : {LW{1'b0}};
            end
        end
        for(l=0;l<LEVELS;l=l+1) begin:g_tree
            localparam integer NODES=N>>(l+1);
            localparam integer SW=LW+l+1;
            localparam integer STAGE=l/PIPE_EVERY;
            wire signed [SW-1:0] value[0:M*NODES-1];
            for(c=0;c<M;c=c+1) begin:g_channel
                for(k=0;k<NODES;k=k+1) begin:g_node
                    wire signed [SW-2:0] a,z;
                    if(l==0) begin:from_leaf
                        assign a=leaf[c*N+2*k];
                        assign z=leaf[c*N+2*k+1];
                    end else begin:from_previous
                        assign a=g_tree[l-1].value[c*(2*NODES)+2*k];
                        assign z=g_tree[l-1].value[c*(2*NODES)+2*k+1];
                    end
                    wire signed [SW-1:0] sum=$signed({a[SW-2],a})+$signed({z[SW-2],z});
                    if(((l+1)%PIPE_EVERY)==0 || l==LEVELS-1) begin:registered_cut
                        reg signed [SW-1:0] q;
                        wire stage_valid;
                        if(STAGE==0) assign stage_valid=sample_fire;
                        else assign stage_valid=pipe_valid[STAGE-1];
                        always @(posedge data_clk) begin
                            if(!rst_n) q<=0;
                            else if(stage_valid) q<=sum;
                        end
                        assign value[c*NODES+k]=q;
                    end else begin:combinational_level
                        assign value[c*NODES+k]=sum;
                    end
                end
            end
        end
        for(c=0;c<M;c=c+1) begin:g_accum
            reg signed [AW-1:0] count;
            wire signed [TW-1:0] reduced=g_tree[LEVELS-1].value[c];
            wire signed [AW-1:0] extended={{(AW-TW){reduced[TW-1]}},reduced};
            always @(posedge data_clk) begin
                if(!rst_n) count<=0;
                else if(frame_fire) count<=0;
                else if(pipe_valid[STAGES-1]) count<=count+extended;
            end
            assign out_sum[c*AW+:AW]=count;
        end
    endgenerate

    integer p;
    // Always-on control: wake/drain/backpressure do not depend on a stopped clock.
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE; accepted<=0; pipe_valid<=0; pipe_last<=0;
        end else begin
            pipe_valid[0]<=sample_fire; pipe_last[0]<=sample_last;
            for(p=1;p<STAGES;p=p+1) begin
                pipe_valid[p]<=pipe_valid[p-1]; pipe_last[p]<=pipe_last[p-1];
            end
            if(frame_fire) begin
                state<=RUN; accepted<=0; pipe_valid<=0; pipe_last<=0;
            end
            if(sample_fire) begin
                if(sample_last) state<=DRAIN;
                else accepted<=accepted+1'b1;
            end
            if(pipe_valid[STAGES-1] && pipe_last[STAGES-1]) state<=OUTPUT;
            if(out_valid && out_ready) state<=IDLE;
        end
    end
`ifndef SYNTHESIS
    initial begin
        if(N<2 || (N&(N-1))!=0 || M<1 || (BINS!=4 && BINS!=7) || T<1 ||
           (PIPE_EVERY!=1 && PIPE_EVERY!=2) || AW<TW ||
           AW<1+$clog2(N*127*T+1)+2*(BINS-1))
            $fatal(1,"invalid sc_counter_merged geometry");
    end
`endif
endmodule
