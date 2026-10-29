"""Deterministic synthetic fixtures and integer oracles; no model/PPL claims."""
from pathlib import Path
import hashlib,json,math,random,struct
S=Path(__file__).resolve().parent
CASES=[dict(top='smx_p8_l'+str(l),lanes=l,mode=0) for l in [1,4,16]]+[
 dict(top='smx_'+name+'_l'+str(l),lanes=l,mode=m) for m,name in [(1,'sys'),(2,'bern')] for l in [4,16]]
EXP=[round(32768*math.exp(-i/16)) for i in range(256)]

def save(p,d):p.write_bytes((json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
def mem(p,values,width):p.write_bytes((''.join(format(v,'0%dx'%width)+'\n' for v in values)).encode())
def f32(x):return struct.unpack('<f',struct.pack('<f',x))[0]
def bits(x):return struct.unpack('<I',struct.pack('<f',x))[0]
def bivium(s):
 a=s&((1<<93)-1);b=s>>93;w=0
 for j in range(160):
  t1=((a>>65)^(a>>92))&1;t2=((b>>68)^(b>>83))&1
  w|=(t1^t2)<<j
  fa=t2^(((b>>81)&(b>>82))&1)^((a>>68)&1)
  fb=t1^(((a>>90)&(a>>91))&1)^((b>>77)&1)
  a=((a<<1)|fa)&((1<<93)-1);b=((b<<1)|fb)&((1<<84)-1)
 return w,a|(b<<93)

def oracle(values):
 q=[max(-1024,min(1023,round(v*16))) for v in values]
 clip=any(round(v*16)!=k for v,k in zip(values,q))
 maximum=max(q);w=[EXP[min(maximum-k,255)] for k in q];z=sum(w)
 assert 32768<=z<=4194304
 reciprocal=(1<<32)//z
 prefix=0;cdf=[]
 for x in w:
  prefix+=x;approx=(prefix*reciprocal)>>24
  corrected=approx+int((approx+1)*z<=prefix*256)
  exact=(prefix*256)//z
  assert exact==corrected
  cdf.append(exact)
 out=[v-(cdf[i-1] if i else 0) for i,v in enumerate(cdf)]
 assert sum(out)==256 and min(out)>=0 and max(out)<=256
 return out,clip,q,w

def distributions(seed):
 r=random.Random(seed)
 return [
  ('uniform',[0.0]*128),
  ('singleton',[16.0 if i==seed%128 else -16.0 for i in range(128)]),
  ('gaussian2',[r.gauss(0,2) for _ in range(128)]),
  ('ramp',[(i-63.5)/16 for i in range(128)]),
  ('gaussian6',[r.gauss(0,6) for _ in range(128)]),
  ('four_peaks',[2.0 if i%32==0 else -4.0 for i in range(128)]),
  ('rounding_edges',[[-.03125,.03125,.09375,-.09375,63.96875,-64.,.00001,-.00001][i%8] for i in range(128)]),
  ('saturation',[100.0 if i==0 else (-100.0 if i%2 else 0.0) for i in range(128)])]

def main():
 (S/'fixtures').mkdir(exist_ok=True)
 (S/'exp_function.vh').write_bytes(('function [15:0] exp_lut;\n input [7:0] address;\n begin\n case(address)\n'+''.join("8'd%d: exp_lut=16'd%d;\n"%(i,v) for i,v in enumerate(EXP))+'default: exp_lut=0;\n endcase\n end\nendfunction\n').encode())
 for c in CASES:
  l=c['lanes'];m=c['mode']
  text='''module %s(input wire clk,rst_n,start,load_valid,out_ready,seed_valid,
 input wire [%d:0] score_in,input wire [31:0] seed_data,
 output wire start_ready,load_ready,seed_ready,front_done,out_valid,done,invalid,clipped,
 output wire [6:0] out_index,output wire [%d:0] out_count);
 digital_sampler #(.L(%d),.MODE(%d)) core(.*);
endmodule
'''%(c['top'],32*l-1,9*l-1,l,m)
  (S/(c['top']+'.sv')).write_bytes(text.encode())
 audits=[]
 for seed in [17,503,1009]:
  r=random.Random(seed+198000);states=[r.getrandbits(177) or 1 for _ in range(7)]
  seedwords=[]
  for s in states:seedwords.extend((s>>(32*k))&0xffffffff for k in range(5,-1,-1))
  mem(S/'fixtures'/('seed%d.mem'%seed),seedwords,8)
  warm=states[:]
  for _ in range(5):warm=[bivium(s)[1] for s in warm]
  sysstate=warm[0];bernstate=warm[:]
  scores=[];outputs=[[],[],[]];flags=[]
  for name,values in distributions(seed):
   values=[f32(v) for v in values];q,clip,qs,weights=oracle(values)
   scores.extend(bits(x) for x in values);flags.append(int(clip));outputs[0].extend(q)
   word,sysstate=bivium(sysstate);phase=word&255;ns=[]
   for x in q:
    phase+=128*x;ns.append(phase>>8);phase&=255
   assert sum(ns)==128
   outputs[1].extend(ns)
   nb=[0]*128
   for _ in range(128):
    draws=[]
    for g in range(7):
     word,bernstate[g]=bivium(bernstate[g]);draws.extend((word>>(8*j))&255 for j in range(20))
    for i in range(128):nb[i]+=int(draws[i]<q[i])
   outputs[2].extend(nb)
   m=max(values);p=[math.exp(v-m) for v in values];z=sum(p);p=[x/z for x in p]
   rne=[min(256,max(0,round(256*x))) for x in p]
   audits.append(dict(seed=seed,name=name,clip=clip,probability_mass=sum(q),bernoulli_total_hits=sum(nb),
      tv_fp32_to_conserved_p8=.5*sum(abs(q[i]/256-p[i]) for i in range(128)),
      tv_exp_fixed_only=.5*sum(abs(weights[i]/sum(weights)-p[i]) for i in range(128)),
      zeroed_reference_mass=sum(p[i] for i in range(128) if q[i]==0),rne_mass=sum(rne),
      l1_rne_unrenormalized=sum(abs(rne[i]/256-p[i]) for i in range(128)),
      higher_precision_conserved_tv={str(b):.5*sum(abs(((sum(weights[:i+1])*(1<<b))//sum(weights)-(sum(weights[:i])*(1<<b))//sum(weights))/(1<<b)-p[i]) for i in range(128)) for b in [12,16]}))
  mem(S/'fixtures'/('score%d.mem'%seed),scores,8);mem(S/'fixtures'/('flags%d.mem'%seed),flags,1)
  for mode,values in enumerate(outputs):mem(S/'fixtures'/('expect_m%d_s%d.mem'%(mode,seed)),values,3)
 save(S/'CASES.json',CASES);save(S/'NUMERICAL_AUDIT.json',dict(rows=audits,scope='24 synthetic score rows; not model accuracy or PPL',q_rule='floor differences of exact integer exp-weight CDF at256 mass units',rng='7 compact Bivium maps; continuous states across8queries;5x160 warm bits; not IID certification'))
 print(json.dumps(dict(tops=len(CASES),synthetic_rows=len(audits),max_tv=max(x['tv_fp32_to_conserved_p8'] for x in audits))))
if __name__=='__main__':main()
