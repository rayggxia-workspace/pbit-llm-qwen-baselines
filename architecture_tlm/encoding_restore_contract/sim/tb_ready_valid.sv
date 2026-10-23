`timescale 1ns/1ps
`ifndef KIND
 `define KIND 0
`endif
`ifndef DEPTH
 `define DEPTH 3
`endif
`ifndef T_LOG2
 `define T_LOG2 5
`endif
`ifndef COUNT_W
 `define COUNT_W 12
`endif
module tb_ready_valid;
 localparam integer KIND=`KIND,DEPTH=`DEPTH,FRAC=(KIND==0?7:23);
 localparam integer T_LOG2=`T_LOG2,COUNT_W=`COUNT_W;
 localparam integer CW=(DEPTH<2?1:$clog2(DEPTH+1));
 localparam integer VISIBLE_LATENCY=(KIND==2?1:2);
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,in_valid=0,out_ready=0;
 wire in_ready,out_valid;reg [2047:0] data_in=0;
 reg [15:0] exp_in=0;reg [31:0] scale_in=0,in_tag=0;
 wire [31:0] out_tag;wire [784:0] data_out;
 wire [CW-1:0] reserved_count,queued_count;
`ifdef ER_DUT_TOP
 // Same explicit interface for a generated RTL top or a separately supplied
 // mapped top. Defining this macro does not establish gate-level validation.
 `ER_DUT_TOP dut(.clk(clk),.rst_n(rst_n),.in_valid(in_valid),.in_ready(in_ready),
  .data_in(data_in),.exp_in(exp_in),.scale_in(scale_in),.in_tag(in_tag),
  .out_valid(out_valid),.out_ready(out_ready),.data_out(data_out),.out_tag(out_tag),
  .reserved_count(reserved_count),.queued_count(queued_count));
`else
 generate if(KIND==2)begin:restore
  er_bin_restore_rv #(.COUNT_W(COUNT_W),.T_LOG2(T_LOG2),.DEPTH(DEPTH)) dut(clk,rst_n,in_valid,in_ready,
   data_in[64*COUNT_W-1:0],exp_in,scale_in,in_tag,out_valid,out_ready,
   data_out[31:0],out_tag,reserved_count,queued_count);
  assign data_out[784:32]=0;
 end else begin:encode
  er_pot_encoder_rv #(.FRAC(FRAC),.DEPTH(DEPTH)) dut(clk,rst_n,in_valid,in_ready,
   data_in[64*(FRAC+9)-1:0],in_tag,out_valid,out_ready,
   data_out[511:0],data_out[639:512],data_out[703:640],data_out[767:704],
   data_out[783:768],data_out[784],out_tag,reserved_count,queued_count);
 end endgenerate
`endif
 reg [2047:0] vectors[0:255];reg [15:0] exponents[0:255];
 reg [31:0] scales[0:255];reg [784:0] golden[0:255];
 reg [784:0] expected[0:4095];reg [31:0] expected_tags[0:4095];
 integer accepted_at[0:4095];reg seen[0:4095];
 integer vector_count=0,fd,scan;reg [2047:0] filename;
 reg [2047:0] vcd_path,window_path;integer window_fd;
 time window_start_ps=0,window_end_ps=0;
 integer window_accepted_start=0,window_received_start=0;
 integer window_accepted=0,window_received=0;
 integer cycle=0,stage=-1,head=0,tail=0,tx_sequence=0;
 integer accepted_total=0,received_total=0,flushed_total=0;
 integer blocked_inputs=0,stalled_outputs=0,max_reserved=0,max_queued=0;
 integer simultaneous_transfer_accept=0,input_bubbles=0;
 integer visible_min=99999,visible_max=0,transfer_min=99999,transfer_max=0;
 integer previous_accept=-1,previous_stage=-1,ii_min=99999,ii_max=0;
 integer age,ii,steps,i,seed=7;reg [31:0] rng;
 reg held=0;reg [784:0] held_data;reg [31:0] held_tag;
 reg producer_waiting=0;reg [2047:0] producer_data;
 reg [15:0] producer_exp;reg [31:0] producer_scale,producer_tag;
 // Pre-edge samples define transfers. Post-edge samples define visibility.
 // Both are reported to prevent a one-edge ambiguity in cycle integration.
 always @(posedge clk)begin
  cycle=cycle+1;
  if(!rst_n)begin
   flushed_total=flushed_total+(tail-head);head=0;tail=0;held=0;producer_waiting=0;
   previous_accept=-1;previous_stage=-1;
  end else begin
   if(tail-head!=reserved_count)$fatal(1,"reservation/scoreboard mismatch");
   if(reserved_count>DEPTH||queued_count>reserved_count)$fatal(1,"unbounded queue");
   if(held&&(!out_valid||data_out!==held_data||out_tag!==held_tag))
    $fatal(1,"output changed under backpressure");
   if(producer_waiting&&(!in_valid||data_in!==producer_data||
      exp_in!==producer_exp||scale_in!==producer_scale||in_tag!==producer_tag))
    $fatal(1,"producer withdrew valid or changed payload before acceptance");
   producer_waiting=in_valid&&!in_ready;
   producer_data=data_in;producer_exp=exp_in;producer_scale=scale_in;producer_tag=in_tag;
   held=out_valid&&!out_ready;held_data=data_out;held_tag=out_tag;
   if(in_valid&&!in_ready)blocked_inputs=blocked_inputs+1;
   if(out_valid&&!out_ready)stalled_outputs=stalled_outputs+1;
   if(stage==2&&!in_valid)input_bubbles=input_bubbles+1;
   if(in_valid&&in_ready&&out_valid&&out_ready)
    simultaneous_transfer_accept=simultaneous_transfer_accept+1;
   if(in_valid&&in_ready)begin
    expected[tail]=golden[tx_sequence%vector_count];
    expected_tags[tail]=tx_sequence;accepted_at[tail]=cycle;seen[tail]=0;
    tail=tail+1;tx_sequence=tx_sequence+1;accepted_total=accepted_total+1;
    if(stage==0||stage==3)begin
     if(previous_stage==stage)begin
      ii=cycle-previous_accept;if(ii<ii_min)ii_min=ii;if(ii>ii_max)ii_max=ii;
     end
     previous_accept=cycle;previous_stage=stage;
    end
   end
   if(out_valid&&out_ready)begin
    if(head>=tail)$fatal(1,"output without accepted transaction");
    if(data_out!==expected[head]||out_tag!==expected_tags[head])begin
     $display("FAIL_DATA kind=%0d tag=%0d expected_tag=%0d actual=%h expected=%h",
      KIND,out_tag,expected_tags[head],data_out,expected[head]);
     $fatal(1,"arithmetic/order mismatch");
    end
    age=cycle-accepted_at[head];if(age<transfer_min)transfer_min=age;
    if(age>transfer_max)transfer_max=age;
    head=head+1;received_total=received_total+1;
   end
  end
  #1;
  if(rst_n)begin
   if(tail-head!=reserved_count)$fatal(1,"post-edge reservation mismatch");
   if(reserved_count>max_reserved)max_reserved=reserved_count;
   if(queued_count>max_queued)max_queued=queued_count;
   if(out_valid)begin
    if(head>=tail||data_out!==expected[head]||out_tag!==expected_tags[head])
     $fatal(1,"visible head differs from arithmetic/order oracle");
    if(!seen[head])begin
     age=cycle-accepted_at[head];if(age<visible_min)visible_min=age;
     if(age>visible_max)visible_max=age;seen[head]=1;
    end
   end
  end
 end
 task automatic drive(input integer mode,input integer count);
  integer n;
  begin
   for(n=0;n<count;n=n+1)begin
    @(negedge clk);stage=mode;
    // First 32 continuous cycles warm the bounded pipeline. Record the last
    // 64 cycles only; the selected window contains neither reset nor drain.
    if(mode==3&&n==32)begin
     window_start_ps=$time*1000;
     window_accepted_start=accepted_total;window_received_start=received_total;
    end
    if(mode==4&&n==0)begin
     window_end_ps=$time*1000;
     window_accepted=accepted_total-window_accepted_start;
     window_received=received_total-window_received_start;
    end
    rng=rng*32'd1664525+32'd1013904223;
    // Once offered, a transaction remains valid with the same payload until
    // accepted (or reset). Random bubbles only occur between transactions.
    in_valid=producer_waiting?1:((mode==4)?0:((mode==2)?rng%100<67:1));
    rng=rng*32'd1664525+32'd1013904223;
    out_ready=(mode==1)?0:((mode==2)?rng%100<53:1);
    data_in=vectors[tx_sequence%vector_count];
    exp_in=exponents[tx_sequence%vector_count];
    scale_in=scales[tx_sequence%vector_count];in_tag=tx_sequence;
   end
  end
 endtask
 initial begin
  if(KIND==2&&(T_LOG2<4||T_LOG2>6||COUNT_W!=T_LOG2+7))
   $fatal(1,"unsupported restoration T/count-width configuration");
`ifdef ER_DUT_TOP
  if($value$plusargs("VCD=%s",vcd_path))begin
   $dumpfile(vcd_path);$dumpvars(0,dut);
  end
`endif
  if(!$value$plusargs("VECTORS=%s",filename))$fatal(1,"missing vectors");
  if($value$plusargs("SEED=%d",seed))begin end
  rng=seed;fd=$fopen(filename,"r");if(!fd)$fatal(1,"cannot read vectors");
  while(!$feof(fd))begin
   scan=$fscanf(fd,"%h %h %h %h\n",vectors[vector_count],exponents[vector_count],
    scales[vector_count],golden[vector_count]);
   if(scan==4)vector_count=vector_count+1;
   else if(!$feof(fd))$fatal(1,"malformed vector");
  end
  $fclose(fd);if(vector_count<32)$fatal(1,"insufficient vectors");
  repeat(2)@(negedge clk);rst_n=1;
  drive(0,96); // Continuous ready/valid measures unthrottled II.
  drive(1,20); // Fill every reserved slot and stall a stable head.
  @(negedge clk);
  if(reserved_count!=DEPTH||!out_valid)$fatal(1,"queue did not saturate");
  rst_n=0;in_valid=0;out_ready=0; // Flush accepted work while backpressured.
  repeat(2)@(negedge clk);rst_n=1;
  drive(5,1);
  @(negedge clk);
  if(reserved_count!=1||queued_count!=0)$fatal(1,"missing in-flight reset setup");
  rst_n=0;in_valid=0;out_ready=0; // Also flush an unfinished core operation.
  repeat(2)@(negedge clk);rst_n=1;
  drive(2,240); // Independent bubbles and output stalls.
  drive(3,96); // Recover full throughput after stalls and reset.
  drive(4,DEPTH+8); // Drain.
  @(negedge clk);
  if(head!=tail||reserved_count||out_valid)$fatal(1,"drain did not finish");
  if(accepted_total!=received_total+flushed_total)$fatal(1,"lost or duplicate operation");
  if(flushed_total!=DEPTH+1||blocked_inputs==0||stalled_outputs==0||
     input_bubbles==0||simultaneous_transfer_accept==0)
   $fatal(1,"missing backpressure/reset coverage");
  if(visible_min!=VISIBLE_LATENCY||transfer_min!=VISIBLE_LATENCY+1)
   $fatal(1,"unexpected no-stall latency");
  if(DEPTH>=VISIBLE_LATENCY+1&&(ii_min!=1||ii_max!=1))
   $fatal(1,"full-rate capacity has an avoidable II bubble");
  if(DEPTH==1&&(ii_min!=VISIBLE_LATENCY+1||ii_max!=VISIBLE_LATENCY+1))
   $fatal(1,"single-slot II differs from reservation lifetime");
  if(window_end_ps-window_start_ps!=640000||window_accepted<=0||window_received<=0)
   $fatal(1,"invalid selected activity window");
  if(DEPTH>=VISIBLE_LATENCY+1&&(window_accepted!=64||window_received!=64))
   $fatal(1,"full-rate selected activity window is not 64 complete operations");
  if($value$plusargs("WINDOW=%s",window_path))begin
   window_fd=$fopen(window_path,"w");if(!window_fd)$fatal(1,"cannot write activity window");
   $fdisplay(window_fd,"scenario=synthetic_active");
   $fdisplay(window_fd,"timescale=1ns/1ps");
   $fdisplay(window_fd,"start_ps=%0d",window_start_ps);
   $fdisplay(window_fd,"end_ps=%0d",window_end_ps);
   $fdisplay(window_fd,"period_ps=10000");
   $fdisplay(window_fd,"accepted=%0d",window_accepted);
   $fdisplay(window_fd,"completed=%0d",window_received);
   $fdisplay(window_fd,"contains_reset=0");$fdisplay(window_fd,"contains_drain=0");
   $fdisplay(window_fd,"warmup_continuous_cycles=32");$fclose(window_fd);
  end
  $display("PASS kind=%0d samples=%0d count_width=%0d depth=%0d seed=%0d accepted=%0d received=%0d flushed=%0d blocked=%0d stalled=%0d max_reserved=%0d max_queued=%0d visible_min=%0d visible_max=%0d transfer_min=%0d transfer_max=%0d ii_min=%0d ii_max=%0d simultaneous=%0d input_bubbles=%0d",
   KIND,(KIND==2?(1<<T_LOG2):0),(KIND==2?COUNT_W:0),DEPTH,seed,accepted_total,received_total,flushed_total,blocked_inputs,stalled_outputs,
   max_reserved,max_queued,visible_min,visible_max,transfer_min,transfer_max,ii_min,ii_max,
   simultaneous_transfer_accept,input_bubbles);
  $finish;
 end
 initial begin #200000;$fatal(1,"timeout");end
endmodule
