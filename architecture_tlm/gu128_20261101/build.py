"""Build controlled two-M64 versus fused-M128 GU fixtures and source."""
from pathlib import Path
import hashlib,importlib.util,json,zipfile
P=Path(__file__).resolve().parent
SEEDS=(17,503,1009)
SOURCE_BASE='d0776938a4cd4bca80f1cccba4e70da058974949'
def save(p,v):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
def main():
 assert not (P/'EXECUTION_MANIFEST.json').exists(),'Frozen snapshot'
 archive=P.parent/'gu_shared_frontend_20261101/results/SOURCE_CODE.zip'
 assert hashlib.sha256(archive.read_bytes()).hexdigest()=='e140d53f47cf0822864d8b94fc5291f4e6c7a2cc6aad5369b3d58b137ecebe8d'
 copied={}
 with zipfile.ZipFile(archive) as z:
  for n in z.namelist():
   if n.startswith('flow/') or n in ('job.sh','rtl/primitives.sv'):
    raw=z.read(n);d=P/n;d.parent.mkdir(parents=True,exist_ok=True);d.write_bytes(raw);copied[n]=hashlib.sha256(raw).hexdigest()
 f=P/'flow/run_integrated.py';s=f.read_text(encoding='utf-8').replace("ROOT/'rtl/gu_integrated.sv'","ROOT/'rtl/gu128.sv'")
 s=s.replace('versus64SNGper8columns','versus2SNG64forseparateg/u64cores')
 f.write_bytes(s.encode('utf-8'))
 f=P/'flow/dc.tcl';s=f.read_text(encoding='utf-8')
 needle='    constraints\n    capture check_design_before.rpt {check_design}'
 assert needle in s
 s=s.replace(needle,'''    # Identical mapped backend8 reused sixteen times in both candidates.
    current_design gu128_backend8
    constraints
    compile -map_effort high
    capture backend8_area.rpt {report_area -hierarchy}
    write -format ddc -hierarchy -output backend8_mapped.ddc
    current_design $::CV2_TOP
    if {![link]} {error "Top link after backend mapping failed"}
    set blocks [get_cells -hierarchical * -filter "ref_name == gu128_backend8"]
    if {[sizeof_collection $blocks]!=16} {error "Expected sixteen backend8 instances"}
    set_dont_touch $blocks true
    save_text backend8_instances.txt [sizeof_collection $blocks]
    constraints
    capture check_design_before.rpt {check_design}''')
 f.write_bytes(s.encode('utf-8'))
 spec=importlib.util.spec_from_file_location('gu128_vectors',P/'vectors.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
 cases=[];tops=[];checks=[]
 for dual in (1,0):
  name='gu128_two_m64' if dual else 'gu128_fused'
  c=dict(name=name,top=name,M=128,dual=dual,T=64,din_bits=67857,dout_bits=4113,cycles_per_frame=66,frontend_count=2 if dual else 1,comparator_bits=8,counter_bits=20,backend8_instances=16,expected_DFF_bits=2574 if dual else 2567)
  cc=[]
  for seed in SEEDS:
   r=v.fixtures(c,seed);checks.append(r);cc.append(r['transactions'])
  assert len(set(cc))==1;c['transactions']=cc[0];cases.append(c)
  tops.append('module %s(input wire clk,rst_n,en,input wire [67856:0] din,output wire [4112:0] dout);gu128_integrated #(.DUAL(%d)) u(.*);endmodule\n'%(name,dual))
  bench='''`timescale 1ns/1ps
module tb;
reg clk=0,rst_n=0,en=0;always #5 clk=~clk;
reg [67856:0] din=0;wire [4112:0] dout;
reg [67858:0] stim[0:COUNT-1];reg [4112:0] expected[0:COUNT-1];integer i;
TOP dut(.*);
initial begin
 $readmemh("stim.hex",stim);$readmemh("expect.hex",expected);$dumpfile("activity.vcd");$dumpvars(0,dut);
 for(i=0;i<COUNT;i=i+1)begin
  @(negedge clk);{rst_n,en,din}=stim[i];@(posedge clk);#1;
  if(dout!==expected[i])begin $display("MISMATCH row=%0d got=%h expected=%h",i,dout,expected[i]);$fatal(1);end
 end
 @(negedge clk);#1;$display("FUNCTION_PASS transactions=%0d",COUNT);$finish;
end
endmodule
'''.replace('COUNT',str(cc[0])).replace('TOP',name)
  (P/'benches').mkdir(exist_ok=True);(P/'benches'/(name+'.sv')).write_bytes(bench.encode())
 (P/'rtl/tops.sv').write_bytes(('`timescale 1ns/1ps\n'+''.join(tops)).encode())
 for seed in SEEDS:
  for n in ('stim.hex','expect.hex','WINDOWS.json'):
   a=P/'fixtures/gu128_two_m64'/str(seed)/n;b=P/'fixtures/gu128_fused'/str(seed)/n
   assert a.read_bytes()==b.read_bytes(),(seed,n)
 save(P/'CASES.json',cases)
 save(P/'INPUT_CHECK.json',dict(status='PASS',paired_bytes_equal=True,independent_oracles='direct signed sum vs seven signed magnitude planes;every prefix;separate Wg/Wu sign extremes',checks=checks))
 save(P/'FLOW_PROVENANCE.json',dict(source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),copied_unmodified_or_before_adapter_sha256=copied,adapter='RTL source and boundary;bottom-up fixed backend8 synthesis,16instances protected in both tops;full-top STA unchanged'))
 save(P/'CONFIG.json',dict(date='2026-11-01',issue=204,owner='rayggxia',source_base=SOURCE_BASE,N=64,M=128,g_outputs=64,u_outputs=64,T=64,seeds=list(SEEDS),PVT='SS1.08V125C',clock_MHz=100,output_load_pF=.001,area_factor=.81,cases=2,baseline='two independent64outputcores;sourceA/sourceB symbolic ports;identical stimulus and coherent clear',fused='one source64 and controller,128outputs;16backend8 blocks identical to baseline',weights='64x64 Wg+64x64 Wu,sign+mag7;8192bytes outside storage boundary',output='128signed32 counts+2signed8exponents+valid;Y=C*2^(ex+eW-6)',windows=['idle_source_stopped','stall_partial','replay64'],functional_checks=sum(x['transactions'] for x in checks),PT_windows=18,exclusions=['physical PRNG and upstream broadcast','sourcex/W SRAM and holding','crossK alignment/accumulation','g/u output quantization','BF16','CTS/SDF/SPEF'],note='synthetic paired implementation cost;not training quality or whole GU. Bottom-up hierarchy differs from prior flat M64:remeasure both new candidates.'))
 print(json.dumps(dict(cases=2,checks=sum(x['transactions'] for x in checks),paired_bytes=True)))
if __name__=='__main__':main()
