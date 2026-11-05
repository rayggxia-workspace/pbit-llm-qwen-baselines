# Memory experiment evidence

22 completed full-model cases: 3 historical local Link controls and 19 real DRAMSys runs.
Git retains the small original EXECUTION/MANIFEST files and derived RESULT_SUMMARY.json for the 19 remote runs. The full immutable RESULT.json, transaction traces and bridge output stay under /home/Hongjie_Zeng/projects/pbit-memory-issue182-20261025/; exact locations and original SHA-256 are in work/jieruiz/182/remote_*/**/RAW_REMOTE_INDEX.json and each MANIFEST.

DERIVED_SUMMARY_INDEX.json hashes each derived summary and records the raw manifest/result SHA. The analysis script checks these links when raw files are absent. It does not claim to re-verify inaccessible raw bytes on a fresh checkout. When raw files are locally present, it verifies and computes directly from those originals. The final publication checks both paths produce byte-identical SUMMARY.json.

SUMMARY.json and the Chinese results report distinguish source revisions, seeds and energy caveats. No new PPL, RTL/PT or chip measurement is implied.
