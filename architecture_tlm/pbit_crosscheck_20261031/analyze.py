"""Reconcile existing p-bit power records offline; never runs EDA or a model."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics as st
import zipfile

NUM = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
ROW = re.compile(r"^(.*?)\s+(" + NUM + r")\s+(" + NUM + r")\s+(" + NUM
                 + r")\s+(" + NUM + r")\s+\(\s*" + NUM + r"\s*%\)\s*([a-z ]*)$")


def read(p):
    return json.loads(p.read_text(encoding="utf-8"))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def bit_price(pj, bits):
    return dict(pJ_per_bit=pj / bits, fJ_per_bit=pj / bits * 1000,
                J_per_bit=pj / bits * 1e-12)


def cells(text, inv):
    rows, pending, started = {}, "", False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Cell ") and "Power" in line:
            started = True
            continue
        if not started or not line or line.startswith("---"):
            continue
        pending = (pending + " " + line).strip()
        if pending.startswith("Totals"):
            break
        match = ROW.fullmatch(pending)
        if match:
            name = "".join(match[1].split())
            assert name in inv and name not in rows, name
            rows[name] = [float(match[i]) for i in range(2, 6)]
            pending = ""
    assert rows.keys() == inv.keys(), (len(rows), len(inv))
    return rows


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument("--attention", type=Path, required=True,
                    help="Existing gf64_compare_20261030 directory")
    ap.add_argument("--ffn", type=Path, required=True,
                    help="Existing nonlinear_wd_shared32_20261031 directory")
    ap.add_argument("--catalog", type=Path, required=True,
                    help="Existing random_service/digital_pbit directory")
    args = ap.parse_args()
    ar, fs, cat = args.attention, args.ffn, args.catalog
    evidence = read(ar / "EVIDENCE.json")
    archive = Path(evidence["reports_archive"])
    assert sha(archive) == evidence["sha256"]
    attention, member_index, checked_cells = [], [], 0
    with zipfile.ZipFile(archive) as z:
        for r in read(ar / "RESULTS.json")["results"]:
            top = r["case"]["top"]
            parts, counts = [], []
            for w in r["windows"]:
                if w["window"] != "work":
                    continue
                prefix = "results/v1/" + w["path"] + "/"
                names = [prefix + n for n in ("inventory.tsv", "cell_power.rpt")]
                blobs = [z.read(n) for n in names]
                inv = {v["instance"]: v for v in csv.DictReader(
                    io.StringIO(blobs[0].decode()), delimiter="\t")}
                rows = cells(blobs[1].decode(), inv)
                checked_cells += len(rows)
                # The Attention reports use W, whereas some FFN reports declare mW.
                # Confirm this run's unit directly instead of assuming cross-run units.
                power_text = z.read(prefix + "power.rpt").decode()
                assert re.search(r"Dynamic Power Units\s*=\s*1\s+W", power_text)
                assert re.search(r"Leakage Power Units\s*=\s*1\s+W", power_text)
                assert math.isclose(sum(v[3] for v in rows.values()),
                                    w["power"]["total_W"], rel_tol=.005)
                # Eight queries are included in each work window, including gaps.
                factor = (w["end_ns"] - w["start_ns"]) * 1000 / 8
                groups = {}
                for name, vals in rows.items():
                    key = ("q_ICG" if "clk_gate_shared_q_reg" in name else
                           "q_DFF" if "/shared_q_reg" in name else
                           "candidate_RNG" if "/candidates/" in name else "other")
                    g = groups.setdefault(key, dict(cells=0, raw_area_um2=0, pJ_query=0))
                    g["cells"] += 1
                    g["raw_area_um2"] += float(inv[name]["area_um2"])
                    g["pJ_query"] += vals[3] * factor
                parts.append(groups)
                counts.append(w["energy_pJ"] / 8)
                member_index.extend(dict(member=n, sha256=hashlib.sha256(b).hexdigest())
                                    for n, b in zip(names, blobs))
            assert len(parts) == 3
            groups = {}
            for k in parts[0]:
                if k == "other":
                    continue
                assert len({p[k]["cells"] for p in parts}) == 1
                pj = st.mean(p[k]["pJ_query"] for p in parts)
                raw = parts[0][k]["raw_area_um2"]
                groups[k] = dict(cells=parts[0][k]["cells"], pJ_query=pj,
                                 raw_area_um2=raw, area55eq_um2=raw * .81,
                                 **bit_price(pj, 128 * 128))
            total = st.mean(counts)
            a = dict(case=top, N=128, T=128, queries_per_window=8,
                     total_pJ_query=total,
                     total_normalized_per_internal_candidate_bit=bit_price(total, 16384),
                     total_pJ_per_selected_index=total / 128, groups=groups,
                     pure_sigmoid_compare_pJ_per_bit=None,
                     reason="LUT/comparators flattened with other logic; no isolated old report")
            if r["case"]["luts"] == 4:
                assert groups["q_DFF"]["cells"] == 1024
                assert groups["q_ICG"]["cells"] == 32
                qcost = groups["q_DFF"]["pJ_query"] + groups["q_ICG"]["pJ_query"]
                a["q_bank_per_node_configuration_pJ"] = qcost / 128
                a["q_bank_per_bit"] = bit_price(qcost, 16384)
            attention.append(a)
    ffn = []
    for r in read(fs / "results/SUMMARY_SMALL.json")["table"]:
        if not r["weighted"]:
            continue
        profiles = {}
        for mode in ("replay32", "sample_first", "prepare_first"):
            if mode not in r["profiles"]:
                continue
            h = r["profiles"][mode]["hierarchy"]
            selected = {k: h[k]["total_pJ"] for k in
                        ("sigmoid_LUT_named", "compare_sigma", "probability_registers",
                         "probability_ICG") if k in h}
            pj = sum(selected.values())
            profiles[mode] = dict(named_sigma_energy_pJ=pj, components_pJ=selected,
                                  **bit_price(pj, 2048))
            if mode == "prepare_first":
                profiles[mode]["normalization"] = "Load energy amortized over later2048 bits; zero sample bits in LOAD"
        h = r["profiles"]["replay32"]["hierarchy"]
        assert math.isclose(h["compare_sigma"]["area55eq_um2"], 64 * 39.6 * .81,
                            rel_tol=1e-12)
        qcost = sum(h[k]["total_pJ"] for k in ("probability_registers", "probability_ICG") if k in h)
        ffn.append(dict(case=r["case"], N=64, T=32, frame_ns=r["frame_ns"],
                        real_ICGs=r["real_ICG_cells"], profiles=profiles,
                        q_bank_per_node_configuration_pJ=qcost / 64,
                        q_bank_per_bit=bit_price(qcost, 2048),
                        scope="Named sigmoid LUT+compare+q register+ICG only;no RNG,conversion,AND,Wd or flattened lookup mux/control"))
    cd = read(cat / "catalog.json")
    assert sha(cat / cd["source"]["summary_file"]) == cd["source"]["summary_sha256"]
    standalone = [dict(top=r["top"], raw_area_um2=r["area_um2"],
                       area55eq_um2=r["area_um2"] * .81,
                       random_pJ_call=r["modes"]["random"]["pJ_per_call"],
                       fixed50_pJ_call=r["modes"]["fixed50"]["pJ_per_call"])
                  for r in cd["designs"] if r["corner"] == "ss"]
    source_files = [(ar, n) for n in ("RESULTS.json", "SUMMARY.json", "ising.sv", "gf64_farm.sv", "sigmoid.vh", "tb.sv")]
    source_files += [(fs, n) for n in ("results/SUMMARY_SMALL.json", "rtl/integrated.sv")]
    source_files += [(cat, "catalog.json")]
    result = dict(date="2026-10-31", issue=204, owner="rayggxia", kind="existing_result_reanalysis_no_new_run",
                  analysis_code_sha256=sha(Path(__file__)),
                  conditions="SS1.08V125C100MHz; area raw*.81 once; no energy/time scaling",
                  units="1pJ=1e-12J=1000fJ; denominator counts consumed candidate bits,not independent entropy or ESS",
                  attention=attention, ffn=ffn, standalone_ss=standalone,
                  checks=dict(attention_cell_rows=checked_cells, attention_work_windows=6,
                              attention_source_archive_sha256=evidence["sha256"],
                              inventory_power_totals_match=True, catalog_evidence_sha_match=True,
                              ffn_compare_area_matches_64_single_cores=True),
                  sources=[dict(file=root.name + "/" + n, sha256=sha(root / n)) for root, n in source_files],
                  archive_members=member_index,
                  limitations=["Different LUTs: signed8/F3 FFN versus unsigned gap/F4 Attention",
                               "Different stimuli and output loading; both prelayout with retained power warnings",
                               "FFN actual GF64 remains external; no integrated GF64 nonlinear/Wd measurement",
                               "Named FFN sums omit flattened mux/control; Attention pure p-bit remains unisolated",
                               "First-frame sample profiles are not eight-frame averages or overlapped pipelines"])
    out = Path(__file__).resolve().parent / "ANALYSIS.json"
    out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(dict(output=out.name, checked=checked_cells,
                         attention_total_nJ=[r["total_pJ_query"] / 1000 for r in attention],
                         ffn_sigma_fJ=[r["profiles"]["replay32"]["fJ_per_bit"] for r in ffn])))


if __name__ == "__main__":
    main()
