"""Freeze explicit tops/constraints and commands; no private library included."""
import argparse
from pathlib import Path
import json
from .validate import sha,write,HERE


WIN_PORTS='''input wire clk,rst_n,start,output wire start_ready,busy,cfg_valid,input wire cfg_ready,
 input wire [511:0] candidate_mask,input wire [8:0] initial_index,
 input wire [31:0] requested_samples,burn_updates,
 input wire frame_valid,output wire frame_ready,input wire [511:0] frame_bits,
 input wire fair_valid,output wire fair_ready,input wire [8:0] fair_word,
 output wire out_valid,input wire out_ready,output wire [8:0] out_index,output wire done,failed'''
WIN_CONNECT='''.clk(clk),.rst_n(rst_n),.start(start),.start_ready(start_ready),.busy(busy),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
 .candidate_mask(candidate_mask),.initial_index(initial_index),.requested_samples(requested_samples),.burn_updates(burn_updates),
 .frame_valid(frame_valid),.frame_ready(frame_ready),.frame_bits(frame_bits),.fair_valid(fair_valid),.fair_ready(fair_ready),.fair_word(fair_word),
 .out_valid(out_valid),.out_ready(out_ready),.out_index(out_index),.done(done),.failed(failed),
 .issued(),.committed(),.consumed(),.holds(),.switches(),.fair_words(),.fair_bits(),.rank_retries(),.winner_index()'''
REJ_PORTS='''input wire clk,rst_n,start,output wire start_ready,busy,cfg_valid,input wire cfg_ready,
 input wire [8:0] reference_index,input wire [31:0] requested_samples,proposal_cap,
 input wire proposal_valid,output wire proposal_ready,input wire [511:0] proposal_bits,
 output wire fair_ready,input wire fair_valid,input wire [23:0] fair_bits_input,
 output wire [4:0] shift_m,output wire out_valid,input wire out_ready,output wire [8:0] out_index,output wire done,failed'''
REJ_CONNECT='''.clk(clk),.rst_n(rst_n),.start(start),.start_ready(start_ready),.busy(busy),.cfg_valid(cfg_valid),.cfg_ready(cfg_ready),
 .reference_index(reference_index),.requested_samples(requested_samples),.proposal_cap(proposal_cap),.proposal_valid(proposal_valid),
 .proposal_ready(proposal_ready),.proposal_bits(proposal_bits),.fair_ready(fair_ready),.fair_valid(fair_valid),.fair_bits_input(fair_bits_input),
 .shift_m(shift_m),.out_valid(out_valid),.out_ready(out_ready),.out_index(out_index),.done(done),.failed(failed),
 .proposals(),.accepted(),.consumed(),.rejected_multi(),.rejected_empty(),.fair_words(),.fair_bits()'''


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False);rtl=a.output/'rtl';rtl.mkdir()
    specs=[]
    for group,prep,onehot,early in [(8,2,0,0),(16,1,0,0),(16,2,0,0),(32,2,0,0),(16,2,1,0),(16,2,0,1)]:
        name=f'win512_g{group}_p{prep}_o{onehot}_e{early}'
        body=f'module {name}({WIN_PORTS});\nac_winner #(.N(512),.GROUP({group}),.PREP_STAGES({prep}),.STREAM(1),.WINNER_ONEHOT({onehot}),.RANK_CAP(64),.EARLY_HOLD({early})) dut({WIN_CONNECT});\nendmodule\n'
        (rtl/(name+'.sv')).write_bytes(body.encode());specs.append(dict(top=name,kind='winner',group=group,prep=prep,onehot=onehot,early=early))
    for pref in (0,1):
        name=f'rej512_pref{pref}'
        body=f'module {name}({REJ_PORTS});\nac_rejection #(.N(512),.PREFETCH_FAIR({pref})) dut({REJ_CONNECT});\nendmodule\n'
        (rtl/(name+'.sv')).write_bytes(body.encode());specs.append(dict(top=name,kind='rejection',prefetch=pref))
    dependencies=[HERE/'rtl/ac_scan.sv',HERE/'rtl/ac_winner.sv',HERE/'rtl/ac_rejection.sv',HERE.parent/'rtl/nr_singleton_tree.sv']
    for src in dependencies:(rtl/src.name).write_bytes(src.read_bytes())
    write(a.output/'CASES.json',dict(tops=specs,frequencies_MHz=[100,250,500],
         first_stage='SS1.08V125C100MHz; TT1.2V25C complementary; higher frequencies only after lower-stage review',
         boundary='control only, no RNG/LUT/SRAM/QK/V; diagnostic counters disconnected and may be optimized out',
         input_slew_ns=.1,output_load_pF=.02,setup_uncertainty_ns=2,hold_uncertainty_ns=.1,
         active_idle_energy='measure separate continuous/hold/switch/rank-retry/zero/multi/empty-reject/config-wait/output-stall windows',
         source_files={str(f.relative_to(a.output)):sha(f) for f in rtl.glob('*.sv')}))
    # Commands are structured arguments; fill private runtime values through
    # environment/config, never concatenate credentials into a shell command.
    flow=Path(__file__).parent/'flow'
    for f in flow.glob('*.tcl'):(a.output/f.name).write_bytes(f.read_bytes())
    print(json.dumps(dict(tops=len(specs),output=str(a.output))))


if __name__=='__main__':main()
