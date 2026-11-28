`timescale 1ns/1ps
// One physical single-zone CIM, many input rows per resident weight tile.
// The arithmetic, probability encoder and PRNG are the unchanged upstream RTL.
module plpu_prefill_core #(parameter AW=21)(
 input wire clk,rst_n,flush,sample_enable,seed_valid,
 input wire [127:0] seeds,
 input wire cmd_valid,output wire cmd_ready,
 input wire cmd_mode,input wire [2:0] cmd_log2,
 input wire [5:0] cmd_rows,input wire [15:0] cmd_group,cmd_k,cmd_tag,
 input wire cmd_last,
 input wire [15:0] wr_valid,output wire [15:0] wr_ready,
 input wire [79:0] wr_row,input wire [2047:0] wr_data,
 input wire [255:0] wr_tag,input wire [15:0] wr_error,
 output wire row_req,input wire row_valid,output wire row_ready,
 output wire [5:0] row_index,output wire [15:0] row_group,row_k,
 input wire [639:0] row_x,input wire [1023:0] row_gu,
 input wire [6:0] row_scale,input wire signed [7:0] row_e0,row_e1,
 output wire result_valid,input wire result_ready,
 output wire [128*AW-1:0] result_data,output wire [95:0] result_meta,
 output wire sample_fire,output wire [63:0] events,signs,
 output wire capture,weight_release,output wire idle,
 output wire [5:0] dbg_row,output wire [15:0] dbg_group,dbg_k,
 output wire [1:0] result_used,output wire [2:0] zone_state,
 output wire [1:0] error
);
 reg active,started,mode,last;
 reg [2:0] lg;reg [5:0] rows,issued,captured;
 reg [15:0] group_id,k_id,tag;
 reg [1023:0] gu_hold;reg [6:0] scale_hold;
 wire zready,zcompute,zrelease,zvalid,worker_ready;
 wire [65535:0] weights;wire [2:0] worker_state;
 wire launch=cmd_valid&&cmd_ready;
 assign cmd_ready=rst_n&&!flush&&!active&&zready;
 wire accept=row_valid&&row_ready;
 assign row_req=rst_n&&!flush&&active&&issued<rows;
 assign row_ready=row_req&&worker_ready&&zvalid&&(started||zcompute);
 assign row_index=issued;assign row_group=group_id;assign row_k=k_id;
 assign dbg_row=captured;assign dbg_group=group_id;assign dbg_k=k_id;
 assign weight_release=capture&&captured+1==rows;
 assign idle=!active&&worker_state==0&&result_used==0&&zone_state==0;
 wire [95:0] meta={14'd0,last,tag,{10'd0,issued},mode,row_e1,row_e0,k_id,group_id};
 plpu_cim_single_zone zone(.clk(clk),.rst_n(rst_n),.cancel(flush),
   .cmd_valid(launch),.cmd_ready(zready),.cmd_tag(cmd_tag),.cmd_meta(64'd0),
   .wr_valid(wr_valid),.wr_ready(wr_ready),.wr_row(wr_row),.wr_data(wr_data),
   .wr_tag(wr_tag),.wr_error(wr_error),.compute_valid(accept&&!started),
   .compute_ready(zcompute),.release_valid(weight_release),.release_ready(zrelease),
   .weights(weights),.weights_valid(zvalid),.active_tag(),.active_meta(),
   .state(zone_state),.loaded_words(),.error_code(error),.stale_seen());
 plpu_tile_worker #(.AW(AW),.MW(96)) worker(
   .clk(clk),.rst_n(rst_n),.flush(flush),.sample_enable(sample_enable),
   .seed_valid(seed_valid),.seeds(seeds),
   .job_valid(row_valid&&row_req&&zvalid&&(started||zcompute)),.job_ready(worker_ready),
   .job_mode(mode),.job_log2(lg),.job_meta(meta),.x(row_x),.gu_codes(gu_hold),
   .gu_scale(scale_hold),.weights(weights),.result_valid(result_valid),
   .result_ready(result_ready),.result_data(result_data),.result_meta(result_meta),
   .release_cim(capture),.sample_fire(sample_fire),.events(events),.signs(signs),
   .result_used(result_used),.debug_state(worker_state),.sample_pos());
 always @(posedge clk)begin
   if(!rst_n||flush)begin active<=0;started<=0;issued<=0;captured<=0;end
   else begin
     if(launch)begin active<=1;started<=0;mode<=cmd_mode;last<=cmd_last;lg<=cmd_log2;
       rows<=cmd_rows;group_id<=cmd_group;k_id<=cmd_k;tag<=cmd_tag;issued<=0;captured<=0;end
     if(accept)begin issued<=issued+1;started<=1;gu_hold<=row_gu;scale_hold<=row_scale;end
     if(capture)begin captured<=captured+1;if(weight_release)active<=0;end
   end
 end
`ifndef SYNTHESIS
 always @(posedge clk)if(rst_n&&!flush)begin
   if(launch)assert(cmd_rows>0&&cmd_rows<=32) else $fatal(1,"bad rows");
   if(capture)assert(captured<issued&&active) else $fatal(1,"capture identity");
   if(weight_release)assert(zrelease&&issued==rows) else $fatal(1,"early release");
 end
`endif
endmodule
