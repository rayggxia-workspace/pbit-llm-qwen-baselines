"""Read-only paired comparison of downloaded, already verified Issue182 results."""
import copy
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def get(root, pattern):
    paths = list((ROOT / root / "results").glob(pattern + "/RESULT.json"))
    assert len(paths) == 1, paths
    return paths[0], json.loads(paths[0].read_text())


def normalized_config(result):
    c = copy.deepcopy(result["config"])
    for k in ("configuration", "output_prefix"):
        c["dram"].pop(k)
    c["ffn"].pop("prefetch_across_input_groups", None)
    return c


def main():
    paired = []
    for n in (8, 16, 32, 64):
        oldpath, old = get("first11_evidence", "*_balanced_e" + str(n))
        newpath, new = get("cross4_evidence", "*_cross_group_e" + str(n))
        assert normalized_config(old) == normalized_config(new), (n, "config mismatch")
        assert not old["config"]["ffn"].get("prefetch_across_input_groups", False)
        assert new["config"]["ffn"]["prefetch_across_input_groups"]
        assert old["model"] == new["model"]
        assert old["DRAM"]["traffic"] == new["DRAM"]["traffic"], (n, "traffic mismatch")
        assert old["FFN_activity"]["SC_64x64_tiles"] == new["FFN_activity"]["SC_64x64_tiles"] == 656640
        assert new["FFN_contract"]["weight_pipeline"]["counts"]["cross_input_group_prefetches"] == 6840
        assert not new["FFN_contract"]["weight_pipeline"]["pending"]
        for x in (old, new):
            assert x["config"]["digital_weight_chunk_bytes"] == 65536
            assert x["DRAM"]["details"]["configuration_sha256"] == "ddbdd1aee7f20d5e3eaf12d73b7e300894ad3ab5cc50ae2a8aa5fd121b2fa419"
            assert x["metrics"]["full_physical_energy_J"] is None
        om, nm = old["metrics"]["TPOT_ms"], new["metrics"]["TPOT_ms"]
        paired.append(dict(engines=n, first_round_result=str(oldpath), first_round_result_sha256=sha(oldpath),
                           cross_group_result=str(newpath), cross_group_result_sha256=sha(newpath),
                           first_round_TPOT_ms=om, cross_group_TPOT_ms=nm,
                           TPOT_change_percent=(nm/om-1)*100,
                           first_round_DRAM_core_model_J=old["energy_J"]["external_DRAMPower_core"],
                           cross_group_DRAM_core_model_J=new["energy_J"]["external_DRAMPower_core"],
                           traffic_identical=True, normalized_configuration_identical=True,
                           burst_count=new["DRAM"]["details"]["burst_count"],
                           cross_group_prefetches=6840, wall_seconds=new["wall_seconds"]))
    energies = []
    for root in ("first11_evidence", "attention4_evidence", "cross4_evidence"):
        for p in sorted((ROOT/root/"results").glob("*/RESULT.json")):
            x = json.loads(p.read_text())
            adapters = x["DRAM"]["details"]["power_at_system_end"]
            act = sum(v["core_components_J"]["ACT"] for v in adapters.values())
            core = sum(v["core_J"] for v in adapters.values())
            energies.append(dict(case=x["case"], seed=x["config"]["seed"],
                                 result_sha256=sha(p), core_model_J=core,
                                 ACT_increment_J=act, ACT_percent_of_core=100*act/core,
                                 total_physical_energy_J=x["metrics"]["full_physical_energy_J"]))
    assert len(energies) == 19, len(energies)
    out = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
               paired_cross_group_cases=paired, energy_component_audit=energies,
               boundary="Negative ACT is an uncalibrated model decomposition artifact under current-limit parameters, not physical negative activation energy. Its fraction is not a total error bound. No original results were modified. Different E values scale hardware resources; not an equal-area comparison.",
               comparison_normalization="Removed execution-specific DRAM config/output paths and the intentionally changed prefetch_across_input_groups flag. All remaining configuration fields and full per-kind DRAM traffic match for each E pair.")
    target = ROOT/"FINAL_PAIRED_AND_ENERGY_AUDIT.json"
    with target.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(json.dumps(dict(path=str(target), sha256=sha(target), pairs=paired, energy_cases=len(energies))))


if __name__ == "__main__":
    main()
