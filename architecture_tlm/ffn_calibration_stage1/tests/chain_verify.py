# Independent whole-chain oracle: Python arbitrary-width integer math.
import json, random, re
from pathlib import Path

def rne(num, shift):
    sign=-1 if num<0 else 1
    a=abs(num)
    q,r=divmod(a,1<<shift)
    if shift and (r>(1<<(shift-1)) or (r==(1<<(shift-1)) and q&1)): q+=1
    return sign*q

def packed(values,width):
    return sum((int(v)&((1<<width)-1))<<(i*width) for i,v in enumerate(values))

def generate(output, *, bins, t, seed=193):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    rng=random.Random(seed); frames=[]; state=0
    for f in range(8):
        weights=[127 if f<2 else rng.randrange(128) for _ in range(64)]
        ws=[int(f==1) if f<2 else rng.randrange(2) for _ in range(64)]
        xs=[0 if f<2 else rng.randrange(2) for _ in range(64)]
        ids=[i%bins for i in range(64)]
        streams=[(2**64-1 if f<2 else rng.getrandbits(64)) for _ in range(t)]
        if f==6: streams=[0]*t
        coeff=[1,65535,301,0,32767,65535,123,3][f]
        shift=[0,13,8,7,12,0,63,1][f]; clear=int(f in (0,4))
        counts=[0]*bins
        for s in streams:
            for i in range(64):
                if (s>>i)&1: counts[ids[i]]+=weights[i]*(-1 if ws[i]^xs[i] else 1)
        value=sum(c*2**(2*(bins-1-b)) for b,c in enumerate(counts))
        delta=rne(value*coeff,shift)
        new=delta if clear else state+delta
        ov=int(new>2**63-1 or new<-(2**63)); state=max(-(2**63),min(2**63-1,new))
        frames.append(dict(weights=weights,w_sign=ws,x_sign=xs,bins=ids,streams=streams,coeff=coeff,rshift=shift,clear=clear,counts=counts,delta=delta,sum=state,overflow=ov))
    (output/'oracle.json').write_text(json.dumps(dict(seed=seed,frames=frames),indent=2)+'\n',encoding='utf-8')
    code=['''`timescale 1ns/1ps
module tb;
reg clk=0; always #5 clk=~clk;
reg rst_n=0,frame_valid=0,sample_valid=0,out_ready=0,frame_clear=0;
wire frame_ready,sample_ready,out_valid,ov,sticky;
reg [447:0] w_mag7=0;reg [63:0] w_sign=0,x_sign=0,sample_bits=0;
reg [191:0] bin_id=0;reg [15:0] coeff=0;reg [5:0] rshift=0;
wire signed [63:0] out_sum;
integer cycle=0,outputs=0,accepted=0,started=0,stalls=0;
reg held=0;reg [63:0] held_value;
''',f'ffn_chain #(.BINS({bins}),.T({t})) dut(.*,.out_overflow(ov),.out_sticky(sticky));\n', '''always @(posedge clk) begin
 cycle=cycle+1;
 if(rst_n) begin
  if(frame_valid && frame_ready) begin started=started+1; $display("START %0d %0d",started,cycle); end
  if(sample_valid && sample_ready) accepted=accepted+1;
  if(held && (!out_valid || out_sum!==held_value)) $fatal(1,"blocked output changed");
  held=out_valid&&!out_ready; held_value=out_sum;
  if(held) stalls=stalls+1;
  if(out_valid&&out_ready) begin
   outputs=outputs+1;$display("OUTPUT %0d %0d %016h %0d %0d",outputs,cycle,out_sum,ov,sticky);
  end
 end else held=0;
end
initial begin
 repeat(3) @(negedge clk); rst_n=1;
''']
    for f,fr in enumerate(frames):
        code += ['out_ready='+str(int(f in (0,4)))+';\n']
        code += [f'@(negedge clk); while(!frame_ready) @(negedge clk);\nw_mag7=448\'h{packed(fr["weights"],7):x}; w_sign=64\'h{packed(fr["w_sign"],1):x}; x_sign=64\'h{packed(fr["x_sign"],1):x}; bin_id=192\'h{packed(fr["bins"],3):x}; coeff=16\'d{fr["coeff"]}; rshift=6\'d{fr["rshift"]}; frame_clear=1\'b{fr["clear"]}; frame_valid=1;\n@(negedge clk); frame_valid=0; coeff=57005; rshift=61; frame_clear=~frame_clear;\n']
        for j,s in enumerate(fr['streams']):
            if f%2 and j%11==0: code += ['sample_valid=0; @(negedge clk);\n']
            code += [f"sample_bits=64'h{s:x}; sample_valid=1; while(!sample_ready) @(negedge clk); @(negedge clk);\n"]
        code += [f'sample_valid=0; $display("LAST {f+1} %0d",cycle);\n']
        code += ['wait(out_valid); @(negedge clk); @(negedge clk); out_ready=0;\n' if f in (0,4) else 'wait(out_valid); repeat(4) @(negedge clk); out_ready=1; @(negedge clk); out_ready=0;\n']
    code += [f'''if(outputs!=8 || started!=8 || accepted!={8*t}) $fatal(1,"wrong handshake totals");
$display("CHAIN_PASS outputs=%0d samples=%0d stalls=%0d",outputs,accepted,stalls); $finish;
end
initial begin #1000000; $fatal(1,"timeout"); end
endmodule
''']
    tb=output/'tb_chain.sv';tb.write_text(''.join(code),encoding='utf-8',newline='\n')
    return tb, frames

def check(stdout, frames):
    got=re.findall(r'OUTPUT (\d+) (\d+) ([0-9a-fA-F]+) (\d+) (\d+)',stdout)
    if len(got)!=len(frames): raise AssertionError('missing output '+stdout[-1000:])
    timings=[]
    starts={int(a):int(b) for a,b in re.findall(r'START (\d+) (\d+)',stdout)}
    lasts={int(a):int(b) for a,b in re.findall(r'LAST (\d+) (\d+)',stdout)}
    for row,fr in zip(got,frames):
        idx,cycle,h,ov,sticky=row; idx=int(idx); v=int(h,16);v=v-2**64 if v>=2**63 else v
        if (v,int(ov),int(sticky))!=(fr['sum'],fr['overflow'],0): raise AssertionError((row,fr))
        timings.append(dict(frame=idx,start=starts[idx],last_sample=lasts[idx],output_handshake=int(cycle),cycles_from_frame=int(cycle)-starts[idx],cycles_after_last=int(cycle)-lasts[idx]))
    for index in (0,4):
        expected=16 if len(frames[index]['counts'])==4 else 18
        if timings[index]['cycles_after_last']!=expected: raise AssertionError(('latency',timings[index],expected))
    if 'CHAIN_PASS' not in stdout: raise AssertionError('missing PASS')
    return dict(status='passed',frames=len(frames),timings=timings,backpressure_tested=True)
