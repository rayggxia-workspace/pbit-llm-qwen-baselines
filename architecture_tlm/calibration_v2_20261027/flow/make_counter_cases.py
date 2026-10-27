"""Generate per-top/per-window counter cases, without starting any EDA job."""
import argparse,json
from pathlib import Path
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--frequencies",type=float,nargs="+",default=[100])
    ap.add_argument("--bins",type=int,nargs="+",choices=[4,7],default=[4,7])
    ap.add_argument("--outputs",type=int,nargs="+",choices=[1,8],default=[1])
    ap.add_argument("--pipeline",type=int,nargs="+",choices=[1,2],default=[1,2])
    ap.add_argument("--gate-mode",type=int,nargs="+",choices=[0,2],default=[0])
    ap.add_argument("--modes",nargs="+",choices=["continuous","sparse","idle","wake","stall"],default=["continuous","idle"])
    ap.add_argument("--seed",type=int,default=17);ap.add_argument("--frames",type=int,default=8)
    a=ap.parse_args()
    if a.output.exists(): raise SystemExit("Use new case directory")
    if a.frames<=0 or any(f<=0 for f in a.frequencies):raise SystemExit("Invalid frames/frequency")
    a.output.mkdir(parents=True)
    count=0
    for b in a.bins:
      for m in a.outputs:
       for p in a.pipeline:
        for gate in a.gate_mode:
         for freq in a.frequencies:
          for mode in a.modes:
           t=64 if b==4 else 128;aw=26 if b==4 else 33
           top=f"counter_b{b}_t{t}_m{m}_p{p}_g{gate}"
           name=f"{top}_{freq:g}MHz_{mode}_s{a.seed}".replace(".","_")
           c=dict(id=name,top=top,tb_top="tb_counter_power",gate_mode=gate,frequency_mhz=freq,
            rtl_files=["common/pbit_icg.sv","counter/rtl/sc_counter_merged.sv","counter/rtl/counter_tops.sv"],
            tb_files=["counter/tests/tb_counter_power.sv"],include_dirs=["common","counter/rtl"],
            defines=[f"DUT_TOP={top}",f"DUT_M={m}",f"DUT_BINS={b}",f"DUT_T={t}",f"DUT_AW={aw}"],
            plusargs=[f"+MODE={mode}",f"+SEED={a.seed}",f"+FRAMES={a.frames}","+P8=128"],
            power_mode=mode,operation_name=f"N64_M{m}_T{t}_completed_frame",
            outputs_per_operation=m,latency_cycles=None,ii_cycles=1,
            timing_note="sample II1; measured frame/drain latency from functional bench; not STA verified")
           (a.output/(name+".json")).write_text(json.dumps(c,indent=2)+"\n",encoding="utf-8",newline="\n");count+=1
    print(json.dumps(dict(cases=count,started_jobs=0,output=str(a.output))))
if __name__=="__main__":main()
