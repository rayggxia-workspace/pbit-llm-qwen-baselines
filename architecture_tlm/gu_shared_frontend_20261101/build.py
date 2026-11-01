"""Build paired shared/replicated GU source and synthetic bit-true fixtures."""
from pathlib import Path
import hashlib
import importlib.util
import json
import zipfile

P=Path(__file__).resolve().parent
SEEDS=(17,503,1009)
SOURCE_BASE='3a0fa5395005624d65cbc519c8c6a2d286a6bfb4'


def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


def main():
    assert not (P/'EXECUTION_MANIFEST.json').exists(), 'Frozen; make a new snapshot'
    archive=P.parent/'nonlinear_wd_t64_20261031/results/SOURCE_CODE.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()=='516c28ef45f3e9a6071c418d0cf69555541a88c4289b1b3d1a9ed76aee74ce25'
    copied={}
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.startswith('flow/') or name in ('job.sh','rtl/primitives.sv'):
                raw=z.read(name);dest=P/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
                copied[name]=hashlib.sha256(raw).hexdigest()
    flow=P/'flow/run_integrated.py'
    s=flow.read_text(encoding='utf-8')
    start=s.index('U.ROOT=ROOT;');end=s.index('\n_config=',start)
    s=s[:start]+"U.ROOT=ROOT;U.FLOW=FLOW;U.sources=lambda:[ROOT/'rtl/primitives.sv',ROOT/'rtl/gu_integrated.sv',ROOT/'rtl/tops.sv']"+s[end:]
    s=s.replace("operation_definition='oneK64/M8 frame:'+str(c['cycles_per_frame'])+'cycles;66full or98shared;T64;prepare/sample first-frame diagnostics separate',",
        "operation_definition='oneK64/M'+str(c['M'])+'/T64frame;66cycles;M/2g+M/2uoutputs',")
    old="boundary='Already encodedg8/u8->full64 or2shared LUT;512probability bits in shared variants;192eight-bit comparators;AND;fixedWd M8;weighted20 orOR4signed9/10;no GU,SRAM,PRNG,crossK/FP/CTS/SDF/SPEF. CE or64realwordICG as case states.'"
    assert old in s
    s=s.replace(old,"boundary='EncodedP8x+sign+fullone and externalR8;64SNGshared acrossMcolumns versus64SNGper8columns;fixedWsignmag7;20bit/output;no source/SRAM/holding/crossK/quantizer/CTS/SDF/SPEF'")
    flow.write_bytes(s.encode('utf-8'))
    spec=importlib.util.spec_from_file_location('gu_vectors',P/'vectors.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
    cases=[];tops=[];checks=[]
    for M in (16,64):
        for shared in (0,1):
            name='gu_m%d_%s'%(M,'shared' if shared else 'replicated8')
            c=dict(name=name,top=name,M=M,shared=shared,T=64,din_bits=1152*(M//8)+512*M+16,
                dout_bits=M*32+17,cycles_per_frame=66,frontend_count=1 if shared else M//8,
                comparator_bits=8,counter_bits=20,expected_DFF_bits=M*20+7)
            counts=[]
            for seed in SEEDS:
                result=v.fixtures(c,seed);checks.append(result);counts.append(result['transactions'])
            assert len(set(counts))==1;c['transactions']=counts[0];cases.append(c)
            tops.append('module %s(input wire clk,rst_n,en,input wire [%d:0] din,output wire [%d:0] dout);gu_integrated #(.M(%d),.SHARE(%d)) u(.*);endmodule\n'%(c['top'],c['din_bits']-1,c['dout_bits']-1,M,shared))
            bench='''`timescale 1ns/1ps
module tb;
reg clk=0,rst_n=0,en=0;always #5 clk=~clk;
reg [DI-1:0] din=0;wire [DO-1:0] dout;
reg [DI+1:0] stim[0:COUNT-1];reg [DO-1:0] expected[0:COUNT-1];integer i;
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
'''
            for k,value in [('COUNT',counts[0]),('TOP',c['top']),('DI',c['din_bits']),('DO',c['dout_bits'])]:bench=bench.replace(k,str(value))
            dest=P/'benches'/(name+'.sv');dest.parent.mkdir(exist_ok=True);dest.write_bytes(bench.encode())
    (P/'rtl/tops.sv').write_bytes(('`timescale 1ns/1ps\n'+''.join(tops)).encode())
    for M in (16,64):
        for seed in SEEDS:
            a=P/'fixtures'/('gu_m%d_replicated8'%M)/str(seed);b=P/'fixtures'/('gu_m%d_shared'%M)/str(seed)
            for name in ('stim.hex','expect.hex'):
                assert (a/name).read_bytes()==(b/name).read_bytes(),(M,seed,name)
    save(P/'CASES.json',cases)
    save(P/'INPUT_CHECK.json',dict(status='PASS',paired_stimuli_and_expected_bytes_equal=True,independent_oracles='direct signed-weight sum versus seven magnitude planes;all rows and prefixes',checks=checks))
    save(P/'FLOW_PROVENANCE.json',dict(source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),copied_unmodified_or_before_adapter_sha256=copied,adapter='sources and cost boundary changed in run_integrated.py;constraints/STA/activity validation unchanged'))
    save(P/'CONFIG.json',dict(date='2026-11-01',issue=204,owner='rayggxia',source_base=SOURCE_BASE,N=64,M_candidates=[16,64],T=64,
        seeds=list(SEEDS),PVT='SS1.08V125C',clock_MHz=100,output_load_pF=.001,area_factor=.81,cases=4,
        baseline='One SNG64 per8columns with separate symbolic input-copy ports;copies have identical values every row',
        shared='One SNG64 broadcasts events/signs to all columns;first halfWg,secondWu',
        output='M32signed counts+2signed8 shared exponents+valid;Y=C*2^(ex+eW-6)',
        windows=['idle_clock_source_active','idle_source_stopped','hold_nonzero','replay64'],
        functional_checks=sum(x['transactions'] for x in checks),PT_windows=48,
        exclusions=['physical PRNG and distribution before SNG','sourcex/W SRAM and holding','crossK alignment/accumulation','g/u output quantization','BF16','CTS/SDF/SPEF'],
        note='Synthetic implementation/cost ablation only;no model quality claim;baseline external port copies do not charge duplicate DRAM reads'))
    print(json.dumps(dict(cases=4,checks=sum(x['transactions'] for x in checks),paired_bytes=True)))


if __name__=='__main__':main()
