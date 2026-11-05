"""Generate synthetic, independently scored fixtures; no model-quality claims."""
from pathlib import Path
import hashlib,json,random
ROOT=Path(__file__).resolve().parent
SEEDS=(17,503,1009)
N=64;T=32
NAMES=['zero','positive_max','negative_max','cancel','ones','mixed_bins',
       'invalid_bin','shared_half','independent_half','iid_shared',
       'iid_independent','stratified_shared','endpoints','small_weights','random']
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def pack(v,w):return sum((x&((1<<w)-1))<<(i*w) for i,x in enumerate(v))
def fixture(m,seed):
 r=random.Random(seed);data={k:[] for k in ('wmag','wsign','xsign','bins','q9','samples')}
 expected={k:[] for k in range(6)};metrics=[]
 for f,name in enumerate(NAMES):
  mag=[r.randrange(128) for _ in range(N*m)];ws=[r.randrange(2) for _ in mag]
  xs=[r.randrange(2) for _ in range(N)];bs=[r.randrange(4) for _ in range(N)];q=[r.randrange(257) for _ in range(N)]
  if name in ('positive_max','negative_max','cancel','ones','shared_half','independent_half'):
   mag=[127]*(N*m);xs=[0]*N;bs=[0]*N;ws=[0]*(N*m)
   if name=='negative_max':ws=[1]*(N*m)
   if name=='cancel':ws=[i%2 for i in range(N*m)]
  if name=='zero':q=[0]*N
  if name in ('positive_max','negative_max','cancel','ones'):q=[256]*N
  if name in ('shared_half','independent_half'):q=[128]*N
  if name=='mixed_bins':bs=[i%4 for i in range(N)]
  if name=='invalid_bin':bs=[4+i%4 for i in range(N)];q=[256]*N
  if name=='endpoints':q=[(0,1,255,256)[i%4] for i in range(N)]
  if name=='small_weights':mag=[(0,1,127)[i%3] for i in range(N*m)]
  ev=[]
  for t in range(T):
   common=8*t+r.randrange(8) if name=='stratified_shared' else r.randrange(256)
   rr=[r.randrange(256) for _ in range(N)] if name in ('independent_half','iid_independent') else [common]*N
   bits=[int(rr[i]<q[i]) for i in range(N)];ev.append(bits);data['samples'].append(pack(bits,1))
  exact=[];digital=[];or4=[]
  for j in range(m):
   weights=[((-1)**(ws[j*N+i]^xs[i]))*mag[j*N+i]*(4**(3-bs[i])) if bs[i]<4 else 0 for i in range(N)]
   exact.append(sum(weights[i]*ev[t][i] for t in range(T) for i in range(N)))
   digital.append(sum(weights[i]*q[i] for i in range(N)))
   total=0
   # Independent OR oracle: build sets of active signed powers of two per group.
   for bits in ev:
    for g in range(N//4):
     pos=set();neg=set()
     for i in range(g*4,g*4+4):
      if not bits[i]:continue
      w=weights[i];a=abs(w);target=pos if w>=0 else neg
      power=1
      while a:
       if a&1:target.add(power)
       a>>=1;power<<=1
     total+=sum(pos)-sum(neg)
   or4.append(total)
   metrics.append({'frame':name,'output':j,'same_event_exact':exact[-1],'or4':total,
       'quantized_target_T32':digital[-1]/8.0,'or4_error_same_event':total-exact[-1],
       'event_error_quantized':exact[-1]-digital[-1]/8.0})
  for mode in range(6):expected[mode].append(pack(or4 if mode==3 else digital if mode>=4 else exact,32))
  for key,values,w in [('wmag',mag,7),('wsign',ws,1),('xsign',xs,1),('bins',bs,3),('q9',q,9)]:data[key].append(pack(values,w))
 out=ROOT/'fixtures'/('m%d_s%d'%(m,seed));out.mkdir(parents=True,exist_ok=True)
 for key,values in data.items():
  (out/(key+'.hex')).write_text(''.join('%x\n'%x for x in values),encoding='ascii',newline='\n')
 for mode,values in expected.items():
  (out/('expect%d.hex'%mode)).write_text(''.join('%x\n'%x for x in values),encoding='ascii',newline='\n')
 save(out/'metrics.json',metrics)
 return out

BENCH=r'''`timescale 1ns/1ps
module tb;
localparam N=64,M=__M__,T=32,F=__F__,MODE=__MODE__,STRESS=__STRESS__;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,frame_valid=0,sample_valid=0,out_ready=0;
reg [N*M*7-1:0] w_mag7=0;reg [N*M-1:0] w_sign=0;
reg [N-1:0] x_sign=0,sample_bits=0;reg [N*3-1:0] bin_id=0;reg [N*9-1:0] q9=0;
wire frame_ready,sample_ready,out_valid;wire [M*32-1:0] out_sum;
__TOP__ dut(.*);
reg [N*M*7-1:0] wm[0:F-1];reg [N*M-1:0] ws[0:F-1];reg [N-1:0] xs[0:F-1];
reg [N*3-1:0] bs[0:F-1];reg [N*9-1:0] qs[0:F-1];reg [N-1:0] events[0:F*T-1];
reg [M*32-1:0] expected[0:F-1];
integer f,t,c=0,fc,latency;real start_ns,end_ns,idle_start,idle_end;
always @(posedge clk) c=c+1;
initial begin #2000000; $fatal(1,"timeout");end
initial begin
 $dumpfile("activity.vcd");$dumpvars(0,tb);
 $readmemh("wmag.hex",wm);$readmemh("wsign.hex",ws);$readmemh("xsign.hex",xs);
 $readmemh("bins.hex",bs);$readmemh("q9.hex",qs);$readmemh("samples.hex",events);
 $readmemh("expect__MODE__.hex",expected);
 repeat(4) @(negedge clk);rst_n=1;
 // Abort an in-flight frame and reset. A fresh frame must not retain data.
 frame_valid=1;@(negedge clk);frame_valid=0;
 if(MODE<4) begin sample_valid=1;sample_bits=~64'b0;repeat(4) @(negedge clk);end
 rst_n=0;frame_valid=0;sample_valid=0;repeat(3) @(negedge clk);rst_n=1;
 repeat(2) @(negedge clk);start_ns=$realtime;
 for(f=0;f<F;f=f+1) begin
  while(!frame_ready) @(negedge clk);
  w_mag7=wm[f];w_sign=ws[f];x_sign=xs[f];bin_id=bs[f];q9=qs[f];
  frame_valid=1;fc=c;@(negedge clk);frame_valid=0;
  if(MODE<4) begin
   for(t=0;t<T;t=t+1) begin
    if(STRESS && (t%7==3)) begin sample_valid=0;repeat(2) @(negedge clk);end
    while(!sample_ready) @(negedge clk);
    sample_valid=1;sample_bits=events[f*T+t];@(negedge clk);
   end
   sample_valid=0;sample_bits=0;
  end
  while(!out_valid) @(negedge clk);
  latency=c-fc;
  if(out_sum!==expected[f]) $fatal(1,"mismatch frame=%d got=%h expected=%h",f,out_sum,expected[f]);
  if(sample_ready) $fatal(1,"sample_ready while output pending");
  if(STRESS) repeat(3) begin
   @(negedge clk);if(!out_valid || out_sum!==expected[f]) $fatal(1,"stall stability");
  end
  $display("FRAME %0d %0d",f,latency);
  out_ready=1;@(negedge clk);out_ready=0;
 end
 end_ns=$realtime;idle_start=end_ns+20;
 repeat(2) @(negedge clk);
 repeat(64) begin @(negedge clk);if(out_valid || !frame_ready) $fatal(1,"idle handshake");end
 idle_end=$realtime;
 $display("WINDOW active %0.3f %0.3f %0d",start_ns,end_ns,F);
 $display("WINDOW idle %0.3f %0.3f 0",idle_start,idle_end);
 $display("FUNCTION_PASS mode=%0d M=%0d frames=%0d stress=%0d",MODE,M,F,STRESS);
 $finish;
end
endmodule
'''
def main():
 (ROOT/'rtl').mkdir(exist_ok=True)
 top=[]
 ports='''input wire clk,rst_n,frame_valid,output wire frame_ready,
 input wire [M*448-1:0] w_mag7,input wire [M*64-1:0] w_sign,
 input wire [63:0] x_sign,input wire [191:0] bin_id,input wire [575:0] q9,
 input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,
 output wire out_valid,input wire out_ready,output wire [M*32-1:0] out_sum'''
 for m in (1,8):
  for mode in range(6):
   name='matrix_s%d_m%d'%(mode,m)
   head='module %s(%s);\n'%(name,ports.replace('M*',str(m)+'*'))
   if mode==0:
    body='''wire [M*25-1:0] sums;
 sc_counter_merged #(.M(M),.T(32),.BINS(4),.PIPE_EVERY(2),.GATE_MODE(0),.AW(25)) core(
 .clk(clk),.rst_n(rst_n),.test_en(1'b0),.frame_valid(frame_valid),.frame_ready(frame_ready),
 .w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),.bin_id(bin_id),
 .sample_bits(sample_bits),.sample_valid(sample_valid),.sample_ready(sample_ready),
 .out_valid(out_valid),.out_ready(out_ready),.out_sum(sums));
 genvar j;generate for(j=0;j<M;j=j+1) begin:extend
  assign out_sum[j*32+:32]={{7{sums[j*25+24]}},sums[j*25+:25]};
 end endgenerate
'''.replace('.M(M)','.M(%d)'%m).replace('M*','%d*'%m).replace('j<M','j<%d'%m)
   else:body='matrix_variant #(.M(%d),.MODE(%d)) core(.*);\n'%(m,mode)
   top.append(head+body+'endmodule\n')
 (ROOT/'rtl/tops.sv').write_text('`timescale 1ns/1ps\n'+''.join(top),encoding='ascii',newline='\n')
 for m in (1,8):
  for seed in SEEDS:
   fixture(m,seed)
  for mode in range(6):
   for stress in (0,1):
    s=BENCH
    for k,v in {'M':m,'MODE':mode,'F':len(NAMES),'STRESS':stress,'TOP':'matrix_s%d_m%d'%(mode,m)}.items():s=s.replace('__'+k+'__',str(v))
    p=ROOT/'benches'/('m%d_mode%d_stress%d.sv'%(m,mode,stress));p.parent.mkdir(exist_ok=True);p.write_text(s,encoding='ascii',newline='\n')
 save(ROOT/'CONFIG.json',{'N':64,'T':32,'BINS':4,'M':[1,8],'seeds':SEEDS,'frames':NAMES,
     'SC_out':'raw signed event sum','digital_out':'q9 numerator with denominator256; T32 target is raw/8',
     'static_configuration':'must remain stable frame_valid&&frame_ready through out_valid&&out_ready',
     'area_multiplier':0.81,'clock_MHz':100,'model_quality':'not evaluated'})
 print('FIXTURES_READY',len(NAMES)*2*3,'frames per variant; independent OR oracle')
if __name__=='__main__':main()
