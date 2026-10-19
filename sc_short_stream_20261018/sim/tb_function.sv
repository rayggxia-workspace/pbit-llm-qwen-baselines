`timescale 1ns/1ps
module tb_function;
    parameter integer N=64, MODE=1, LOG_T=7, INTERNAL_RNG=1;
    localparam integer SAMPLES=1<<LOG_T;
    localparam integer NEEDS_RANDOM=(MODE!=2)&&!(MODE==1&&LOG_T==8);
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0,sample_valid=0,seed_load=0;
    reg [31:0] seed_in=0;
    reg [7:0] ext_random=0;
    reg [N*8-1:0] probability=0,weights=0;
    reg [N-1:0] input_sign=0;
    wire busy,done,accept,rng_step;
    wire [LOG_T:0] sample_count;
    wire [7:0] threshold;
    wire [N-1:0] bits_out;
    wire [31:0] rng_state;
    wire signed [26:0] raw_sum;
    sc_ss_exact #(.N(N),.MODE(MODE),.LOG_T(LOG_T),.INTERNAL_RNG(INTERNAL_RNG)) dut(.*);
    function automatic [31:0] step_rng(input [31:0] value);
        reg [31:0] a;
        begin a=value^(value<<13);a=a^(a>>17);step_rng=a^(a<<5);end
    endfunction
    integer checked=0,frames=0,total_stalls=0;
    reg [31:0] reference_state=1;
    reg signed [63:0] last_total=0;
    reg [31:0] last_hash=0;
    task automatic set_inputs(input integer kind);
        integer j,q,w;
        begin
            for(j=0;j<N;j=j+1) begin
                case(kind)
                    0:q=0;
                    1:q=1+(j%2);
                    2:q=26;
                    3:q=128;
                    default:case(j%5) 0:q=0;1:q=1;2:q=255;3:q=128;default:q=26;endcase
                endcase
                case(j%4) 0:w=-128;1:w=127;2:w=-1;default:w=0;endcase
                probability[j*8+:8]=q;
                weights[j*8+:8]=w;
                input_sign[j]=(j%3)==1;
            end
        end
    endtask
    task automatic reload(input [31:0] value);
        begin
            @(negedge clk);seed_load=1;seed_in=value;start=0;sample_valid=0;
            @(posedge clk);#1;
            reference_state=value==0?32'h1:value;
            if(INTERNAL_RNG && NEEDS_RANDOM && rng_state!==reference_state) $fatal(1,"Seed load mismatch");
            if((!INTERNAL_RNG || !NEEDS_RANDOM) && rng_state!==0) $fatal(1,"Unused RNG state not zero");
            @(negedge clk);seed_load=0;
        end
    endtask
    task automatic frame(input integer kind,input integer stalled);
        integer index,cycles,j,r,q,w,partial,c;
        reg accepted;
        reg signed [63:0] total,enumerated;
        reg [31:0] hash,before_state;
        begin
            set_inputs(kind);index=0;cycles=0;total=0;hash=0;
            @(negedge clk);start=1;sample_valid=1;
            @(posedge clk);#1;
            if(!busy || done || sample_count!==0 || raw_sum!==0) $fatal(1,"Start handshake failure");
            while(index<SAMPLES) begin
                @(negedge clk);
                // Busy start and seed loads must be ignored, without dropping samples.
                start=(cycles==7);
                seed_load=(cycles==11);seed_in=32'hdeadbeef;
                sample_valid=!(stalled && (cycles%5==2 || cycles%11==3));
                ext_random=reference_state[7:0];
                #1;
                if(MODE==0) r=reference_state[7:0];
                else if(MODE==1) r=(index<<(8-LOG_T))|(reference_state[7:0]&((1<<(8-LOG_T))-1));
                else r=index;
                if(threshold!==r[7:0]) $fatal(1,"Threshold mismatch index=%0d expected=%0d actual=%0d",index,r,threshold);
                partial=0;
                for(j=0;j<N;j=j+1) begin
                    q=probability[j*8+:8];w=$signed(weights[j*8+:8]);
                    if(bits_out[j] !== (q>r)) $fatal(1,"Comparator mismatch lane %0d",j);
                    if(q>r) partial=partial+(input_sign[j]?-w:w);
                end
                accepted=sample_valid;
                if(accept!==accepted || rng_step!==(accepted&&NEEDS_RANDOM)) $fatal(1,"Accept/rng_step mismatch");
                before_state=reference_state;
                if(accepted) begin
                    total=total+partial;index=index+1;checked=checked+1;
                    hash=(hash<<1)^(hash>>31)^r;
                    if(NEEDS_RANDOM) reference_state=step_rng(reference_state);
                end else total_stalls=total_stalls+1;
                @(posedge clk);#1;
                if($signed(raw_sum)!==total) $fatal(1,"Accumulator mismatch N=%0d mode=%0d index=%0d expected=%0d actual=%0d",N,MODE,index,total,$signed(raw_sum));
                if(sample_count!==index) $fatal(1,"Counter mismatch expected=%0d actual=%0d",index,sample_count);
                if(INTERNAL_RNG && NEEDS_RANDOM && rng_state!==reference_state) $fatal(1,"PRNG replay/stall mismatch");
                if(done!==(index==SAMPLES) || busy!==(index<SAMPLES)) $fatal(1,"Completion mismatch");
                cycles=cycles+1;
            end
            if(!NEEDS_RANDOM) begin
                enumerated=0;
                for(j=0;j<N;j=j+1) begin
                    q=probability[j*8+:8];w=$signed(weights[j*8+:8]);
                    enumerated=enumerated+(input_sign[j]?-w:w)*q;
                end
                if(total!==enumerated) $fatal(1,"256-enumeration identity failure");
            end
            last_total=total;last_hash=hash;frames=frames+1;
            @(negedge clk);start=0;seed_load=0;sample_valid=0;
            @(posedge clk);#1;
            if(done || busy || sample_count!==SAMPLES || $signed(raw_sum)!==total) $fatal(1,"Done pulse or idle hold failure");
            $display("PASS frame=%0d N=%0d mode=%0d T=%0d internal=%0d case=%0d sum=%0d hash=%h cycles=%0d",frames,N,MODE,SAMPLES,INTERNAL_RNG,kind,total,hash,cycles);
        end
    endtask
    reg signed [63:0] saved_total;
    reg [31:0] saved_hash,checkpoint,base_seed;
    initial begin
        if(!$value$plusargs("SEED=%h",base_seed)) base_seed=32'h13579bdf;
        repeat(2) @(posedge clk);
        @(negedge clk);rst_n=1;
        // Start plus seed_load is explicitly blocked; seed load itself succeeds.
        @(negedge clk);seed_load=1;start=1;seed_in=0;
        @(posedge clk);#1;if(busy) $fatal(1,"Ambiguous start accepted during seed_load");
        @(negedge clk);seed_load=0;start=0;reference_state=1;
        reload(base_seed);frame(4,1);saved_total=last_total;saved_hash=last_hash;
        reload(base_seed);frame(4,0);
        if(last_total!==saved_total || last_hash!==saved_hash) $fatal(1,"Same seed replay changed under stalls");
        // Save/reload next-frame checkpoint: continuation and replay must match.
        checkpoint=reference_state;frame(1,1);saved_total=last_total;saved_hash=last_hash;
        reload(checkpoint);frame(1,0);
        if(last_total!==saved_total || last_hash!==saved_hash) $fatal(1,"Checkpoint replay mismatch");
        reload(0);frame(0,1);frame(2,0);frame(3,1);
        $display("ALL_PASS frames=%0d accepted=%0d stalls=%0d",frames,checked,total_stalls);
        $finish;
    end
    initial begin #2000000;$fatal(1,"Simulation timeout");end
endmodule
