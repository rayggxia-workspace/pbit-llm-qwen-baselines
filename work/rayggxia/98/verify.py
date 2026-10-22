"""Validate Issue98 research artifacts; no model/EDA/network execution."""
from pathlib import Path
import csv, hashlib, io, json, math, re, subprocess, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[3]
DIR = ROOT / "architecture_tlm/benchmark_protocol_20261022"
BASE = "83e15289434af50fc09c35e699d8b39965389d98"
checks = []
def check(name, value, detail=None):
    checks.append({"name":name,"passed":bool(value),"detail":detail})
    if not value:
        raise AssertionError(name)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
papers = json.loads((DIR/"PAPERS.json").read_text(encoding="utf-8"))
protocol = json.loads((DIR/"PROTOCOL_PROPOSAL.json").read_text(encoding="utf-8"))
readme = (DIR/"README_ZH.md").read_text(encoding="utf-8")
rows = list(csv.DictReader(io.StringIO((DIR/"PAPERS.csv").read_text(encoding="utf-8"))))
check("16 unique paper IDs",len(papers["papers"])==16 and len({p["id"] for p in papers["papers"]})==16)
check("CSV JSON order and row IDs match",[r["id"] for r in rows]==[p["id"] for p in papers["papers"]])
check("11 target venue rows",sum(p["venue"] in {"DAC","ISCA","MICRO","ASPLOS","HPCA"} for p in papers["papers"])==11)
check("source fields populated",all(p["source_url"].startswith("https://") and p["source_locator"] and p["source_version"] and p["pitfall"] for p in papers["papers"]))
check("all paper rows retain unknown voltage as null",all("voltage_V" in p for p in papers["papers"]))
check("protocol not executable result",protocol["status"]=="PROPOSED_NOT_APPROVED_NOT_EXECUTED" and protocol["not_runnable_simulator_config"])
check("quality acceptance not invented",protocol["quality"]["acceptance"]["noninferiority_margin"] is None and protocol["quality"]["acceptance"]["illustrative_budgets_are_venue_rules"] is False)
check("three-seed minimum retained",protocol["quality"]["stochastic"]["minimum_independent_runs"]==3)
check("acc_norm character length source recorded","len(choice_string)" in protocol["quality"]["harness"]["default_multiple_choice_acc_norm_denominator"])
check("GPU and same-node comparisons separated",protocol["fairness"]["these_are_distinct_experiments"] and "external" in protocol["fairness"]["GPU_role"])
check("unknown PPA not zero",protocol["physical_cost"]["null_means_unknown_not_zero"] and protocol["random_service"]["unknown_source_PPA_is_null"])
check("not taking implementation ownership",protocol["frozen_reference"]["implementation_issues_read_only"]==[37,78,95,96])
check("matched stable design point required","design_point_id" in protocol["output_contract"] and protocol["fairness"]["quality_and_PPA_config_must_match"])
check("no model/EDA execution authorized by proposal","No EDA execution" in protocol["non_goals"] and "No model downloads/runs" in protocol["non_goals"])
values = {
    "santa_aggregate_ms_per_output":101.22/(6*2048)*1000,
    "santa_batch_step_ms":101.22/2048*1000,
    "santa_flash_aggregate_ms_per_output":80.97/(6*2048)*1000,
    "santa_decode_speedup":101.22/80.97,
    "santa_prefill_plus_decode_speedup":(56.69+101.22)/(56.61+80.97),
    "ppl_5pct_delta_nll":math.log(1.05),
    "kelle_table_rounded_relative_ppl":5.62/4.88-1,
}
check("SANTA denominator demonstrates factor6",math.isclose(values["santa_batch_step_ms"]/values["santa_aggregate_ms_per_output"],6))
check("SANTA displayed rounded values match",round(values["santa_aggregate_ms_per_output"],4)==8.2373 and round(values["santa_prefill_plus_decode_speedup"],4)==1.1478)
check("PPL log ratio",math.isclose(math.exp(values["ppl_5pct_delta_nll"]),1.05))
check("Kelle rounded relative increase",round(values["kelle_table_rounded_relative_ppl"]*100,2)==15.16)
# Relative source links must exist locally or in the frozen Git tree.
links=re.findall(r"\]\(([^)]+)\)",readme)
local_targets=[]
for target in links:
    if target.startswith(("http://","https://")):
        continue
    resolved=(DIR/target.split("#")[0]).resolve()
    try:
        rel=resolved.relative_to(ROOT).as_posix()
    except ValueError:
        raise AssertionError("relative link escapes repository: "+target)
    if resolved.exists():
        exists=True
    else:
        proc=subprocess.run(["git","cat-file","-e",BASE+":"+rel],cwd=ROOT,capture_output=True)
        exists=proc.returncode==0
    check("relative link "+rel,exists)
    local_targets.append(rel)
# Existing result progress is checked by source text; no new inference.
def gittext(path):
    return subprocess.check_output(["git","show",BASE+":"+path],cwd=ROOT).decode("utf-8")
qwen=gittext("qwen/results/task_accuracy_20261019/RESULTS_ZH.md")
llama=gittext("llama2/results/task_accuracy_20261020/FINAL_RESULTS_20261022_ZH.md")
check("Qwen39 complete; subset explicit","39/39" in qwen and "1000" in qwen)
check("Llama26 final, not legacy pending","26/26" in llama and "109564" in llama and "78.99891" in llama)
source_paths={
    "mba_user_pdf":Path("C:/Users/86134/Downloads/509_Camera_Ready_Paper.pdf"),
    "historical_gpu_report":Path("C:/Users/86134/Documents/a_P_BIT/gpu_energy_20261011/GPU_ENERGY_REPORT_ZH.txt"),
    "historical14_model_sample":Path("C:/Users/86134/Documents/a_P_BIT/pbit_llm_master_report_20261012/LLM_HARDWARE_BENCHMARK_MODEL_SAMPLE_20261017.json")
}
source_hashes={key:{"path":str(path),"sha256":sha(path),"bytes":path.stat().st_size} for key,path in source_paths.items()}
check("user PDF bytes verified",source_hashes["mba_user_pdf"]["sha256"]=="23d1f57ce46566027c75f98c9ea332d904c2547c659cf8903142115c145fdd73")
for path in DIR.iterdir():
    if path.suffix in {".md",".json",".csv"}:
        raw=path.read_bytes()
        check("UTF8 LF "+path.name, b"\r" not in raw and raw.endswith(b"\n") and not raw.startswith(b"\xef\xbb\xbf"))
report_files={str(p.relative_to(ROOT)).replace("\\","/"):{"sha256":sha(p),"bytes":p.stat().st_size} for p in sorted(DIR.iterdir()) if p.suffix in {".md",".json",".csv"}}
out={"issue":98,"base_commit":BASE,"validation_kind":"research_document_consistency_and_existing_evidence_reads_only","new_model_or_PPA_runs":False,"checks":checks,"check_count":len(checks),"all_passed":all(c["passed"] for c in checks),"derived_values":values,"artifacts":report_files,"source_hashes":source_hashes,"relative_targets":local_targets,"not_applicable":"No new numerical experiment: new model/data configuration, seeds, runtime environment, Slurm and EDA result manifest fields are not applicable. Future-run fields in proposal remain unresolved/null."}
destination=ROOT/"work/rayggxia/98/VALIDATION.json"
destination.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps({"checks":out["check_count"],"all_passed":out["all_passed"],"report_files":len(report_files),"derived_values":values},ensure_ascii=False))
