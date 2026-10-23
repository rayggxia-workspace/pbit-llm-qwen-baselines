$ErrorActionPreference = 'Stop'
$repo = 'rayggxia-workspace/pbit-llm-qwen-baselines'
$raw = "protocol=https`nhost=github.com`nusername=jieruiz`n`n" | git credential fill
$keys = @{}
foreach ($line in $raw) { $pair = $line -split '=', 2; if ($pair.Length -eq 2) { $keys[$pair[0]] = $pair[1] } }
$headers = @{Authorization="Bearer $($keys['password'])"; Accept='application/vnd.github+json'; 'User-Agent'='Codex-Issue146'}
$user = Invoke-RestMethod https://api.github.com/user -Headers $headers -TimeoutSec 20
if ($user.login -ne 'jieruiz') { throw 'GitHub identity mismatch' }
$pr = Invoke-RestMethod "https://api.github.com/repos/$repo/pulls/148" -Headers $headers -TimeoutSec 20
$head = (git rev-parse HEAD).Trim()
if ($pr.head.sha -ne $head) { throw "Remote PR head differs from local: $($pr.head.sha)" }
$body = @"
Issue146 PPA v2 delivered on existing PR148, head $head. No RTL/testbench byte changes.

Adds SS/TT 100MHz Slurm smoke/formal matrices, immutable source snapshots, three-seed runs, verified real non-inverting buffer selection, exclusive-leaf area/power summaries, units/activity/energy checks and small success/failure archives. Fixed the original Tcl buffer-pin interpolation error. No FGP license required.

Actual local validation: 11 helper checks, four small RTL simulations, 48 scalarized X/Z-clean windows; 33 package files match staged Git blobs. **DC/VCS/PT are pending, not passed PPA.** Registry: cim-frontend-146-ppa-v2-prepared. Existing v1 evidence is preserved.

Package: sc_cim_frontend_ppa_20261023_v2.zip, 49471 bytes, SHA256 f2ef9036c30adcbccd4a2c2c24543fe27061ff04facb3d6a27948f294b701228. Upload/run guide: architecture_tlm/sc_cim_frontend_20261023/RUN_BATCH_ZH.txt. Run smoke first, return reports tarballs/logs, then full 64x64. Do not double-count W8 AND already present in Issue133 counters. Q probe is not physical SRAM storage.

PR remains open/unmerged; no remote EDA jobs started here. Projects board update remains pending maintainer access; no new board-permission claim.
"@
$payload = [System.Text.Encoding]::UTF8.GetBytes((@{body=$body} | ConvertTo-Json))
$issueComment = Invoke-RestMethod "https://api.github.com/repos/$repo/issues/146/comments" -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 20
$prComment = Invoke-RestMethod "https://api.github.com/repos/$repo/issues/148/comments" -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 20
$receipt = @{login=$user.login;repository=$repo;head=$head;pr=148;state=$pr.state;merged=$pr.merged;issue_comment=$issueComment.html_url;pr_comment=$prComment.html_url;status='PUSHED_REMOTE_HEAD_VERIFIED';board='not_updated_pending_maintainer';eda='not_run'}
$json = ($receipt | ConvertTo-Json -Depth 5) -replace "`r`n","`n"
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'V2_PUBLICATION.json'),$json+"`n",[System.Text.UTF8Encoding]::new($false))
Write-Output $json
