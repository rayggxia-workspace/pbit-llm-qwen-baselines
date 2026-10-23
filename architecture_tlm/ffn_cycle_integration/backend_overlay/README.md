# FFN cycle backend overlay

This package contains four files created for Issue123 and the exact unified diff
for `architecture_tlm/cycle_v1/ffn.py`. The backend was published in
[PR126](https://github.com/rayggxia-workspace/pbit-llm-qwen-baselines/pull/126)
at fixed head `160f46e0b63bdf94499e2434dc35e09f44fc2fcc`, with scientific commit
`ddd2e3406caac5075689f9388a041603e17d2b19`. This package retains the revision4
overlay for reproduction and history; it does not distribute the unchanged
backend or serve as evidence that a PR has merged.

`MANIFEST.json` pins that published baseline, the rebased FFN change
`15a87d93a5ce2626b21d0f6579a454fa02d74076`, the runner
`a0a0e53e901177053807f5cc5215a51f6383c93c`, and the revision4 snapshot
`7d3b45001b48e20d39d49237a5575b0d7b487ca5`. The three integration commits are
local snapshot provenance; public availability is established separately by
the parent publication. Original pre-rebase commit IDs remain in
`historical_local_commits`. The published baseline's `ffn.py` is byte-equivalent
after LF normalization to the former `902c49b` baseline; the patch and four
payload files are unchanged by this publication update.
The manifest records both the actual-byte SHA-256 from the research run and
the LF-normalized SHA-256 for every file in the revision4 52-file source closure.
The five changed files are outputs of the overlay, not baseline prerequisites.
The other 47 files are checked before installation, including the published
backend's snapshot, release-validation and result-publication tools.

Prepare a **separate, idle checkout** at the PR126 fixed head and stage the
encoding/restore and active-memory helper dependencies listed in the manifest
from their matching publication snapshot. A checkout of PR126 alone lacks
those Issue123 dependencies. Do not use a colleague's active worktree or the
publication checkout as the installation target. Hashes must match this
snapshot; a newer backend needs a separately reviewed overlay.

From the publication repository, using Python 3.11 or newer:

```sh
python -B -P architecture_tlm/ffn_cycle_integration/backend_overlay/apply_overlay.py \
  --backend-root /absolute/path/to/independent/backend --check
python -B -P architecture_tlm/ffn_cycle_integration/backend_overlay/apply_overlay.py \
  --backend-root /absolute/path/to/independent/backend
```

`--check` performs the entire preflight without creating files. A successful
fresh check reports `ready`; a matching installed tree reports `already_applied`
without writing, including on repeated normal invocation. The preflight rejects
missing or mismatched dependencies, unknown/preexisting new files, partial
application, unsafe paths, symbolic links and junctions. LF and CRLF are accepted
by normalizing CRLF to LF for hash checks; bare CR is rejected. The patch must
match every context line at its original offset, without fuzz or relocation.
The existing `ffn.py` keeps uniform CRLF if it used CRLF; new files use LF.

Before writing source files, installation preserves the exact original bytes in
`.ffn_contract_overlay/<overlay_id>/ffn.py.original` and writes an intent record.
New source files use exclusive creation. The existing `ffn.py` is replaced only
after another exact-byte check. Per-file steps and a final receipt record actual
and normalized hashes. An interrupted installation retains its backup and
journal and refuses an automatic fresh replay. Inspect the intent, failure
record and current files before manually recovering to a known state; the tool
does not delete files or automatically roll back. Keep the checkout idle:
this is not a cross-process transaction or protection from concurrent writers.
No tool here fetches code or installs external dependencies.

The synthetic installer regressions do not bundle Issue116 source:

```sh
python -B -P architecture_tlm/ffn_cycle_integration/backend_overlay/test_apply_overlay.py
```

On Windows, if the sandbox's default temporary directory is not writable, set
`FFN_OVERLAY_TEST_TMP` to a short writable directory **outside the publication
checkout**, then run the same test file. Tests cover LF/CRLF, complete dependency
preflight, exact patch application, wrong hashes, repeated application without
mtime changes, interrupted writes and preserved backups. The symlink regression
is explicitly skipped where Windows does not allow creating test symlinks.

To reproduce this package, use the revision4 raw-byte source manifest staged
with the research run and its matching backend checkout:

```sh
python -B -P architecture_tlm/ffn_cycle_integration/backend_overlay/prepare_overlay.py \
  --snapshot-root /absolute/path/to/reviewed/research/snapshot \
  --source-manifest /absolute/path/to/FFN_SOURCE_MANIFEST.json
```

Preparation requires the pinned revision4 backend commit, checks every snapshot
file before writing the manifest, and checks the four payloads and FFN diff
against the fixed published baseline and rebased integration commits. Existing
identical payloads are retained; changed payloads or a changed diff are refused.
The preparer reads the external snapshot but publishes no unchanged backend
source. A later revision requires reviewing the preparer's pins and regenerating
`MANIFEST.json` from its complete dependency snapshot. Keep
`snapshot_manifest_sha256` with the matching run evidence.

These checks establish source provenance and installer safety. Backend numerical,
trace and full-shape results are reported separately by the parent integration
report; this package does not establish RTL, STA, PPA, PPL or hardware results.
