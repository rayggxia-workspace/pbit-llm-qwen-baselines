"""Finite-width/event equivalence against original RTL and independent Python integers."""
import argparse, hashlib, json, random, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def pack(values,width):
    return sum((int(v)&((1<<width)-1)) << (i*width) for i,v in enumerate(values))

def generate(out,m,bins,t,seed):
    rng=random.Random(seed);aw=1+(64*127*t).bit_length()+2*(bins-1)
    contents={x:[] for x in ['wmag','wsign','xsign','bins','expect','samples']}
    names=['zero','positive_max','negative_max','cancel','all_bins','invalid_bin','iid','stratified32']
    for f,name in enumerate(names):
        mags=[rng.randrange(128) for _ in range(64*m)]
        signs=[rng.randrange(2) for _ in mags];xs=[rng.randrange(2) for _ in range(64)]
        bs=[rng.randrange(bins) for _ in range(64)];ps=[rng.randrange(257) for _ in range(64)]
        if name in ['positive_max','negative_max','cancel']:
            mags=[127]*(64*m);xs=[0]*64;bs=[0]*64
            signs=[int(name=='negative_max') if name!='cancel' else (i%2) for i in range(64*m)]
        if name=='all_bins':bs=[i%bins for i in range(64)]
        if name=='invalid_bin':bs=[bins+(i%(8-bins)) for i in range(64)]
        events=[]
        for j in range(t):
            rv=8*(j%32)+rng.randrange(8) if name=='stratified32' else rng.randrange(256)
            e=[0 if name=='zero' else 1 if name in ['positive_max','negative_max','cancel','invalid_bin'] else int(rv<p) for p in ps]
            events.append(e);contents['samples'].append(pack(e,1))
        sums=[]
        for lane in range(m):
            total=0
            for e in events:
                for n in range(64):
                    if bs[n]<bins:
                        v=mags[lane*64+n]*(-1 if signs[lane*64+n]^xs[n] else 1)
                        total+=(v*e[n]) << (2*(bins-1-bs[n]))
            assert -(1<<(aw-1))<=total<(1<<(aw-1));sums.append(total)
        for key,values,width in [('wmag',mags,7),('wsign',signs,1),('xsign',xs,1),('bins',bs,3),('expect',sums,aw)]:
            contents[key].append(pack(values,width))
    for name,values in contents.items():
        (out/(name+'.hex')).write_text(''.join(f'{v:x}\n' for v in values),encoding='ascii')
    return aw,names

BENCH=r'''`timescale 1ns/1ps
module tb;
localparam N=64,M=__M__,BINS=__B__,T=__T__,AW=__A__,P=__P__,S=6/P,F=8;
reg clk=0;always #5 clk=~clk;
reg rst_n=0,test_en=0,frame_valid=0,sample_valid=0,out_ready=0;
reg [N*M*7-1:0] w_mag7=0;reg [N*M-1:0] w_sign=0;reg [N-1:0] x_sign=0;
reg [N*3-1:0] bin_id=0;reg [N-1:0] sample_bits=0;
wire fr0,fr1,frr,sr0,sr1,srr,ov0,ov1,ovr;
wire [M*AW-1:0] y0,y1,yr;
sc_counter_merged #(.M(M),.BINS(BINS),.T(T),.PIPE_EVERY(P),.GATE_MODE(0)) ungated(
 .clk(clk),.rst_n(rst_n),.test_en(test_en),.frame_valid(frame_valid),.frame_ready(fr0),
 .w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),.bin_id(bin_id),.sample_bits(sample_bits),
 .sample_valid(sample_valid),.sample_ready(sr0),.out_valid(ov0),.out_ready(out_ready),.out_sum(y0));
sc_counter_merged #(.M(M),.BINS(BINS),.T(T),.PIPE_EVERY(P),.GATE_MODE(1)) gated(
 .clk(clk),.rst_n(rst_n),.test_en(test_en),.frame_valid(frame_valid),.frame_ready(fr1),
 .w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),.bin_id(bin_id),.sample_bits(sample_bits),
 .sample_valid(sample_valid),.sample_ready(sr1),.out_valid(ov1),.out_ready(out_ready),.out_sum(y1));
reference_aligned #(.M(M),.BINS(BINS),.T(T)) ref_old(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frr),
 .w_mag7(w_mag7),.w_sign(w_sign),.x_sign(x_sign),.bin_id(bin_id),.sample_bits(sample_bits),
 .sample_valid(sample_valid),.sample_ready(srr),.out_valid(ovr),.out_ready(out_ready),.out_sum(yr));
reg [N*M*7-1:0] wm[0:F-1];reg [N*M-1:0] ws[0:F-1];reg [N-1:0] xs[0:F-1];
reg [N*3-1:0] bs[0:F-1];reg [M*AW-1:0] ex[0:F-1];reg [N-1:0] bits[0:F*T-1];
integer cycles=0, gated_edges=0, base_edges, frame, j, gap, last_c, seen0, seenr, good=0;
reg checking=0; reg [M*AW-1:0] expected;
always @(posedge clk) cycles=cycles+1;
always @(posedge gated.data_clk) gated_edges=gated_edges+1;
always @(posedge clk) begin
 #0.01;
 if(rst_n) begin
   if({fr0,sr0,ov0,y0} !== {fr1,sr1,ov1,y1}) $fatal(1,"gated/ungated mismatch cycle %0d",cycles);
   if(checking) begin
     if(ov0) begin
       if(y0!==expected) $fatal(1,"new integer mismatch cycle %0d got %h want %h",cycles,y0,expected);
       if(seen0<0) seen0=cycles;
     end
     if(ovr) begin
       if(yr!==expected) $fatal(1,"old integer mismatch cycle %0d",cycles);
       if(seenr<0) seenr=cycles;
     end
   end
 end
end
task tick;begin @(posedge clk);#0.02;end endtask
task neg;begin @(negedge clk);#0.01;end endtask
task start_frame(input integer f);
begin
 neg;
 if(!fr0 || !fr1 || !frr) $fatal(1,"not ready at frame start");
 w_mag7=wm[f];w_sign=ws[f];x_sign=xs[f];bin_id=bs[f];frame_valid=1;
 sample_valid=0;out_ready=0;tick;neg;frame_valid=0;
end endtask
task do_reset;
begin
 neg;rst_n=0;frame_valid=0;sample_valid=0;out_ready=0;checking=0;
 repeat(3) tick;
 neg;rst_n=1;tick;
 if(!fr0 || !frr || ov0 || ovr || y0!==0 || yr!==0) $fatal(1,"reset failed");
end endtask
initial begin
 $readmemh("wmag.hex",wm);$readmemh("wsign.hex",ws);$readmemh("xsign.hex",xs);
 $readmemh("bins.hex",bs);$readmemh("expect.hex",ex);$readmemh("samples.hex",bits);
 do_reset;
 repeat(3)tick;neg;base_edges=gated_edges;
 repeat(9)tick;
 if(gated_edges!=base_edges) $fatal(1,"idle data clock did not stop");
 neg;test_en=1;repeat(4)tick;
 if(gated_edges<=base_edges) $fatal(1,"test enable did not open clock");
 neg;test_en=0;
 start_frame(1);
 repeat(5) begin sample_valid=1;sample_bits={N{1'b1}};tick;neg;end
 do_reset;
 start_frame(1);
 repeat(T) begin sample_valid=1;sample_bits={N{1'b1}};tick;neg;end
 sample_valid=0;rst_n=0;tick;do_reset;
 for(frame=0;frame<F;frame=frame+1) begin
   start_frame(frame);expected=ex[frame];seen0=-1;seenr=-1;checking=1;
   for(j=0;j<T;j=j+1) begin
     gap=(j%19==7)?8:((j%7==3)?1:0);
     repeat(gap) begin sample_valid=0;sample_bits=~sample_bits;tick;neg;end
     if(!sr0 || !srr) $fatal(1,"sample II/ready violation");
     sample_valid=1;sample_bits=bits[frame*T+j];tick;
     if(j==T-1) last_c=cycles;
     neg;
   end
   sample_valid=0;sample_bits=0;
   while(!ov0 || !ovr) begin tick;neg;end
   if(seen0-last_c!=S || seenr-last_c!=6) $fatal(1,"latency new=%0d old=%0d",seen0-last_c,seenr-last_c);
   repeat(6) begin tick;neg;end
   base_edges=gated_edges;repeat(5)begin tick;neg;end
   if(gated_edges!=base_edges) $fatal(1,"output-held data clock did not stop");
   out_ready=1;tick;neg;out_ready=0;checking=0;
   good=good+1;
 end
 $display("PASS frames=%0d M=%0d BINS=%0d T=%0d PIPE_EVERY=%0d LAST_TO_VALID=%0d cycles=%0d gated_edges=%0d",good,M,BINS,T,P,S,cycles,gated_edges);
 $finish;
end
initial begin #1000000;$fatal(1,"timeout");end
endmodule
'''

def run(args):
    if args.ivl: args.ivl=str(Path(args.ivl).resolve())
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=False)
    icg=Path(args.icg).resolve();cases=[];started=time.time()
    src=[icg,ROOT/'rtl/sc_counter_merged.sv',ROOT/'tests/reference_ffn_counter.sv',ROOT/'tests/reference_aligned.sv']
    specs=[(m,b,t,p) for m in [1,8] for b,t in [(4,64),(7,128)] for p in [1,2]]
    if args.smoke:specs=[(1,4,64,1),(1,7,128,2)]
    for m,b,t,p in specs:
      for seed in ([17,31,193] if m==1 else [17]):
        name=f'm{m}_b{b}_t{t}_p{p}_seed{seed}';folder=out/name;folder.mkdir()
        aw,patterns=generate(folder,m,b,t,seed)
        tb=BENCH
        for k,v in dict(M=m,B=b,T=t,A=aw,P=p).items():tb=tb.replace('__'+k+'__',str(v))
        (folder/'tb.sv').write_text(tb,encoding='utf-8',newline='\n')
        compile_cmd=[args.iverilog]+(['-B',args.ivl] if args.ivl else [])+['-g2012','-s','tb','-o','sim.vvp',*[str(x) for x in src],str(folder/'tb.sv')]
        c=subprocess.run(compile_cmd,cwd=folder,capture_output=True,text=True,timeout=180)
        (folder/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        sim_cmd=[args.vvp]+(['-M',args.ivl] if args.ivl else [])+['sim.vvp']
        print('RUN '+name,flush=True)
        z=subprocess.run(sim_cmd,cwd=folder,capture_output=True,text=True,timeout=900)
        (folder/'simulation.log').write_text(z.stdout+z.stderr,encoding='utf-8')
        if z.returncode or 'PASS frames=8' not in z.stdout:raise RuntimeError(z.stdout+z.stderr)
        cases.append(dict(case=name,status='passed',seed=seed,frames=8,patterns=patterns,stdout=z.stdout.strip()))
        print(z.stdout.strip(),flush=True)
        (out/'summary.json').write_text(json.dumps(dict(status='running',cases=cases),indent=2)+'\n',encoding='utf-8')
    receipt=dict(status='passed',scope='RTL zero-delay integer/handshake/behavioral ICG only; no STA/PPA',cases=cases,
        frames=sum(x['frames'] for x in cases),elapsed_s=time.time()-started,
        source_sha256={str(x.relative_to(ROOT)) if x.is_relative_to(ROOT) else 'common/pbit_icg.sv':hashlib.sha256(x.read_bytes()).hexdigest() for x in src},
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'summary.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print('ALL PASS',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--icg',required=True)
    ap.add_argument('--iverilog',default='iverilog');ap.add_argument('--vvp',default='vvp');ap.add_argument('--ivl');ap.add_argument('--smoke',action='store_true')
    run(ap.parse_args())
