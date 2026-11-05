"""Single-scale signed INT8 fixtures, independent integer and grouped-OR oracle."""
from pathlib import Path
import json,random
ROOT=Path(__file__).resolve().parent;N=64;T=32;F=16;SEEDS=(17,503,1009)
NAMES=['zero','positive_limit','negative_limit','cancel','zero_weight','x_endpoints','w_endpoints',
 'shared_half','independent_half','shared_sparse','independent_sparse','shared_random','independent_random',
 'stratified_shared','mixed_sign','random']
CASES=[{'mode':i,'M':1} for i in range(7)]+[{'mode':i,'M':8} for i in (0,2,3,5)]
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def pack(v,w):return sum((x&((1<<w)-1))<<(i*w) for i,x in enumerate(v))
def or_dot(weights,bits):
 total=0
 for start in range(0,N,4):
  pos=neg=0
  for i in range(start,start+4):
   if bits[i]:
    if weights[i]<0:neg|=-weights[i]
    else:pos|=weights[i]
  total+=pos-neg
 return total
def fixtures(m,seed,power=False):
 r=random.Random(seed);data={'w8':[],'x8':[],'samples':[]};expected={i:[] for i in range(7)};metrics=[]
 resident=[r.randrange(-128,128) for _ in range(N*m)]
 for frame in range(F):
  name='resident_uniform_INT8_sharedR8' if power else NAMES[frame]
  w=list(resident) if power else [r.randrange(-128,128) for _ in range(N*m)]
  x=[r.randrange(-128,128) for _ in range(N)]
  if not power:
   if name=='zero':x=[0]*N
   if name=='positive_limit':x=[-128]*N;w=[-128]*(N*m)
   if name=='negative_limit':x=[-128]*N;w=[127]*(N*m)
   if name=='cancel':x=[-128]*N;w=[127 if i%2 else -127 for i in range(N*m)]
   if name=='zero_weight':w=[0]*(N*m)
   if name=='x_endpoints':x=[(-128,-127,-1,0,1,126,127,64)[i%8] for i in range(N)]
   if name=='w_endpoints':w=[(-128,-127,-1,0,1,126,127,64)[i%8] for i in range(N*m)]
   if name in ('shared_half','independent_half'):x=[64]*N;w=[127]*(N*m)
   if name in ('shared_sparse','independent_sparse'):x=[1]*N;w=[127]*(N*m)
   if name=='mixed_sign':x=[(-128,127,-64,64)[i%4] for i in range(N)]
  events=[]
  for t in range(T):
   common=8*t+r.randrange(8) if name=='stratified_shared' else r.randrange(256)
   rr=[r.randrange(256) for _ in range(N)] if name.startswith('independent') else [common]*N
   b=[int(rr[i]<2*abs(x[i])) for i in range(N)];events.append(b);data['samples'].append(pack(b,1))
  exact=[];digital=[];ors=[]
  for j in range(m):
   effective=[w[j*N+i]*(-1 if x[i]<0 else 1) for i in range(N)]
   e=sum(effective[i]*sum(b[i] for b in events) for i in range(N))
   d=sum(w[j*N+i]*x[i] for i in range(N));o=sum(or_dot(effective,b) for b in events)
   assert -(1<<19)<=e<(1<<19);assert -(1<<21)<=d<(1<<21)
   exact.append(e);digital.append(d);ors.append(o)
   metrics.append({'frame':frame,'name':name,'output':j,'event_exact':e,'digital_dot':d,'SC_expected':d/4,
    'OR4':o,'OR_error_same_events':o-e,'SC_error_vs_quantized':e-d/4})
  for mode in range(7):expected[mode].append(pack(ors if mode in (3,6) else digital if mode in (4,5) else exact,32))
  data['w8'].append(pack(w,8));data['x8'].append(pack(x,8))
 out=ROOT/('power_fixtures' if power else 'fixtures')/('m%d_s%d'%(m,seed));out.mkdir(parents=True,exist_ok=True)
 for key,values in data.items():(out/(key+'.hex')).write_text(''.join('%x\n'%x for x in values),encoding='ascii',newline='\n')
 for mode,values in expected.items():(out/('expect%d.hex'%mode)).write_text(''.join('%x\n'%x for x in values),encoding='ascii',newline='\n')
 save(out/'metrics.json',metrics)
BENCH=r'''`timescale 1ns/1ps
module tb;
localparam N=64,M=__M__,T=32,F=16,MODE=__MODE__,STRESS=__STRESS__;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,frame_valid=0,sample_valid=0,out_ready=0;
reg [N*M*8-1:0] w8=0;reg [N*8-1:0] x8=0;reg [N-1:0] sample_bits=0;
wire frame_ready,sample_ready,out_valid;wire [M*32-1:0] out_sum;
__TOP__ dut(.*);
reg [N*M*8-1:0] wm[0:F-1];reg [N*8-1:0] xm[0:F-1];
reg [N-1:0] events[0:F*T-1];reg [M*32-1:0] expected[0:F-1];
integer f,t,c=0,fc,latency;real start_ns,end_ns,idle_start,idle_end;
always @(posedge clk) c=c+1;
initial begin #2000000;$fatal(1,"timeout");end
initial begin
 $dumpfile("activity.vcd");$dumpvars(0,tb);
 $readmemh("w8.hex",wm);$readmemh("x8.hex",xm);$readmemh("samples.hex",events);$readmemh("expect__MODE__.hex",expected);
 repeat(4) @(negedge clk);rst_n=1;frame_valid=1;@(negedge clk);frame_valid=0;
 if(MODE!=4 && MODE!=5) begin sample_valid=1;sample_bits=~64'b0;repeat(4) @(negedge clk);end
 rst_n=0;frame_valid=0;sample_valid=0;repeat(3) @(negedge clk);rst_n=1;
 repeat(2) @(negedge clk);start_ns=$realtime;
 for(f=0;f<F;f=f+1) begin
  while(!frame_ready) @(negedge clk);
  w8=wm[f];x8=xm[f];frame_valid=1;fc=c;@(negedge clk);frame_valid=0;
  if(MODE!=4 && MODE!=5) begin
   for(t=0;t<T;t=t+1) begin
    if(STRESS && t%7==3) begin sample_valid=0;repeat(2) @(negedge clk);end
    while(!sample_ready) @(negedge clk);
    sample_valid=1;sample_bits=events[f*T+t];@(negedge clk);
   end
   sample_valid=0;sample_bits=0;
  end
  while(!out_valid) @(negedge clk);latency=c-fc;
  if(out_sum!==expected[f]) $fatal(1,"mismatch f=%d got=%h expected=%h",f,out_sum,expected[f]);
  if(sample_ready) $fatal(1,"sample_ready while output pending");
  if(STRESS) repeat(3) begin @(negedge clk);if(!out_valid || out_sum!==expected[f]) $fatal(1,"stall unstable");end
  $display("FRAME %0d %0d",f,latency);out_ready=1;@(negedge clk);out_ready=0;
 end
 end_ns=$realtime;idle_start=end_ns+20;repeat(2) @(negedge clk);
 repeat(64) begin @(negedge clk);if(out_valid || !frame_ready) $fatal(1,"idle handshake");end
 idle_end=$realtime;
 $display("WINDOW active %0.3f %0.3f %0d",start_ns,end_ns,F);
 $display("WINDOW idle %0.3f %0.3f 0",idle_start,idle_end);
 $display("FUNCTION_PASS mode=%0d M=%0d frames=%0d stress=%0d",MODE,M,F,STRESS);$finish;
end
endmodule
'''
def main():
 tops=[]
 for m in (1,8):
  for mode in range(7):
   name='ss_s%d_m%d'%(mode,m)
   tops.append('module %s(input wire clk,rst_n,frame_valid,output wire frame_ready,input wire [%d:0] w8,input wire [511:0] x8,input wire [63:0] sample_bits,input wire sample_valid,output wire sample_ready,output wire out_valid,input wire out_ready,output wire [%d:0] out_sum);\nss_matrix #(.M(%d),.MODE(%d)) core(.*);\nendmodule\n'%(name,m*512-1,m*32-1,m,mode))
   for stress in (0,1):
    s=BENCH
    for k,v in {'M':m,'MODE':mode,'STRESS':stress,'TOP':name}.items():s=s.replace('__'+k+'__',str(v))
    p=ROOT/'benches'/('m%d_mode%d_stress%d.sv'%(m,mode,stress));p.parent.mkdir(exist_ok=True);p.write_text(s,encoding='ascii',newline='\n')
  for seed in SEEDS:fixtures(m,seed);fixtures(m,seed,True)
 (ROOT/'rtl/tops.sv').write_text('`timescale 1ns/1ps\n'+''.join(tops),encoding='ascii',newline='\n')
 save(ROOT/'CONFIG.json',{'N':64,'T':32,'BINS':1,'signed_INT8_range':[-128,127],'M':[1,8],'seeds':SEEDS,
  'functional_frames':NAMES,'power_frames':F,'power_activity':'resident weights, uniform INT8 inputs, common R8 across input lanes; source external',
  'SC_probability':'abs(x8)/128','SC_output':'signed event sum; expectation equals digital_dot/4','digital_output':'exact signed INT8 dot product',
  'SC_accumulator_bits':20,'digital_sum_bits':22,'area_multiplier':0.81,'clock_MHz':100,'cases':CASES,'model_quality':'not evaluated'})
 print('SINGLE_SCALE_FIXTURES_READY; 7 modes, M1/M8, three seeds, 16 frames; resident-W power profile')
if __name__=='__main__':main()
