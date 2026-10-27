"""Portable DC / gate-VCS / PrimeTime calibration driver. No implicit EDA runs."""
import argparse, hashlib, json, math, os, re, subprocess, sys
from pathlib import Path
PACKAGE = Path(__file__).resolve().parents[1]
FLOW = Path(__file__).resolve().parent
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v): Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False)+"\n",encoding="utf-8",newline="\n")
def tcl(value):
    value=str(value).replace("\\","/")
    if any(c in value for c in "{}\n\r"): raise ValueError("Tcl configuration contains brace/newline")
    return "{"+value+"}"
def paths(values,base):
    result=[]
    for v in values:
        p=Path(v)
        if not p.is_absolute(): p=base/p
        p=p.resolve()
        if not p.is_file(): raise ValueError("Missing file: "+str(p))
        result.append(p)
    return result
def normalize(case,library,base=PACKAGE,library_base=None,case_base=None):
    c=dict(case); l=dict(library); lb=library_base or base; cb=case_base or base
    for key in ("id","top","tb_top"):
        if not IDENT.fullmatch(c[key]): raise ValueError("Invalid "+key)
    c.setdefault("gate_mode",0)
    if re.search(r"_g([02])$",c["top"]) and int(c["top"][-1])!=c["gate_mode"]: raise ValueError("top/gate_mode mismatch")
    if c["gate_mode"] not in (0,2): raise ValueError("Synthesis requires GATE_MODE=0 or 2; mode 1 is simulation-only")
    freq=float(c.get("frequency_mhz",100))
    if freq<=0: raise ValueError("frequency_mhz must be positive")
    c["frequency_mhz"]=freq; c["period_ns"]=1000/freq
    c["uncertainty_ns"]=float(c.get("uncertainty_ns",c["period_ns"]*.05))
    if not 0<=c["uncertainty_ns"]<c["period_ns"]: raise ValueError("Invalid uncertainty")
    for k in ("input_transition_ns","clock_transition_ns","hold_uncertainty_ns"): c[k]=float(c.get(k,.05))
    for k in ("input_delay_max_ns","output_delay_max_ns"): c[k]=float(c.get(k,c["period_ns"]*.1))
    for k in ("input_delay_min_ns","output_delay_min_ns"): c[k]=float(c.get(k,.02))
    c["load_pf"]=float(c.get("load_pf",.02))
    for k in ("rtl_files","tb_files"):
        c[k]=paths(c.get(k,[]),base)
        if not c[k]: raise ValueError(k+" cannot be empty")
    c["data_files"]=paths(c.get("data_files",[]),cb)
    c["validator_source_files"]=paths(c.get("validator_source_files",[]),base)
    if c.get("fixture_manifest"): c["fixture_manifest"]=paths([c["fixture_manifest"]],cb)[0]
    if c.get("validator_script"): c["validator_script"]=paths([c["validator_script"]],base)[0]
    c["include_dirs"]=[str((base/Path(p)).resolve()) if not Path(p).is_absolute() else p for p in c.get("include_dirs",[])]
    c["defines"]=list(c.get("defines",[]))
    for d in c["defines"]:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(=[A-Za-z0-9_]+)?",d): raise ValueError("Unsafe define")
    l["target_db"]=paths([l["target_db"]],lb)[0]
    l["verilog_models"]=paths(l.get("verilog_models",[]),lb)
    if not l["verilog_models"]: raise ValueError("Gate simulation requires library Verilog models")
    if not IDENT.fullmatch(l["reference_cell"]): raise ValueError("Invalid reference_cell")
    for k in ("voltage_v","temperature_c"): l[k]=float(l[k])
    if not l.get("corner"): raise ValueError("corner required")
    l["operating_condition_pattern"]=l.get("operating_condition_pattern",{"ss":"ss|slow","tt":"tt|typ","ff":"ff|fast"}.get(l["corner"],""))
    if not l["operating_condition_pattern"]: raise ValueError("Explicit operating_condition_pattern required for custom corner")
    if l.get("area_scale_um2") is not None:
        l["area_scale_um2"]=float(l["area_scale_um2"])
        if l["area_scale_um2"]<=0 or not l.get("area_unit_source"): raise ValueError("Area conversion needs positive scale and evidence")

    if c["gate_mode"]==2:
        if not IDENT.fullmatch(l.get("icg_cell","")) or l["icg_cell"].startswith("FILL"): raise ValueError("MODE2 requires icg_cell")
        for key in ("icg_enable_pin","icg_test_enable_pin"):
            if not IDENT.fullmatch(l.get(key,"")) or l[key].startswith("FILL"): raise ValueError("MODE2 requires real "+key)
        wrapper=paths([l["icg_wrapper"]],lb)[0]
        if wrapper not in c["rtl_files"]: c["rtl_files"].append(wrapper)
        c["defines"].append("PB_ICG_TECH_MAPPED")
    return c,l
def validate_fixture(c):
    """Bind digital replay data to the independently generated expected trace."""
    if not c.get("fixture_manifest"): return None
    p=c["fixture_manifest"]; f=json.loads(p.read_text(encoding="utf-8"))
    if f.get("top")!=c["top"] or f.get("period_ns")!=c["period_ns"]:
        raise ValueError("Fixture top/period differs from case")
    for name,key in (("vectors.txt","vector_sha256"),("expected.json","expected_sha256")):
        q=p.parent/name
        if not q.is_file() or digest(q)!=f.get(key): raise ValueError("Fixture SHA mismatch: "+name)
        if q not in c["data_files"]: c["data_files"].append(q)
    if not c.get("validator_script"): raise ValueError("Digital fixture needs a post-simulation oracle")
    return f

def validate_window_fixture(w,f):
    if f is None: return
    for key in ("start_ns","end_ns"):
        if not math.isclose(w[key],f[key],abs_tol=1e-5,rel_tol=1e-9): raise ValueError("Bench/fixture window differs: "+key)
    if w["operations"]!=f["frames"] or w["accepted_samples"]!=f["accepted_samples"]:
        raise ValueError("Bench/fixture accepted or retired count differs")

def configuration(c,l):
    rows=[]
    values={"CV2_TOP":c["top"],"CV2_LIBRARY_DB":l["target_db"],"CV2_REF_CELL":l["reference_cell"],
        "CV2_CORNER":l["corner"],"CV2_CORNER_PATTERN":l["operating_condition_pattern"],"CV2_VOLTAGE":l["voltage_v"],"CV2_TEMPERATURE":l["temperature_c"],
        "CV2_ICG_CELL":l.get("icg_cell",""),"CV2_ICG_EN_PIN":l.get("icg_enable_pin",""),"CV2_ICG_TE_PIN":l.get("icg_test_enable_pin",""),"CV2_GATE_MODE":c["gate_mode"]}
    for k in ("period_ns","uncertainty_ns","hold_uncertainty_ns","input_transition_ns","clock_transition_ns",
              "input_delay_max_ns","input_delay_min_ns","output_delay_max_ns","output_delay_min_ns","load_pf"):
        values["CV2_"+k.upper()]=c[k]
    for key,value in values.items(): rows.append("set ::"+key+" "+tcl(value))
    for key,vals in [("CV2_RTL",c["rtl_files"]),("CV2_DEFINES",["SYNTHESIS"]+c["defines"]),("CV2_INCLUDE",c["include_dirs"])]:
        rows.append("set ::"+key+" [list "+" ".join(tcl(v) for v in vals)+"]")
    return "\n".join(rows)+"\n"
def execute(argv,cwd,env,phase,timeout):
    dump(cwd/(phase+"_command.json"),[str(x) for x in argv])
    p=subprocess.run([str(x) for x in argv],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    (cwd/(phase+".log")).write_bytes(p.stdout)
    if p.returncode: raise RuntimeError(phase+" exit "+str(p.returncode))
def number(path):
    if not path.is_file(): return None
    try: return float(path.read_text().strip())
    except ValueError: return None
def collect_sta(folder,gate_mode=0):
    setup=number(folder/"setup_slack_ns.txt"); hold=number(folder/"hold_slack_ns.txt")
    state="unknown" if setup is None or hold is None else "met" if min(setup,hold)>=0 else "not_met"
    gating=dict(status="not_applicable")
    if gate_mode==2:
        a=number(folder/"gate_setup_slack_ns.txt");b=number(folder/"gate_hold_slack_ns.txt")
        reports=[folder/"gate_setup.rpt",folder/"gate_hold.rpt"]
        classified=all(p.is_file() and "gating" in p.read_text(errors="replace").lower() for p in reports)
        gating=dict(setup_slack_ns=a,hold_slack_ns=b,library_gating_paths_reported=classified,
            status="review_required" if a is None or b is None or not classified else "met" if min(a,b)>=0 else "not_met")
        if gating["status"]!="met" and state=="met":state=gating["status"]
    return dict(setup_slack_ns=setup,hold_slack_ns=hold,status=state,gating=gating)
def power_parse(text):
    out={};factors={"w":1.,"mw":1e-3,"uw":1e-6,"nw":1e-9,"pw":1e-12}
    headers={}
    for kind in ("Dynamic","Leakage"):
        h=re.search(r"^\s*"+kind+r" Power Units?\s*[:=]\s*([0-9.eE+-]+)\s*([munp]?W)\s*$",text,re.M|re.I)
        headers[kind]=float(h[1])*factors[h[2].lower()] if h else None
    for key,label in {"internal":"Cell Internal Power","switching":"Net Switching Power","leakage":"Cell Leakage Power","total":"Total Power"}.items():
        m=re.search(r"^\s*"+re.escape(label)+r"\s*=\s*([0-9.eE+-]+)(?:\s*([munp]?W)\b)?",text,re.M|re.I)
        scale=(factors[m[2].lower()] if m and m[2] else headers["Leakage" if key=="leakage" else "Dynamic"])
        value=float(m[1])*scale if m and scale is not None else None
        out[key+"_w"]=value if value is not None and math.isfinite(value) and value>=0 else None
    vals=[out[k+"_w"] for k in ("internal","switching","leakage","total")]
    out["power_sum_consistent"]=None if any(v is None for v in vals) else math.isclose(sum(vals[:3]),vals[3],rel_tol=.02,abs_tol=1e-12)
    return out
def activity_parse(text):
    out={}
    labels={"nets":"Total number of nets","annotated_nets":"Number of annotated nets","leaves":"Total number of leaf cells","fully_annotated_leaves":"Number of fully annotated leaf cells"}
    for k,label in labels.items():
        m=re.search(re.escape(label)+r"\s*=\s*(\d+)",text);out[k]=int(m[1]) if m else None
    for a,total,name in [("annotated_nets","nets","net_coverage_percent"),("fully_annotated_leaves","leaves","leaf_coverage_percent")]:
        out[name]=100*out[a]/out[total] if out[a] is not None and out[total] and 0<=out[a]<=out[total] else None
    return out
def warnings(folder):
    texts="\n".join(p.read_text(errors="replace") for p in folder.glob("*.rpt"))
    return sorted(set(re.findall(r"(?im)^.*(?:warning:|violated|not annotated|out.of.range|extrapolat).*$",texts)))[:200]
def validate_reuse(folder,c,l):
    prior=folder.parent/"RESULT.json"
    if not prior.is_file(): raise ValueError("Reused synthesis needs its parent RESULT.json")
    old=json.loads(prior.read_text(encoding="utf-8"))
    if old.get("status")!="completed_provisional": raise ValueError("Reused synthesis did not complete")
    for key in ("top","gate_mode","period_ns","uncertainty_ns","hold_uncertainty_ns","load_pf",
                "input_transition_ns","clock_transition_ns","input_delay_max_ns","input_delay_min_ns",
                "output_delay_max_ns","output_delay_min_ns"):
        if old["case"].get(key)!=c[key]: raise ValueError("Reused synthesis configuration differs: "+key)
    for source in c["rtl_files"]+[l["target_db"]]+l["verilog_models"]:
        if old["source_sha256"].get(str(source))!=digest(source): raise ValueError("Reused synthesis source/library differs: "+str(source))
    if old.get("netlist_sha256")!=digest(folder/"mapped.v"): raise ValueError("Reused netlist hash mismatch")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case",type=Path,required=True);ap.add_argument("--library",type=Path,required=True);ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--stage",choices=["preflight","synth","gate_sim","sta","power","all"],default="preflight")
    ap.add_argument("--reuse-synth",type=Path);ap.add_argument("--windows",type=Path)
    ap.add_argument("--dc",default="dc_shell");ap.add_argument("--pt",default="pt_shell");ap.add_argument("--vcs",default="vcs");ap.add_argument("--timeout",type=int,default=7200)
    a=ap.parse_args();out=a.output.resolve()
    if out.exists(): raise SystemExit("Use a NEW output directory; frozen output is never overwritten")
    out.mkdir(parents=True);rec=dict(status="running",stage=a.stage,scope="pre-layout macro calibration; not whole chip or 500MHz proof")
    try:
        c,l=normalize(json.loads(a.case.read_text(encoding="utf-8")),json.loads(a.library.read_text(encoding="utf-8")),library_base=a.library.resolve().parent,case_base=a.case.resolve().parent)
        fixture=validate_fixture(c)
        serial=lambda d:{k:[str(x) for x in v] if isinstance(v,list) else str(v) if isinstance(v,Path) else v for k,v in d.items()}
        rec.update(case=serial(c),library=serial(l),source_sha256={str(p):digest(p) for p in c["rtl_files"]+c["tb_files"]+[l["target_db"]]+l["verilog_models"]})
        rec["input_sha256"]={str(p):digest(p) for p in c["data_files"]+c["validator_source_files"]+[p for p in (c.get("fixture_manifest"),c.get("validator_script")) if p is not None]}
        rec["flow_sha256"]={p.name:digest(p) for p in sorted(FLOW.glob("*")) if p.is_file() and p.suffix in (".py",".tcl")}
        cfg=out/"configuration.tcl";cfg.write_text(configuration(c,l),encoding="utf-8",newline="\n");rec["configuration_sha256"]=digest(cfg)
        env=os.environ.copy();env.update(CV2_CONFIG=str(cfg),CV2_FLOW=str(FLOW))
        synth=a.reuse_synth.resolve() if a.reuse_synth else out/"synth"
        stages=["synth","gate_sim","sta","power"] if a.stage=="all" else [a.stage]
        if "synth" in stages:
            if a.reuse_synth: raise ValueError("Cannot synthesize into reused output")
            synth.mkdir();execute([a.dc,"-f",FLOW/"dc.tcl"],synth,env,"dc",a.timeout)
            if not (synth/"STAGE_COMPLETE").is_file(): raise RuntimeError("DC completion marker missing")
        if a.stage!="preflight":
            if a.reuse_synth: validate_reuse(synth,c,l)
            if not (synth/"mapped.v").is_file(): raise ValueError("Supply --reuse-synth with mapped.v for this stage")
            env["CV2_NETLIST"]=str(synth/"mapped.v");rec["netlist_sha256"]=digest(synth/"mapped.v")
        if "gate_sim" in stages:
            sim=out/"gate_sim";sim.mkdir()
            cmd=[a.vcs,"-full64","-sverilog","-timescale=1ns/1ps","+notimingcheck","+nospecify","-top",c["tb_top"],"-o",sim/"simv",synth/"mapped.v"]
            cmd+=l["verilog_models"]+c["tb_files"]+[("+incdir+"+v) for v in c["include_dirs"]]
            cmd += [("+define+"+v) for v in c["defines"]]+c.get("vcs_options",[])
            execute(cmd,sim,env,"compile",a.timeout)
            plus=[str(v).replace("{RUN_DIR}",str(sim)).replace("{CASE_DIR}",str(a.case.resolve().parent)) for v in c.get("plusargs",[])]
            execute([sim/"simv","+VCD="+str(sim/"activity.vcd"),"+PERIOD_NS="+str(c["period_ns"])]+plus,sim,env,"run",a.timeout)
            if not (sim/"activity.vcd").is_file(): raise RuntimeError("Bench did not write +VCD activity file")
            if c.get("validator_script"):
                args=[str(v).replace("{RUN_DIR}",str(sim)).replace("{CASE_DIR}",str(a.case.resolve().parent)) for v in c.get("validator_args",[])]
                execute([sys.executable,c["validator_script"]]+args,sim,env,"validate_trace",a.timeout)
                checked=json.loads((sim/"validate_trace.log").read_text(encoding="utf-8"))
                if checked.get("status")!="passed": raise RuntimeError("Trace oracle did not confirm passed")
                rec["gate_trace_validation"]=checked
                rec["gate_trace_validation_sha256"]=digest(sim/"validate_trace.log")
                if (sim/"trace.txt").is_file(): rec["gate_trace_sha256"]=digest(sim/"trace.txt")
            if (sim/"thresholds_used.hex").is_file(): rec["thresholds_used_sha256"]=digest(sim/"thresholds_used.hex")
            rec["vcd_sha256"]=digest(sim/"activity.vcd")
            text=(sim/"run.log").read_text(errors="replace")
            pat=r"WINDOW start_ns=([0-9.eE+-]+) end_ns=([0-9.eE+-]+) frames=(\d+) accepted_samples=(\d+)"
            found=re.findall(pat,text)
            if len(found)!=1: raise RuntimeError("Expected one explicit WINDOW marker from bench")
            start,end,frames,samples=found[0]
            window=dict(name=c.get("power_mode","measured"),vcd=str(sim/"activity.vcd"),strip_path=c.get("dut_path",c["tb_top"]+"/dut"),start_ns=float(start),end_ns=float(end),operations=int(frames),accepted_samples=int(samples),operation_unit=c.get("operation_name","completed_result"))
            validate_window_fixture(window,fixture)
            window["vcd_sha256"]=digest(sim/"activity.vcd")
            dump(out/"auto_windows.json",dict(top=c["top"],period_ns=c["period_ns"],netlist_sha256=rec["netlist_sha256"],windows=[window]))
        if "sta" in stages:
            sta=out/"sta";sta.mkdir();execute([a.pt,"-f",FLOW/"sta.tcl"],sta,env,"pt_sta",a.timeout);rec["sta"]=collect_sta(sta,c["gate_mode"])
            if not (sta/"STAGE_COMPLETE").is_file(): raise RuntimeError("STA completion marker missing")
        if "power" in stages:
            if not a.windows and (out/"auto_windows.json").is_file(): a.windows=out/"auto_windows.json"
            if not a.windows: raise ValueError("Power requires --windows; no invented window or operation count")
            manifest=json.loads(a.windows.read_text(encoding="utf-8"));rec["window_manifest_sha256"]=digest(a.windows);rec["windows"]=[]
            if manifest.get("netlist_sha256")!=rec["netlist_sha256"] or manifest.get("top")!=c["top"] or manifest.get("period_ns")!=c["period_ns"]: raise ValueError("Power window/netlist/top/period provenance mismatch")
            for w in manifest["windows"]:
                if not IDENT.fullmatch(w["name"]): raise ValueError("Invalid window name")
                start,end=float(w["start_ns"]),float(w["end_ns"])
                if not end>start>=0: raise ValueError("Invalid power window")
                ops=w.get("operations")
                if ops is not None and (not isinstance(ops,int) or ops<0): raise ValueError("operations must be measured nonnegative integer or null")
                vcd=Path(w["vcd"])
                if not vcd.is_absolute(): vcd=a.windows.resolve().parent/vcd
                if not vcd.is_file(): raise ValueError("Window VCD missing: "+str(vcd))
                if w.get("vcd_sha256")!=digest(vcd): raise ValueError("Window VCD SHA missing/mismatch")
                folder=out/("power_"+w["name"]);folder.mkdir()
                penv=env.copy();penv.update(CV2_VCD=str(vcd.resolve()),CV2_STRIP_PATH=w["strip_path"],CV2_START_NS=str(start),CV2_END_NS=str(end))
                execute([a.pt,"-f",FLOW/"power.tcl"],folder,penv,"pt_power",a.timeout)
                if not (folder/"POWER_CALCULATED").is_file(): raise RuntimeError("Power marker missing")
                p=power_parse((folder/"power.rpt").read_text(errors="replace"));time_s=(end-start)*1e-9
                result=dict(**w,**p,vcd_sha256=digest(vcd),duration_ns=end-start,sta=collect_sta(folder,c["gate_mode"]),area_library_units=number(folder/"area_library_units.txt"),area_um2=(number(folder/"area_library_units.txt")*l["area_scale_um2"] if l.get("area_scale_um2") is not None and number(folder/"area_library_units.txt") is not None else None),area_unit_source=l.get("area_unit_source"),
                    activity=activity_parse((folder/"activity.rpt").read_text(errors="replace")),warnings=warnings(folder),activity_status="REQUIRES_REPORT_REVIEW",status="CALCULATED_PROVISIONAL",gross_pj_per_operation=None,dynamic_pj_per_operation=None)
                if ops and p["power_sum_consistent"] is True and p["total_w"] is not None: result["gross_pj_per_operation"]=p["total_w"]*time_s*1e12/ops
                if ops and p["power_sum_consistent"] is True and p["internal_w"] is not None and p["switching_w"] is not None: result["dynamic_pj_per_operation"]=(p["internal_w"]+p["switching_w"])*time_s*1e12/ops
                if p["power_sum_consistent"] is not True:result["status"]="INCOMPLETE_POWER_UNITS_OR_TOTAL"
                rec["windows"].append(result)
        rec["status"]="preflight_passed" if a.stage=="preflight" else "completed_provisional"
        rec["usable_at_requested_frequency"]=rec.get("sta",{}).get("status")=="met" if "sta" in rec else None
    except Exception as exc:
        rec["status"]="failed";rec["error"]=repr(exc);dump(out/"RESULT.json",rec);raise
    dump(out/"RESULT.json",rec);print(json.dumps({"status":rec["status"],"output":str(out),"usable_at_requested_frequency":rec.get("usable_at_requested_frequency")}))
if __name__=="__main__": main()
