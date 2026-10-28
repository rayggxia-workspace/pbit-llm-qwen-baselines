"""Deterministic microbenchmark fixtures; independent Python integer oracles."""
from pathlib import Path
import hashlib,json,math,random,shutil
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1];OLD=REPO/'architecture_tlm/matrix_single_scale_20261028'
SEEDS=(17,503,1009);T=32;N=64
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def unpack(v,n,b,signed=False):
 a=[(int(v,16)>>(i*b))&((1<<b)-1) for i in range(n)]
 return [x-(1<<b) if signed and x>=(1<<(b-1)) else x for x in a]
def pack(a,widths):
 v=0;offset=0
 for x,b in zip(a,widths):v|=(int(x)&((1<<b)-1))<<offset;offset+=b
 return v
def sat(v,b):return min((1<<(b-1))-1,max(-(1<<(b-1)),v))
def ow_for(widths,first):
 lo=-sum((1<<(b-1))*(1<<(first+i)) for i,b in enumerate(widths))
 hi=sum(((1<<(b-1))-1)*(1<<(first+i)) for i,b in enumerate(widths));w=1
 while lo<-(1<<(w-1)) or hi>(1<<(w-1))-1:w+=1
 return w
def cases():
 out=[]
 def add(name,family,iw,ow,**k):out.append(dict(id=len(out),name=name,family=family,IW=iw,OW=ow,**k))
 for n in (8,16,32,64):
  for drop in ((0,1,2) if n==16 else (0,1)):
   add('pop%d_d%d'%(n,drop),'pop',n,n.bit_length()-drop,N=n,DROP=drop)
 add('popdiff16','diff',32,6,N=16)
 add('maskor64','mask',192,32,N=64)
 for widths,first in [([8]*4,0),([7]*6,1),([8]*6,1),([9]*6,1),([11]*6,1),([9]*7,0),([11]*7,0),([11]*8,0),([7,8,8,9,9,9],1)]:
  name='shift_'+str(first)+'_'+'_'.join(map(str,widths));add(name,'shift',sum(widths),ow_for(widths,first),widths=widths,FIRST=first)
 for b in (7,8,9,10,11):add('acc%d'%b,'acc',6,b,B=b)
 for b in (9,11):add('plane64_b%d'%b,'plane',192,b,N=64,B=b)
 for widths,first,label in [([11]*7,0,'77'),([9]*6,1,'54'),([7,8,8,9,9,9],1,'50')]:
  add('bank'+label,'bank',64+448+64,ow_for(widths,first),widths=widths,FIRST=first)
 for w in (16,20,24):add('align%d'%w,'align',2*w+3,w+1,W=w)
 return out
RTL=r'''`timescale 1ns/1ps
module me_pop #(parameter N=16,W=$clog2(N)+1)(input wire [N-1:0] bits,output wire [W-1:0] count);
genvar l,k;generate for(l=0;l<$clog2(N);l=l+1) begin:level
 wire [l+1:0] v[0:(N>>(l+1))-1];
 for(k=0;k<(N>>(l+1));k=k+1) begin:node
  if(l==0) assign v[k]={1'b0,bits[2*k]}+{1'b0,bits[2*k+1]};
  else assign v[k]={1'b0,level[l-1].v[2*k]}+{1'b0,level[l-1].v[2*k+1]};
 end
end endgenerate
assign count=level[$clog2(N)-1].v[0];endmodule
module me_diff #(parameter N=16,W=$clog2(N)+1)(input wire [2*N-1:0] bits,output wire signed [W:0] delta);
wire [W-1:0] p,n;me_pop #(.N(N)) pt(bits[N-1:0],p),nt(bits[2*N-1:N],n);
assign delta=$signed({1'b0,p})-$signed({1'b0,n});endmodule
module me_mask #(parameter N=64)(input wire [3*N-1:0] din,output wire [N/2-1:0] grouped);
wire [N-1:0] pos,neg;genvar i,g;generate
for(i=0;i<N;i=i+1) begin:lane
 assign pos[i]=din[i]&din[N+i]&!din[2*N+i];
 assign neg[i]=din[i]&din[N+i]&din[2*N+i];
end
for(g=0;g<N/4;g=g+1) begin:or4
 assign grouped[g]=|pos[4*g+:4];assign grouped[N/4+g]=|neg[4*g+:4];
end endgenerate endmodule
module me_acc #(parameter B=9,D=6,R=((B>D)?B:D)+1)(input wire clk,rst_n,clear,en,input wire signed [D-1:0] delta,output reg signed [B-1:0] value);
localparam signed [R-1:0] HI=(1<<(B-1))-1,LO=-(1<<(B-1));
wire signed [R-1:0] a={{(R-B){value[B-1]}},value},b={{(R-D){delta[D-1]}},delta};
wire signed [R-1:0] sum=a+b;
always @(posedge clk) begin
 if(!rst_n || clear) value<=0;
 else if(en) begin if(sum>HI) value<=HI[B-1:0];else if(sum<LO) value<=LO[B-1:0];else value<=sum[B-1:0];end
end endmodule
module me_plane #(parameter B=9)(input wire clk,rst_n,clear,en,input wire [191:0] din,output wire signed [B-1:0] value);
wire [31:0] grouped;wire signed [5:0] delta;me_mask mask(din,grouped);me_diff diff(grouped,delta);me_acc #(.B(B)) acc(clk,rst_n,clear,en,delta,value);endmodule
module me_sum #(parameter N=8,LW=16,TW=LW+$clog2(N))(input wire [N*LW-1:0] leaves,output wire signed [TW-1:0] total);
genvar l,k;generate for(l=0;l<$clog2(N);l=l+1) begin:level
 wire signed [LW+l:0] v[0:(N>>(l+1))-1];
 for(k=0;k<(N>>(l+1));k=k+1) begin:node
  wire signed [LW+l-1:0] a,b;
  if(l==0) begin assign a=leaves[2*k*LW+:LW];assign b=leaves[(2*k+1)*LW+:LW];end
  else begin assign a=level[l-1].v[2*k];assign b=level[l-1].v[2*k+1];end
  assign v[k]=$signed({a[LW+l-1],a})+$signed({b[LW+l-1],b});
 end
end endgenerate assign total=level[$clog2(N)-1].v[0];endmodule
'''
def shift_logic(widths,first,ow,source='din'):
 s=[];padded=1<<(len(widths)-1).bit_length();offset=0
 s.append('wire [%d:0] leaves;wire signed [%d:0] total;'%(padded*ow-1,ow+int(math.log2(padded))-1))
 for i,b in enumerate(widths):
  s.append('wire signed [%d:0] c%d=$signed(%s[%d+:%d]);assign leaves[%d+:%d]=c%d <<< %d;'%(ow-1,i,source,offset,b,i*ow,ow,i,first+i));offset+=b
 for i in range(len(widths),padded):s.append('assign leaves[%d+:%d]=0;'%(i*ow,ow))
 s.append('me_sum #(.N(%d),.LW(%d)) tree(leaves,total);'% (padded,ow))
 return '\n'.join(s)
def top(c):
 f=c['family'];s='module me_%s(input wire clk,rst_n,clear,en,input wire [%d:0] din,output wire [%d:0] dout);\n'%(c['name'],c['IW']-1,c['OW']-1)
 if f=='pop':s+='wire [%d:0] count;me_pop #(.N(%d)) pc(din,count);assign dout=count >> %d;\n'%(c['N'].bit_length()-1,c['N'],c['DROP'])
 elif f=='diff':s+='me_diff #(.N(%d)) diff(din,dout);\n'%c['N']
 elif f=='mask':s+='me_mask mask(din,dout);\n'
 elif f=='acc':s+='me_acc #(.B(%d)) acc(clk,rst_n,clear,en,$signed(din),dout);\n'%c['B']
 elif f=='plane':s+='me_plane #(.B(%d)) plane(clk,rst_n,clear,en,din,dout);\n'%c['B']
 elif f=='shift':s+=shift_logic(c['widths'],c['FIRST'],c['OW'])+'\nassign dout=total;\n'
 elif f=='align':
  w=c['W'];s+='wire signed [%d:0] a=din[0+:%d],b=din[%d+:%d];wire signed [%d:0] moved=b >>> din[%d+:3];assign dout=$signed({a[%d],a})+$signed({moved[%d],moved});\n'%(w-1,w,w,w,w-1,2*w,w-1,w-1)
 elif f=='bank':
  widths=c['widths'];s+='reg [1:0] state;reg [4:0] samples;reg signed [%d:0] result;wire accept=en&&(state==1);assign dout=result;\n'%(c['OW']-1)
  s+='wire [%d:0] counters,isolated;assign isolated=(state==2)?counters:0;\n'%(sum(widths)-1)
  offset=0
  for j,b in enumerate(widths):
   p=c['FIRST']+j;s+='wire [191:0] sel%d;assign sel%d[63:0]=din[63:0];assign sel%d[191:128]=din[575:512];\n'%(j,j,j)
   for i in range(64):s+='assign sel%d[%d]=din[%d];\n'%(j,64+i,64+7*i+p)
   s+='me_plane #(.B(%d)) plane%d(clk,rst_n,clear,accept,sel%d,counters[%d+:%d]);\n'%(b,j,j,offset,b);offset+=b
  s+=shift_logic(widths,c['FIRST'],c['OW'],'isolated')+'\n'
  s+='always @(posedge clk) begin if(!rst_n) begin state<=0;samples<=0;result<=0;end else begin if(clear) begin state<=1;samples<=0;end else begin if(accept) begin if(samples==31) state<=2;else samples<=samples+1\'b1;end if(state==2) begin result<=total;state<=3;end if(state==3) state<=0;end end end\n'
 return s+'endmodule\n'
BENCH=r'''`timescale 1ns/1ps
module tb;
localparam IW=__IW__,OW=__OW__,L=__L__;
reg clk=0;always #5 clk=~clk;reg rst_n=0,clear=0,en=0;reg [IW-1:0] din=0;wire [OW-1:0] dout;
me___NAME__ dut(.*);
reg [IW+1:0] stim[0:L-1];reg [OW-1:0] expected[0:L-1];integer i;
initial begin $dumpfile("activity.vcd");$dumpvars(0,tb);$readmemh("stim.hex",stim);$readmemh("expect.hex",expected);
 repeat(4) @(negedge clk);rst_n=1;
 for(i=0;i<L;i=i+1) begin @(negedge clk);{clear,en,din}=stim[i];@(posedge clk);#1;if(dout!==expected[i]) $fatal(1,"Mismatch index=%0d got=%h expected=%h",i,dout,expected[i]);end
 @(negedge clk);$display("FUNCTION_PASS transactions=%0d",L);$finish;end
initial begin #1000000;$fatal(1,"Timeout");end
endmodule
'''
def inputs(seed):
 p=OLD/'power_fixtures'/('m8_s%d'%seed)
 ws=[unpack(x,512,8,True) for x in (p/'w8.hex').read_text().splitlines()];xs=[unpack(x,64,8,True) for x in (p/'x8.hex').read_text().splitlines()]
 ev=[int(x,16) for x in (p/'samples.hex').read_text().splitlines()]
 return ws,xs,ev
def mask_vector(ws,xs,ev,f,t,plane):
 row=f%8;weights=ws[f][row*64:(row+1)*64];neg=[int((w<0)^(x<0)) for w,x in zip(weights,xs[f])]
 mask=[(abs(w)>>plane)&1 for w in weights];return ev[f*32+t]|(pack(mask,[1]*64)<<64)|(pack(neg,[1]*64)<<128)
def mask_or(v):
 event=v&((1<<64)-1);mask=(v>>64)&((1<<64)-1);neg=v>>128;pos=event&mask&~neg;negative=event&mask&neg
 return sum(int(bool((pos>>(4*g))&15))<<g for g in range(16)) | sum(int(bool((negative>>(4*g))&15))<<(16+g) for g in range(16))
def popdiff(v,n=16):return (v&((1<<n)-1)).bit_count()-(v>>n).bit_count()
def fixture(c,seed):
 r=random.Random(seed*1000+c['id']);ws,xs,events=inputs(seed);rows=[];windows=[];state=0;count=0;result=0;cs=[0]*len(c.get('widths',[]));acc=0
 def oracle(v,clear,en):
  nonlocal state,count,result,cs,acc
  f=c['family']
  if f=='pop':return v.bit_count()>>c['DROP']
  if f=='diff':return popdiff(v,c['N'])
  if f=='mask':return mask_or(v)
  if f=='align':
   w=c['W'];a,b=unpack(hex(v)[2:],2,w,True);return a+(b>>(v>>(2*w)))
  if f=='shift':return sum(a*(1<<(c['FIRST']+i)) for i,a in enumerate(unpack_mixed(v,c['widths'])))
  if f in ('acc','plane'):
   delta=unpack(hex(v)[2:],1,6,True)[0] if f=='acc' else popdiff(mask_or(v))
   if clear:acc=0
   elif en:acc=sat(acc+delta,c['B'])
   return acc
  oldstate=state
  if clear:state=1;count=0;cs=[0]*len(cs)
  else:
   if state==1 and en:
    b=v&((1<<64)-1);mags=unpack(hex(v>>64)[2:],64,7);neg=(v>>512)&((1<<64)-1)
    for j,width in enumerate(c['widths']):
     p=c['FIRST']+j;mv=b|(sum(((a>>p)&1)<<i for i,a in enumerate(mags))<<64)|(neg<<128);cs[j]=sat(cs[j]+popdiff(mask_or(mv)),width)
    if count==31:state=2
    else:count+=1
   if oldstate==2:result=sum(v*(1<<(c['FIRST']+i)) for i,v in enumerate(cs));state=3
   if oldstate==3:state=0
  return result
 def add(v=0,clear=0,en=1):rows.append((v|(en<<c['IW'])|(clear<<(c['IW']+1)),oracle(v,clear,en)&((1<<c['OW'])-1)))
 for profile in ('sparse','dense','replay','idle'):
  add(0,clear=1,en=0);start=len(rows);f=c['family']
  if profile=='idle':
   for _ in range(64):add(0,en=0)
   operations=0
  elif f in ('acc','plane','bank'):
   for frame in range(16):
    add(0,clear=1,en=0)
    for t in range(32):
     if profile=='replay':mv=mask_vector(ws,xs,events,frame,t,1+frame%6)
     else:
      event=pack([int(r.random()<(.05 if profile=='sparse' else .5)) for _ in range(64)],[1]*64)
      mv=event|(r.getrandbits(64)<<64)|(r.getrandbits(64)<<128)
     if f=='acc':v=popdiff(mask_or(mv))&63
     elif f=='plane':v=mv
     else:
      weights=ws[frame][(frame%8)*64:(frame%8+1)*64];mags=[min(127,abs(w)) for w in weights];neg=[int((w<0)^(x<0)) for w,x in zip(weights,xs[frame])]
      if profile!='replay':mags=[r.randrange(128) for _ in range(64)];neg=[r.randrange(2) for _ in range(64)]
      v=(events[frame*32+t] if profile=='replay' else mv&((1<<64)-1))|(pack(mags,[7]*64)<<64)|(pack(neg,[1]*64)<<512)
     add(v)
    if f=='bank':add(0,en=0);add(0,en=0)
   operations=16
  elif f=='shift' and profile=='replay':
   for frame in range(16):
    vals=[0]*len(c['widths'])
    for t in range(32):
     for j,width in enumerate(c['widths']):vals[j]=sat(vals[j]+popdiff(mask_or(mask_vector(ws,xs,events,frame,t,c['FIRST']+j))),width)
    for _ in range(33):add(0,en=0)
    add(pack(vals,c['widths']));add(0,en=0)
   operations=16
  else:
   for i in range(512):
    if profile=='replay' and f in ('mask','diff','pop'):
     mv=mask_vector(ws,xs,events,i//32,i%32,1+(i//32)%6)
     v=mv if f=='mask' else mask_or(mv)
     if f=='pop':v=(v&((1<<16)-1)) if c['N']==16 else pack([int(r.random()<.35) for _ in range(c['N'])],[1]*c['N'])
    elif f=='shift':
     vals=[r.randint(-(1<<(b-1)),(1<<(b-1))-1) if profile=='dense' else (r.randint(-3,3) if r.random()<.05 else 0) for b in c['widths']];v=pack(vals,c['widths'])
    elif f=='align':v=r.getrandbits(c['IW']) if profile!='sparse' else pack([r.randint(-3,3),r.randint(-3,3),r.randrange(8)],[c['W'],c['W'],3])
    else:v=pack([int(r.random()<(.05 if profile=='sparse' else .5)) for _ in range(c['IW'])],[1]*c['IW'])
    add(v)
   operations=512
  windows.append({'mode':profile,'start_ns':50+10*start,'end_ns':50+10*len(rows),'operations':operations})
 folder=ROOT/'fixtures'/c['name']/str(seed);folder.mkdir(parents=True,exist_ok=True)
 for name,index in [('stim',0),('expect',1)]: (folder/(name+'.hex')).write_text(''.join('%x\n'%x[index] for x in rows),encoding='ascii',newline='\n')
 save(folder/'WINDOWS.json',{'transactions':len(rows),'windows':windows})
 return len(rows)
def unpack_mixed(v,widths):
 a=[]
 for b in widths:
  x=v&((1<<b)-1);a.append(x-(1<<b) if x>=(1<<(b-1)) else x);v>>=b
 return a
def main():
 cs=cases();(ROOT/'rtl').mkdir(exist_ok=True);(ROOT/'benches').mkdir(exist_ok=True)
 (ROOT/'rtl/primitives.sv').write_text(RTL,encoding='ascii',newline='\n');(ROOT/'rtl/tops.sv').write_text('`timescale 1ns/1ps\n'+''.join(top(c) for c in cs),encoding='ascii',newline='\n')
 for c in cs:
  counts=[fixture(c,seed) for seed in SEEDS];assert len(set(counts))==1
  s=BENCH
  for k,v in dict(IW=c['IW'],OW=c['OW'],L=counts[0],NAME=c['name']).items():s=s.replace('__'+k+'__',str(v))
  (ROOT/'benches'/(c['name']+'.sv')).write_text(s,encoding='ascii',newline='\n')
 save(ROOT/'CASES.json',cs)
 save(ROOT/'INPUT_REFERENCE.json',{'source_commit':'5dcef4fd99200418f804cbd51f3bf325d1cbea60','files':{p.relative_to(REPO).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (OLD/'power_fixtures').glob('m8_*/*.hex') if p.name in ('w8.hex','x8.hex','samples.hex')},
  'replay':'M8 uniform resident W/commonR8 synthetic traces; single-plane primitive replay rotates planes1..6. Bank uses7-bit magnitude=min(127,abs(W)); this explicit contract differs from completeINT8. Not a real model trace.'})
 print('MODULE_FIXTURES_READY',len(cs),'cases')
if __name__=='__main__':main()
