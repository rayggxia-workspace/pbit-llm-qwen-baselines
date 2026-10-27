"""Generate replay fixtures and real DC/VCS/PT cases; does not invoke EDA."""
import argparse, importlib.util, json, sys
from pathlib import Path
PACKAGE=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--package",type=Path,default=PACKAGE,help="Integrated package containing digital/tests/prepare_power.py")
    ap.add_argument("--tops",nargs="+",default=["dig_fp32_add","dig_bf16_mac"])
    ap.add_argument("--modes",nargs="+",choices=["continuous","idle","stall"],default=["continuous","idle"])
    ap.add_argument("--frequency-mhz",type=float,default=100.)
    ap.add_argument("--seed",type=int,default=17)
    a=ap.parse_args(); package=a.package.resolve()
    if a.frequency_mhz<=0: raise ValueError("Frequency must be positive")
    generator=package/"digital/tests/prepare_power.py"
    if not generator.is_file(): raise ValueError("Integrate digital package before generating cases")
    sys.path.insert(0,str(generator.parent))
    spec=importlib.util.spec_from_file_location("digital_prepare_power",generator)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if any(t not in module.TOPS for t in a.tops): raise ValueError("Unknown digital top")
    if a.output.exists(): raise ValueError("Use a new output directory; do not overwrite fixtures")
    a.output.mkdir(parents=True); index=[];period=1000/a.frequency_mhz
    for top in a.tops:
        for mode in a.modes:
            name=f"{top}_{mode}_f{a.frequency_mhz:g}_s{a.seed}".replace(".","p")
            dest=a.output/name
            f=module.prepare(top,mode,a.seed,dest,period)
            mac=f["macs_per_transaction"]>0
            context=top in ("dig_bf16_accum","dig_bf16_context16")
            c=dict(id=name,top=top,tb_top=f["bench"],gate_mode=0,frequency_mhz=a.frequency_mhz,
                rtl_files=["digital/rtl/dig_fp32.sv","digital/rtl/dig_mac.sv"],
                tb_files=[f"digital/tests/{f['bench']}.sv"],defines=f["defines"],
                plusargs=[v for v in f["plusargs"] if not v.startswith("+PERIOD_NS=")],
                dut_path=f["bench"]+"/dut",power_mode=mode,seed=a.seed,
                operation_name="completed_"+top+"_transaction",primitive_operations_per_transaction=f["primitive_operations_per_transaction"],
                macs_per_transaction=f["macs_per_transaction"],
                latency_cycles=14 if mac else 2 if top=="dig_fp32_to_bf16" else 7,
                ii_cycles=15 if top=="dig_bf16_accum" else 1,
                ii_condition="round-robin independent contexts; same-context II=15" if context and top!="dig_bf16_accum" else "no downstream stall",
                activity=f["activity"],fixture_manifest="FIXTURE.json",data_files=["vectors.txt","expected.json"],
                validator_script="digital/tests/prepare_power.py",
                validator_source_files=["digital/tests/verify_digital.py","digital/tests/verify_context.py"],
                validator_args=["--check-fixture","{CASE_DIR}","--trace","{RUN_DIR}/trace.txt"])
            (dest/"case.json").write_text(json.dumps(c,indent=2)+"\n",encoding="utf-8",newline="\n")
            index.append(dict(case=str(dest/"case.json"),top=top,mode=mode,frames=f["frames"],accepted_samples=f["accepted_samples"]))
    (a.output/"INDEX.json").write_text(json.dumps(index,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(dict(status="generated_no_eda",cases=len(index),output=str(a.output)),indent=2))
if __name__=="__main__":main()
