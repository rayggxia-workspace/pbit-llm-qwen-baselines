`timescale 1ns/1ps
// Matrix-phase controller prototype. Six cores are a candidate configuration;
// the decode controller and arithmetic sources are not modified.
module plpu_prefill_top #(parameter CORES=6,CW=$clog2(CORES),GROUPS=64)(
 input wire clk,rst_n,cancel,
 input wire cmd_valid,output wire cmd_ready,
 input wire cmd_mode,input wire [2:0] cmd_log2,input wire [5:0] cmd_rows,
 input wire [6:0] cmd_groups,input wire [7:0] cmd_kblocks,
 input wire [63:0] cmd_base,input wire signed [7:0] cmd_base_exp,
 input wire [15:0] cmd_tag,input wire [CORES-1:0] cmd_core_mask,
 output wire done_valid,input wire done_ready,output wire [1:0] done_error,
 input wire [CORES-1:0] sample_enable,input wire seed_valid,
 input wire [CORES*128-1:0] seeds,
 output wire [3:0] rd_valid,input wire [3:0] rd_ready,
 output wire [255:0] rd_addr,output wire [31:0] rd_id,
 input wire [3:0] rsp_valid,output wire [3:0] rsp_ready,
 input wire [31:0] rsp_id,input wire [2047:0] rsp_data,input wire [3:0] rsp_error,
 output wire [CORES-1:0] row_req,input wire [CORES-1:0] row_valid,
 output wire [CORES-1:0] row_ready,output wire [CORES*6-1:0] row_index,
 output wire [CORES*16-1:0] row_group,row_k,
 input wire [CORES*640-1:0] row_x,input wire [CORES*1024-1:0] row_gu,
 input wire [CORES*7-1:0] row_scale,input wire [CORES*8-1:0] row_e0,row_e1,
 output wire [1:0] commit_valid,input wire [1:0] commit_ready,
 output wire [4095:0] commit_data,output wire [191:0] commit_meta,
 output wire [3:0] commit_beat,
 output wire dispatch_fire,output wire [CW-1:0] assigned_core,
 output wire [15:0] assigned_group,assigned_k,
 output wire [CORES-1:0] sample_fire,capture,weight_release,
 output wire [CORES*64-1:0] events,signs,
 output wire [CORES*6-1:0] capture_row,
 output wire [CORES*16-1:0] capture_group,capture_k,
 output wire [CORES*2-1:0] result_used,
 output wire [8:0] dma_used,output wire [1:0] bank_conflict,state_read,state_write,
 output wire [4:0] queue_used,output wire busy
);
 localparam QW=113+CORES;
 reg [QW-1:0] queue[0:15];reg [3:0] qread,qwrite;reg [4:0] qcount;
 reg active,aborting,finished;reg [1:0] error_latched;
 reg mode;reg [2:0] lg;reg [5:0] rows;reg [6:0] groups;
 reg [7:0] kblocks;reg [63:0] base;reg signed [7:0] base_exp;
 reg [15:0] tag;reg [CORES-1:0] core_mask;
 reg [GROUPS-1:0] group_busy,group_done;reg [7:0] next_k[0:GROUPS-1];
 reg [31:0] row_done[0:GROUPS-1];
 reg [CORES-1:0] lease_valid;reg [6:0] lease_group[0:CORES-1];
 reg [6:0] group_rr;reg [CW-1:0] core_rr;
 wire [CORES-1:0] core_ready,core_idle,res_valid;reg [CORES-1:0] res_ready;
 wire [CORES*128*21-1:0] res_data;wire [CORES*96-1:0] res_meta;
 wire [CORES*3-1:0] zone_states;wire [CORES*2-1:0] core_errors;
 wire [CORES*16-1:0] wr_valid,wr_ready,wr_error;
 wire [CORES*80-1:0] wr_row;wire [CORES*2048-1:0] wr_data;
 wire [CORES*256-1:0] wr_tag;
 wire dma_empty,dma_fault,desc_ready;
 wire [3:0] dout_valid,dout_ready,dout_error,rejected;
 wire [4*CW-1:0] dout_core;wire [51:0] dout_offset;
 wire [63:0] dout_tag;wire [2047:0] dout_data;
 wire [1:0] state_idle,state_error,state_in_ready;
 reg [1:0] state_in_valid;reg [2*32*21-1:0] state_count;
 reg [191:0] state_meta;reg [15:0] state_slot;reg [3:0] state_beat;
 wire stop=aborting||cancel;
 wire flush=stop;
 assign cmd_ready=rst_n&&!stop&&qcount<16;
 wire push=cmd_valid&&cmd_ready;
 wire pop=rst_n&&!stop&&!active&&!finished&&qcount!=0&&dma_empty&&(&core_idle)&&(&state_idle);
 assign done_valid=finished;assign done_error=error_latched;
 assign busy=active||aborting;assign queue_used=qcount;
 integer c,g,s,idx,gpick,cpick;
 always @*begin
   gpick=-1;cpick=-1;
   for(s=0;s<CORES;s=s+1)begin c=(core_rr+s)%CORES;
     if(cpick<0&&core_mask[c]&&core_ready[c])cpick=c;end
   for(s=0;s<GROUPS;s=s+1)begin g=(group_rr+s)%GROUPS;
     if(gpick<0&&g<groups&&!group_busy[g]&&!group_done[g]&&
       (!lease_valid[g%CORES]||lease_group[g%CORES]==g))gpick=g;end
 end
 assign assigned_core=cpick<0?0:CW'(cpick);
 assign assigned_group=gpick<0?0:16'(gpick);
 assign assigned_k=gpick<0?0:{8'd0,next_k[gpick]};
 assign dispatch_fire=rst_n&&active&&!stop&&cpick>=0&&gpick>=0&&desc_ready;
 wire [63:0] tile_address=base+((64'(assigned_group)*kblocks+assigned_k)<<13);
 plpu_shared_dma #(.CORES(CORES),.CW(CW)) dma(
  .clk(clk),.rst_n(rst_n),.stop(stop),.desc_valid(dispatch_fire),.desc_ready(desc_ready),
  .desc_core(assigned_core),.desc_tag(tag),.desc_addr(tile_address),
  .rd_valid(rd_valid),.rd_ready(rd_ready),.rd_addr(rd_addr),.rd_id(rd_id),
  .rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.rsp_id(rsp_id),.rsp_data(rsp_data),.rsp_error(rsp_error),
  .out_valid(dout_valid),.out_ready(dout_ready),.out_core(dout_core),.out_tag(dout_tag),
  .out_offset(dout_offset),.out_data(dout_data),.out_error(dout_error),
  .target_enabled({CORES{!stop}}),.empty(dma_empty),.used_total(dma_used),.protocol_error(dma_fault));
 plpu_cim_write_router #(.CORES(CORES),.PORTS(4),.CW(CW)) router(
  .clk(clk),.rst_n(rst_n),.flush(flush),.in_valid(dout_valid),.in_ready(dout_ready),
  .in_core(dout_core),.in_offset(dout_offset),.in_data(dout_data),.in_tag(dout_tag),
  .in_error(dout_error),.rejected(rejected),.wr_valid(wr_valid),.wr_ready(wr_ready),
  .wr_row(wr_row),.wr_data(wr_data),.wr_tag(wr_tag),.wr_error(wr_error));
 genvar n;
 generate for(n=0;n<CORES;n=n+1)begin:core
  plpu_prefill_core compute(.clk(clk),.rst_n(rst_n),.flush(flush),.sample_enable(sample_enable[n]),
   .seed_valid(seed_valid),.seeds(seeds[n*128+:128]),
   .cmd_valid(dispatch_fire&&assigned_core==n),.cmd_ready(core_ready[n]),
   .cmd_mode(mode),.cmd_log2(lg),.cmd_rows(rows),.cmd_group(assigned_group),
   .cmd_k(assigned_k),.cmd_tag(tag),.cmd_last(assigned_k+1==kblocks),
   .wr_valid(wr_valid[n*16+:16]),.wr_ready(wr_ready[n*16+:16]),
   .wr_row(wr_row[n*80+:80]),.wr_data(wr_data[n*2048+:2048]),
   .wr_tag(wr_tag[n*256+:256]),.wr_error(wr_error[n*16+:16]),
   .row_req(row_req[n]),.row_valid(row_valid[n]),.row_ready(row_ready[n]),
   .row_index(row_index[n*6+:6]),.row_group(row_group[n*16+:16]),.row_k(row_k[n*16+:16]),
   .row_x(row_x[n*640+:640]),.row_gu(row_gu[n*1024+:1024]),
   .row_scale(row_scale[n*7+:7]),.row_e0(row_e0[n*8+:8]),.row_e1(row_e1[n*8+:8]),
   .result_valid(res_valid[n]),.result_ready(res_ready[n]),
   .result_data(res_data[n*128*21+:128*21]),.result_meta(res_meta[n*96+:96]),
   .sample_fire(sample_fire[n]),.events(events[n*64+:64]),.signs(signs[n*64+:64]),
   .capture(capture[n]),.weight_release(weight_release[n]),.idle(core_idle[n]),
   .dbg_row(capture_row[n*6+:6]),.dbg_group(capture_group[n*16+:16]),.dbg_k(capture_k[n*16+:16]),
   .result_used(result_used[n*2+:2]),.zone_state(zone_states[n*3+:3]),.error(core_errors[n*2+:2]));
 end endgenerate
 // Each result packet is four 32-lane beats. Token row parity selects a
 // worker; a core's FIFO head remains owned until beat3 has been accepted.
 reg [1:0] hold;reg [CW-1:0] chosen[0:1],rr[0:1];reg [1:0] beat[0:1];
 integer p,j,sel[0:1];reg [95:0] sm;
 always @*begin
  state_in_valid=0;state_count=0;state_meta=0;state_slot=0;state_beat=0;sm=0;idx=0;
  for(p=0;p<2;p=p+1)begin
   sel[p]=-1;
   if(hold[p])sel[p]=chosen[p];
   else for(j=0;j<CORES;j=j+1)begin idx=(rr[p]+j)%CORES;
    if(sel[p]<0&&res_valid[idx]&&res_meta[idx*96+49]==p)sel[p]=idx;end
   if(sel[p]>=0)begin
    sm=res_meta[sel[p]*96+:96];state_meta[p*96+:96]=sm;
    state_slot[p*8+:8]=8'((sm[15:0]%CORES)*32+sm[64:49]);
    state_beat[p*2+:2]=hold[p]?beat[p]:2'd0;
    state_count[p*32*21+:32*21]=res_data[sel[p]*128*21+(hold[p]?beat[p]:0)*32*21+:32*21];
    state_in_valid[p]=res_valid[sel[p]]&&!stop;
   end
  end
 end
 // Keep payload/valid selection independent of downstream ready.
 always @*begin
  res_ready=0;
  for(integer w=0;w<2;w=w+1)
   if(sel[w]>=0&&state_in_ready[w]&&state_in_valid[w]&&state_beat[w*2+:2]==3)
    res_ready[sel[w]]=1;
 end
 plpu_prefill_state state_mem(.clk(clk),.rst_n(rst_n),.flush(flush),
  .in_valid(state_in_valid),.in_ready(state_in_ready),.in_count(state_count),
  .in_meta(state_meta),.in_slot(state_slot),.in_beat(state_beat),.base_exp(base_exp),
  .out_valid(commit_valid),.out_ready(commit_ready),.out_data(commit_data),.out_meta(commit_meta),
  .out_beat(commit_beat),.out_error(state_error),.idle(state_idle),.bank_conflict(bank_conflict),
  .read_fire(state_read),.write_fire(state_write));
 wire [31:0] expected_rows=rows==32?32'hffffffff:(32'd1<<rows)-1;
 reg [31:0] completed_mask;reg all_done;
 always @*begin all_done=1;for(integer a=0;a<GROUPS;a=a+1)if(a<groups&&!group_done[a])all_done=0;end
 always @(posedge clk)begin
  if(!rst_n)begin qread<=0;qwrite<=0;qcount<=0;active<=0;aborting<=0;finished<=0;
   error_latched<=0;group_busy<=0;group_done<=0;lease_valid<=0;hold<=0;
   core_rr<=0;group_rr<=0;for(integer a=0;a<2;a=a+1)begin rr[a]<=0;beat[a]<=0;end
  end else begin
   if(push)begin queue[qwrite]<={cmd_core_mask,cmd_tag,cmd_base_exp,cmd_base,cmd_kblocks,cmd_groups,cmd_rows,cmd_log2,cmd_mode};qwrite<=qwrite+1;end
   if(pop)begin
    {core_mask,tag,base_exp,base,kblocks,groups,rows,lg,mode}<=queue[qread];
    qread<=qread+1;active<=1;error_latched<=0;group_busy<=0;group_done<=0;lease_valid<=0;
    core_rr<=0;group_rr<=0;
    for(integer a=0;a<GROUPS;a=a+1)begin next_k[a]<=0;row_done[a]<=0;end
   end
   case({push,pop})2'b10:qcount<=qcount+1;2'b01:qcount<=qcount-1;default:;endcase
   if(finished&&done_ready)finished<=0;
   if(dispatch_fire)begin group_busy[assigned_group]<=1;row_done[assigned_group]<=0;
    lease_valid[assigned_group%CORES]<=1;lease_group[assigned_group%CORES]<=assigned_group;
    core_rr<=(assigned_core+1)%CORES;group_rr<=(assigned_group+1)%GROUPS;end
   for(integer a=0;a<GROUPS;a=a+1)begin
    completed_mask=row_done[a];
    for(integer w=0;w<2;w=w+1)if(commit_valid[w]&&commit_ready[w]&&commit_beat[w*2+:2]==3&&commit_meta[w*96+:16]==a)
      completed_mask[commit_meta[w*96+49+:16]]=1;
    if(completed_mask!=row_done[a])begin
     row_done[a]<=completed_mask;
     if(completed_mask==expected_rows)begin group_busy[a]<=0;
      if(next_k[a]+1==kblocks)begin group_done[a]<=1;lease_valid[a%CORES]<=0;end
      else next_k[a]<=next_k[a]+1;end
    end
   end
   for(integer w=0;w<2;w=w+1)if(state_in_valid[w]&&state_in_ready[w])begin
    if(state_beat[w*2+:2]==3)begin hold[w]<=0;rr[w]<=(sel[w]+1)%CORES;end
    else begin hold[w]<=1;chosen[w]<=sel[w];beat[w]<=state_beat[w*2+:2]+1;end
   end
   if(active&&all_done&&dma_empty&&(&core_idle)&&(&state_idle))begin active<=0;finished<=1;end
   if(cancel||(active&&(dma_fault||(|core_errors)||(|rejected)||(|(state_error&commit_valid)))))begin
    active<=0;aborting<=1;error_latched<=cancel?2'd1:2'd2;qcount<=0;qread<=0;qwrite<=0;hold<=0;
   end
   if(aborting&&dma_empty)begin aborting<=0;finished<=1;end
  end
 end
`ifndef SYNTHESIS
 always @(posedge clk)if(rst_n&&!stop)begin
  if(pop)begin
   assert(queue[qread][9:4]>0&&queue[qread][9:4]<=32)else $fatal(1,"prompt block rows");
   assert(queue[qread][16:10]>0&&queue[qread][16:10]<=GROUPS)else $fatal(1,"groups");
   assert(queue[qread][24:17]>0)else $fatal(1,"K length");
  end
  if(dispatch_fire)assert(core_ready[assigned_core])else $fatal(1,"dispatch target");
  for(integer w=0;w<2;w=w+1)if(commit_valid[w]&&commit_ready[w])begin
   assert(group_busy[commit_meta[w*96+:16]])else $fatal(1,"orphan result");
   assert(commit_meta[w*96+16+:16]==next_k[commit_meta[w*96+:16]])else $fatal(1,"K order");
  end
 end
`endif
endmodule
