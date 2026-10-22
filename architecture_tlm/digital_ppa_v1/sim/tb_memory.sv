`timescale 1ns/1ps
module tb_memory;
 reg clk=0;always #5 clk=~clk;reg rst_n=0;
 reg [3:0] qv=0,qw=0,rr=0;reg [127:0] qa=0,qd=0;wire [3:0] qr,rv;wire [127:0] rd;
 wire [15:0] en,we;wire [63:0] ba;wire [511:0] wd;reg [511:0] bd=0;
`ifdef GATE_ROUTER
 nr_sram_router_mapped router(clk,rst_n,qv,qw,qa,qd,qr,rv,rr,rd,16'hffff,en,we,ba,wd,bd);
`else
 nr_sram_router #(.PORTS(4),.BANKS(16),.DATA_W(32),.ROW_W(4)) router(clk,rst_n,qv,qw,qa,qd,qr,rv,rr,rd,16'hffff,en,we,ba,wd,bd);
`endif
 // Testbench memory ONLY: the synthesized router has no SRAM/DFF data array.
 reg [31:0] memory[0:15][0:15];integer b,r;
 always @(posedge clk)for(b=0;b<16;b=b+1)if(en[b])begin
  if(we[b])memory[b][ba[b*4+:4]]<=wd[b*32+:32];
  bd[b*32+:32]<=memory[b][ba[b*4+:4]];
 end
 reg start=0;reg [63:0] base=64'h1000;reg [31:0] bursts=35;
 reg cmd_ready=0,complete=0;wire cmd_valid,complete_ready,busy,done,error;wire [63:0] cmd_address;
`ifdef GATE_DMA
 nr_dma_window_mapped dma(clk,rst_n,start,base,bursts,cmd_valid,cmd_ready,cmd_address,complete,complete_ready,busy,done,error);
`else
 nr_dma_window #(.WINDOW(4)) dma(clk,rst_n,start,base,bursts,cmd_valid,cmd_ready,cmd_address,complete,complete_ready,busy,done,error);
`endif
 integer timeout,accepted,owed,issued,retired,ticks;reg [3:0] fire;reg ci,cr;
 reg [4095:0] wave_name;integer wf;real router_start,router_end,dma_start,dma_end;
 initial begin
  if($value$plusargs("VCD=%s",wave_name))begin $dumpfile(wave_name);$dumpvars(0,tb_memory);end
  for(b=0;b<16;b=b+1)for(r=0;r<16;r=r+1)memory[b][r]=b*256+r;
  repeat(3)@(negedge clk);rst_n=1;
  @(negedge clk);router_start=$realtime;qv=3;qa[31:0]=0;qa[63:32]=64;accepted=0;
  timeout=0;
  while(accepted<2&&timeout<30)begin
   @(posedge clk);fire=qv&qr;accepted=accepted+fire[0]+fire[1];#1;qv=qv&~fire;timeout=timeout+1;
  end
  if(accepted!=2)$fatal(1,"bank arbitration stalled");
  timeout=0;while(rv!=3&&timeout<30)begin @(negedge clk);timeout=timeout+1;end
  if(rv!=3||rd[31:0]!==0||rd[63:32]!==1)$fatal(1,"SRAM read/owner mismatch");
  repeat(3)begin @(negedge clk);if(rv!=3||rd[63:32]!==1)$fatal(1,"response not held");end
  rr=15;repeat(3)@(negedge clk);
  qv=4;qw=4;qa[95:64]=212;qd[95:64]=32'hdeadbeef;
  @(posedge clk);if(!qr[2])$fatal(1,"write not accepted");#1;qv=0;
  repeat(5)@(negedge clk);qw=0;qv=8;qa[127:96]=212;
  @(posedge clk);if(!qr[3])$fatal(1,"read not accepted");#1;qv=0;
  timeout=0;while(!rv[3]&&timeout<20)begin @(negedge clk);timeout=timeout+1;end
  if(!rv[3]||rd[127:96]!==32'hdeadbeef)$fatal(1,"read after write mismatch");
  @(negedge clk);router_end=$realtime;dma_start=$realtime;start=1;
  @(negedge clk);start=0;owed=0;issued=0;retired=0;ticks=0;
  while(!done&&ticks<300)begin
   cmd_ready=ticks%5!=0;complete=owed>0&&ticks%3!=0;
   @(posedge clk);ci=cmd_valid&&cmd_ready;cr=complete&&complete_ready;
   if(ci)begin if(cmd_address!==base+issued*64)$fatal(1,"DMA address");issued=issued+1;end
   if(cr)retired=retired+1;
   owed=owed+ci-cr;if(owed>4||owed<0)$fatal(1,"DMA window bound");
   #1;if(error)$fatal(1,"DMA protocol error");ticks=ticks+1;
   @(negedge clk);
  end
  if(!done||issued!=35||retired!=35||owed!=0)$fatal(1,"DMA drain/completion");
  start=1;bursts=0;complete=0;
  @(posedge clk);#1;if(!done||busy)$fatal(1,"zero DMA");
  dma_end=$realtime;
  @(negedge clk);bursts=1;start=1;cmd_ready=0;complete=0;
  @(negedge clk);start=0;complete=1;
  @(posedge clk);#1;if(!error)$fatal(1,"illegal completion not flagged");
  wf=$fopen("router_window.txt","w");$fdisplay(wf,"start_ns=%0.3f",router_start);$fdisplay(wf,"end_ns=%0.3f",router_end);$fdisplay(wf,"inputs=4");$fdisplay(wf,"outputs=4");$fclose(wf);
  wf=$fopen("dma_window.txt","w");$fdisplay(wf,"start_ns=%0.3f",dma_start);$fdisplay(wf,"end_ns=%0.3f",dma_end);$fdisplay(wf,"inputs=35");$fdisplay(wf,"outputs=35");$fclose(wf);
  $display("PASS bank conflict/read/write/backpressure and35 DMA bursts/window/drain");$finish;
 end
endmodule
