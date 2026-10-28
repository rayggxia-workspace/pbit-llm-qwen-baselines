"""Build isolated 128-lane control variants from the verified v2 equations."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'control_v2'
def write(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(s.encode('utf-8'))
def main():
    src=(OLD/'rtl/ac_winner.sv').read_text()
    src=src.replace('module ac_winner #(','module ac_winner128 #(')
    src=src.replace('parameter integer N=512,','parameter integer COUNT_W=32,N=128,')
    src=src.replace('input wire [31:0] requested_samples,burn_updates','input wire [COUNT_W-1:0] requested_samples,burn_updates')
    src=src.replace('output reg [31:0] issued,committed,consumed,holds,switches,fair_words,fair_bits,rank_retries,','output reg [COUNT_W-1:0] issued,committed,\n output reg [31:0] consumed,holds,switches,fair_words,fair_bits,rank_retries,')
    src=src.replace('reg [31:0] target_frames,burn_r;','reg [COUNT_W-1:0] target_frames,burn_r;')
    src=src.replace(">33'h0ffffffff",">{1'b0,{COUNT_W{1'b1}}}")
    src=src.replace('initial if(N<2','initial if(COUNT_W<1||COUNT_W>32||N<2')
    write(HERE/'rtl/ac_winner128.sv',src)
    write(HERE/'rtl/ac_scan.sv',(OLD/'rtl/ac_scan.sv').read_text())
    specs=[]
    configs=[(8,1,0,0,10,1),(16,1,0,0,10,1),(32,1,0,0,10,1),(16,2,0,0,10,1),
             (16,1,0,1,10,1),(16,1,1,0,10,1),(16,1,0,0,32,1),(16,1,0,0,10,0)]
    for group,prep,onehot,early,count,stream in configs:
        name=f'win128_g{group}_p{prep}_o{onehot}_e{early}_c{count}_s{stream}'
        ports='''input wire clk,rst_n,start,output wire start_ready,busy,cfg_valid,input wire cfg_ready,
 input wire [127:0] candidate_mask,input wire [6:0] initial_index,
 input wire [COUNT_W-1:0] requested_samples,burn_updates,
 input wire frame_valid,output wire frame_ready,input wire [127:0] frame_bits,
 input wire fair_valid,output wire fair_ready,input wire [6:0] fair_word,
 output wire out_valid,input wire out_ready,output wire [6:0] out_index,output wire done,failed'''.replace('COUNT_W',str(count))
        signals='clk rst_n start start_ready busy cfg_valid cfg_ready candidate_mask initial_index requested_samples burn_updates frame_valid frame_ready frame_bits fair_valid fair_ready fair_word out_valid out_ready out_index done failed'.split()
        connect=','.join('.'+x+'('+x+')' for x in signals)
        connect+=','+','.join('.'+x+'()' for x in 'issued committed consumed holds switches fair_words fair_bits rank_retries winner_index'.split())
        body=f'module {name}({ports});\nac_winner128 #(.N(128),.GROUP({group}),.PREP_STAGES({prep}),.WINNER_ONEHOT({onehot}),.EARLY_HOLD({early}),.COUNT_W({count}),.STREAM({stream}),.RANK_CAP(64)) dut({connect});\nendmodule\n'
        write(HERE/'rtl'/f'{name}.sv',body)
        specs.append(dict(top=name,kind='winner',group=group,prep=prep,onehot=onehot,early=early,count_width=count,stream=stream))
    write(HERE/'CASES.json',json.dumps(dict(tops=specs,N=128,parent='5f4f5bde2051c7c646d5a790179ad37208a8b9de',old_rtl_sha256=hashlib.sha256((OLD/'rtl/ac_winner.sv').read_bytes()).hexdigest(),scope='feedback/arbitration only; no probability driver/RNG/V/memory/accumulator'),indent=2)+'\n')
    tb=(OLD/'eda_20261028/tb_eda.sv').read_text().replace('[511:0]','[127:0]').replace('[8:0]','[6:0]')
    tb=tb.replace('reg [31:0] requested_samples=0,burn_updates=0;','reg [`AC_COUNT_W-1:0] requested_samples=0,burn_updates=0;')
    write(HERE/'tb_eda.sv',tb)
    dc=(OLD/'eda_20261028/dc.tcl').read_text().replace('ac_scan.sv ac_winner.sv ac_rejection.sv nr_singleton_tree.sv','ac_scan.sv ac_winner128.sv')
    dc=dc.replace('report_constraint -all_violators > constraints.rpt','report_constraint -all_violators > constraints.rpt\n    report_timing -from [all_registers -clock_pins] -to [all_registers -data_pins] -delay_type max -max_paths 10 > reg_setup.rpt\n    report_timing -from [all_registers -clock_pins] -to [all_registers -data_pins] -delay_type min -max_paths 10 > reg_hold.rpt')
    write(HERE/'dc.tcl',dc)
    pt=(OLD/'eda_20261028/pt.tcl').read_text()
    pt=pt.replace('report_analysis_coverage > analysis_coverage.rpt','report_analysis_coverage > analysis_coverage.rpt\n    report_analysis_coverage -status_details untested > untested.rpt\n    report_disable_timing > disable_timing.rpt\n    report_exceptions > exceptions.rpt\n    report_timing -from [all_registers -clock_pins] -to [all_registers -data_pins] -delay_type max -max_paths 10 > reg_setup.rpt\n    report_timing -from [all_registers -clock_pins] -to [all_registers -data_pins] -delay_type min -max_paths 10 > reg_hold.rpt')
    write(HERE/'pt.tcl',pt)
    write(HERE/'job.sh',(OLD/'eda_20261028/job.sh').read_text())
    print(json.dumps(dict(tops=len(specs),changed_equations='only finite sample-counter widths; default32 identical, new10 supports 1..1023 total updates')))
if __name__=='__main__':main()
