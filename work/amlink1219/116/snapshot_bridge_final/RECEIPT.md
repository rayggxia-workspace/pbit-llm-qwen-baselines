# Fresh snapshot execution receipt

Source commit: `1395231`. Windows Python 3.13.3. This is a new local smoke after the dependency-closure fix, independent of the frozen server matrix results.

Command from the cycle23-core worktree:

```text
python -X utf8 -m architecture_tlm.cycle_v1.package_snapshot --archive work/amlink1219/116/snapshot_bridge_final/snapshot.tar.gz --manifest work/amlink1219/116/snapshot_bridge_final/manifest.json --check-directory ../../_snapshot_116_bridge_final
```

The archive contains 66 tracked source/data files, including 13 historical Python imports and the exact default SRAM calibration JSON. All 66 extracted hashes match the manifest. Archive SHA-256: `6ab85b51a911e947c07646e09d7949553d84e70cb3095e320ecfcd4e9cc24a0c`.

The subprocess used `-I`, had no `PYTHONPATH`, and verified every loaded project module lies under the new extraction directory. The source archive is retained locally, excluded from Git; it contains no weights, actual model fixture, historical result collections or environments. The calibration JSON is the explicitly required small runtime-data exception to result-directory exclusion.

- Synthetic cycle FFN completed: 945 accepted operations, 31,375,000 ps.
- Complete 64→64→64 v6 bridge smoke passed: legacy 6,890.5 ns; cycle 11,962.5 ns. These are separate timing contracts, not a speedup comparison.
- The new bridge cycle/event executions have equal full payloads, including traces, actions, timing, memory and numeric state.
- `manifest.json` records all source/data SHA-256 and the loaded-module paths. `stdout.txt`, `stderr.txt`, `bridge_summary.json`, `bridge_START.json` and `cycle_summary.json` preserve the actual fresh execution evidence. The bridge source commit is null inside the deliberately standalone extraction; the surrounding snapshot manifest binds all bytes to the checked-out source commit.

Scope: default runtime dependency closure for the supported cycle/v6 bridge. Custom calibration paths, actual model inputs, external RTL tools and external framework binaries remain explicit separate inputs.
