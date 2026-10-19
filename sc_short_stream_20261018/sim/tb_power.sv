`timescale 1ns/1ps
// One DUT, one frame, identical stable inputs and seed across variants.
module tb_power;
    parameter integer MODE=1, LOG_T=7, INTERNAL_RNG=1, SAMPLER_ONLY=0;
    localparam integer N=64;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,sample_valid=0,seed_load=0;
    reg [31:0] seed_in=32'h13579bdf,external_state=32'h13579bdf;
    wire [7:0] ext_random=external_state[7:0];
    reg [N*8-1:0] probability=0,weights=0;
    reg [N-1:0] input_sign=0;
    wire busy,done,accept,rng_step;
    wire [LOG_T:0] sample_count;
    wire [7:0] threshold;
    wire [N-1:0] bits_out;
    wire [31:0] rng_state;
    wire signed [26:0] raw_sum;
    reg dump_enable=0;
    generate if(SAMPLER_ONLY) begin:sampler
        sc_ss_sampler #(.N(N),.MODE(MODE),.LOG_T(LOG_T),.INTERNAL_RNG(INTERNAL_RNG)) dut(
            .clk(clk),.rst_n(rst_n),.start(start),.sample_valid(sample_valid),
            .seed_load(seed_load),.seed_in(seed_in),.ext_random(ext_random),
            .probability(probability),.busy(busy),.done(done),.sample_count(sample_count),
            .accept(accept),.rng_step(rng_step),.threshold(threshold),.bits_out(bits_out),.rng_state(rng_state));
        assign raw_sum=0;
        initial begin wait(dump_enable);$dumpvars(0,tb_power.sampler.dut);end
    end else begin:integrated
        sc_ss_exact #(.N(N),.MODE(MODE),.LOG_T(LOG_T),.INTERNAL_RNG(INTERNAL_RNG)) dut(.*);
        initial begin wait(dump_enable);$dumpvars(0,tb_power.integrated.dut);end
    end endgenerate
    function automatic [31:0] step_rng(input [31:0] value);
        reg [31:0] a;
        begin a=value^(value<<13);a=a^(a>>17);step_rng=a^(a<<5);end
    endfunction
    always @(posedge clk) begin
        if(seed_load&&!busy) external_state<=seed_in;
        else if(rng_step) external_state<=step_rng(external_state);
    end
    integer kind,j,q,w,fd;
    time start_time,end_time;
    reg [2047:0] vcd_path,window_path;
    initial begin
        if(!$value$plusargs("CASE=%d",kind)) kind=1;
        if(!$value$plusargs("SEED=%h",seed_in)) seed_in=32'h13579bdf;
        if(seed_in==0) seed_in=32'h1;
        external_state=seed_in;
        if(!$value$plusargs("VCD=%s",vcd_path)) vcd_path="frame.vcd";
        if(!$value$plusargs("WINDOW=%s",window_path)) window_path="window.json";
        if(kind<0 || kind>4) $fatal(1,"Invalid CASE");
        for(j=0;j<N;j=j+1) begin
            case(kind)
                0:q=0;1:q=1+(j%2);2:q=26;3:q=128;
                default:case(j%5)0:q=0;1:q=1;2:q=255;3:q=128;default:q=26;endcase
            endcase
            case(j%4)0:w=-128;1:w=127;2:w=-1;default:w=0;endcase
            probability[j*8+:8]=q;weights[j*8+:8]=w;input_sign[j]=(j%3)==1;
        end
        repeat(2) @(posedge clk);
        @(negedge clk);rst_n=1;seed_load=1;
        @(negedge clk);seed_load=0;
        @(negedge clk);
        $dumpfile(vcd_path);dump_enable=1;
        start_time=$time;start=1;
        @(negedge clk);start=0;sample_valid=1;
        wait(done);@(negedge clk);sample_valid=0;end_time=$time;
        $dumpoff;
        fd=$fopen(window_path,"w");
        $fdisplay(fd,"{\"start_ns\":%0d,\"end_ns\":%0d,\"duration_ns\":%0d,\"clock_period_ns\":10,\"sample_cycles\":%0d,\"setup_cycles\":1,\"N\":64,\"mode\":%0d,\"internal_rng\":%0d,\"sampler_only\":%0d,\"case\":%0d,\"seed_hex\":\"%08h\",\"raw_sum\":%0d,\"includes_sram_energy\":false,\"technology_power_measured\":false}",start_time,end_time,end_time-start_time,1<<LOG_T,MODE,INTERNAL_RNG,SAMPLER_ONLY,kind,seed_in,$signed(raw_sum));
        $fclose(fd);
        if(sample_count!==(1<<LOG_T)) $fatal(1,"Power frame incomplete");
        $display("ALL_PASS power_window_ns=%0d accepted=%0d",end_time-start_time,sample_count);
        $finish;
    end
    initial begin #100000;$fatal(1,"Power timeout");end
endmodule
