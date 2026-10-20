$ErrorActionPreference='Stop'
$workspaceRoot='C:\Users\86134\Documents\a_P_BIT'
$auditRoot=Join-Path $workspaceRoot 'tmp\local_cleanup_20261019'
$repo=Join-Path $workspaceRoot 'pbit-llm-qwen-baselines'
$receiptPath=Join-Path $auditRoot 'round2_execution_receipt.json'
if(Test-Path -LiteralPath $receiptPath){throw 'Existing receipt; no repeated cleanup'}
$plan=Get-Content -LiteralPath (Join-Path $auditRoot 'round2_delete_plan.json') -Raw | ConvertFrom-Json
$issues=Get-Content -LiteralPath (Join-Path $auditRoot 'round2_remote_issues.json') -Raw | ConvertFrom-Json
$allowedIssues=@(3,5,9,12,14,16,23,26,30,32,39,46,51,55)
$receipt=[Collections.Generic.List[object]]::new()
$freeBefore=(Get-PSDrive C).Free
function Save-Receipt{
    $json=ConvertTo-Json -InputObject @($receipt) -Depth 9
    [IO.File]::WriteAllText($receiptPath,$json.Replace("`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
}
function Assert-Path([string]$path){
    $full=[IO.Path]::GetFullPath($path)
    if(!$full.StartsWith($workspaceRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path outside workspace'}
    $item=Get-Item -LiteralPath $full -Force
    $node=$item
    while($null -ne $node){
        if($node.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse point'}
        if($node.FullName -eq $workspaceRoot){break}
        $node=if($node.PSIsContainer){$node.Parent}else{$node.Directory}
    }
    return $item
}
function Git-Text([string]$path,[string[]]$argsList){
    $lines=@(& git -C $path @argsList)
    if($LASTEXITCODE -ne 0){throw 'Git failed'}
    return ($lines -join "`n")
}
try{
    foreach($entry in $plan.records){
        $item=Assert-Path $entry.path
        if(!$item.PSIsContainer -or $item.Parent.FullName -ne (Join-Path $workspaceRoot 'tmp')){throw 'Unexpected worktree parent'}
        if($entry.issue -notin $allowedIssues -or $entry.owner -ne 'jieruiz'){throw 'Unexpected task scope'}
        $issue=@($issues | Where-Object {$_.number -eq $entry.issue})
        if($issue.Count -ne 1 -or $issue[0].state -ne 'closed' -or $issue[0].owner -ne 'jieruiz'){throw 'Issue ownership/status mismatch'}
        if($item.Name -eq 'pr47-review-main-20261019'){throw 'Other-owner handoff must be retained'}
        if((Git-Text $item.FullName @('rev-parse','HEAD')) -ne $entry.head){throw 'HEAD changed'}
        if((Git-Text $repo @('rev-parse',$entry.recovery_ref)) -ne $entry.head){throw 'Recovery ref changed'}
        if($entry.branch -and (Git-Text $repo @('rev-parse',$entry.branch)) -ne $entry.head){throw 'Original branch changed'}
        foreach($type in @('zip','bundle')){
            $archive=$entry.$type
            if($archive){
                $file=Assert-Path $archive
                if(!$file.FullName.StartsWith((Join-Path $workspaceRoot 'project_archives\cleanup_20261019_round2')+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected archive location'}
                $hashName=$type+'_sha256'
                if((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.$hashName){throw 'Archive hash changed'}
            }
        }
        foreach($saved in $entry.preserved_files){
            $file=Assert-Path (Join-Path $item.FullName $saved.relative)
            if($file.PSIsContainer -or $file.Length -ne $saved.bytes -or (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $saved.sha256){throw 'Unique file changed after archive'}
        }
        $taskPy='C:/Users/86134/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
        & $taskPy -X utf8 (Join-Path $auditRoot 'validate_round2_state.py') $item.FullName
        if($LASTEXITCODE -ne 0){throw 'Working state changed'}
        if($entry.preserved_files.Count -gt 0 -or $entry.ignored_caches.Count -gt 0){& git -C $repo worktree remove --force $item.FullName}else{& git -C $repo worktree remove $item.FullName}
        if($LASTEXITCODE -ne 0){throw 'Git worktree removal failed'}
        if(Test-Path -LiteralPath $entry.path){throw 'Worktree still exists'}
        if((Git-Text $repo @('rev-parse',$entry.recovery_ref)) -ne $entry.head){throw 'Recovery ref lost'}
        $receipt.Add([pscustomobject]@{path=$entry.path;issue=$entry.issue;head=$entry.head;branch=$entry.branch;recovery_ref=$entry.recovery_ref;bytes=$entry.bytes;files=$entry.files;zip=$entry.zip;zip_sha256=$entry.zip_sha256;bundle=$entry.bundle;bundle_sha256=$entry.bundle_sha256;unique_files=$entry.preserved_files.Count;status='removed_recoverable_worktree'})
        Save-Receipt
        [pscustomobject]@{removed=$item.Name;MiB=[math]::Round($entry.bytes/1MB,2)} | ConvertTo-Json -Compress
    }
}finally{Save-Receipt}
$archives=Get-ChildItem -LiteralPath (Join-Path $workspaceRoot 'project_archives\cleanup_20261019_round2') -File
$summary=[pscustomobject]@{finished=(Get-Date).ToString('o');removed_worktrees=$receipt.Count;removed_bytes=($receipt | Measure-Object bytes -Sum).Sum;unique_files_archived=($receipt | Measure-Object unique_files -Sum).Sum;archive_bytes=($archives | Measure-Object Length -Sum).Sum;archive_count=$archives.Count;free_before=$freeBefore;free_after=(Get-PSDrive C).Free;no_pagefile_or_system_setting_changes=$true}
$summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $auditRoot 'round2_summary.json') -Encoding utf8
$summary | ConvertTo-Json -Depth 6
