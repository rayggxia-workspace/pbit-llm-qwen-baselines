param([Parameter(Mandatory=$true)][ValidateSet('Prepare','Execute')][string]$Mode)
$ErrorActionPreference='Stop'
$workspaceRoot='C:\Users\86134\Documents\a_P_BIT'
$auditRoot=Join-Path $workspaceRoot 'tmp\local_cleanup_20261019'
$repo=Join-Path $workspaceRoot 'pbit-llm-qwen-baselines'

function Assert-WorkspacePath([string]$path){
    $full=[IO.Path]::GetFullPath($path)
    if(!$full.StartsWith($workspaceRoot+'\',[StringComparison]::OrdinalIgnoreCase)){throw "Outside workspace: $full"}
    $item=Get-Item -LiteralPath $full -Force
    $node=$item
    while($null -ne $node){
        if($node.Attributes -band [IO.FileAttributes]::ReparsePoint){throw "Reparse point: $($node.FullName)"}
        if($node.FullName -eq $workspaceRoot){break}
        $node=if($node.PSIsContainer){$node.Parent}else{$node.Directory}
    }
    return $item
}
function Git-Text([string]$path,[string[]]$arguments){
    $lines=@(& git -C $path @arguments)
    if($LASTEXITCODE -ne 0){throw "Git failed in $path : $($arguments -join ' ')"}
    return ($lines -join "`n")
}
function Save-Json($obj,[string]$path){
    $json=ConvertTo-Json -InputObject $obj -Depth 15
    [IO.File]::WriteAllText($path,$json.Replace("`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
}

if($Mode -eq 'Prepare'){
    if(Test-Path -LiteralPath (Join-Path $auditRoot 'delete_plan.json')){throw 'Existing plan: inspect rather than overwrite'}
    $preflight=Get-Content -LiteralPath (Join-Path $auditRoot 'worktree_preflight.json') -Raw | ConvertFrom-Json
    $inventory=Get-Content -LiteralPath (Join-Path $auditRoot 'inventory_before.json') -Raw | ConvertFrom-Json
    $backups=Join-Path $auditRoot 'recovery'
    [void](New-Item -ItemType Directory -Path $backups -Force)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $worktrees=[Collections.Generic.List[object]]::new()
    foreach($entry in $preflight.records){
        $dir=Assert-WorkspacePath $entry.path
        if(!$dir.PSIsContainer -or $dir.Parent.FullName -ne (Join-Path $workspaceRoot 'tmp') -or $dir.Name -notmatch '^pr55-resolve-\d+-20261019$'){throw 'Unexpected worktree root'}
        if(!$entry.ancestor -or $entry.branch -notmatch '^refs/heads/review/55-refresh-pr\d+$'){continue}
        $head=Git-Text $dir.FullName @('rev-parse','HEAD')
        if($head -ne $entry.head){throw "HEAD changed: $($dir.FullName)"}
        $status=Git-Text $dir.FullName @('status','--porcelain=v1','--untracked-files=all')
        $changed=@((Git-Text $dir.FullName @('diff','--name-only','HEAD')).Split("`n",[StringSplitOptions]::RemoveEmptyEntries))
        $untracked=@((Git-Text $dir.FullName @('ls-files','--others','--exclude-standard')).Split("`n",[StringSplitOptions]::RemoveEmptyEntries))
        $ignored=@((Git-Text $dir.FullName @('ls-files','--others','--ignored','--exclude-standard')).Split("`n",[StringSplitOptions]::RemoveEmptyEntries))
        $names=@($changed+$untracked | Sort-Object -Unique)
        if(@($names | Where-Object {$_ -ne 'sources.json' -and $_ -notmatch '^_resolution_inputs/[^/]+$'}).Count -gt 0){continue}
        if(@($ignored | Where-Object {$_ -notmatch '(^|/)(__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache)/'}).Count -gt 0){continue}
        $backupFiles=[Collections.Generic.List[object]]::new()
        $zipPath=Join-Path $backups ($dir.Name+'.zip')
        if($names.Count -gt 0){
            $zip=[IO.Compression.ZipFile]::Open($zipPath,[IO.Compression.ZipArchiveMode]::Create)
            try{
                foreach($name in $names){
                    $file=Assert-WorkspacePath (Join-Path $dir.FullName $name)
                    if($file.PSIsContainer){throw 'Only files may enter recovery zip'}
                    $hash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
                    [void][IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$file.FullName,$name,[IO.Compression.CompressionLevel]::Optimal)
                    $backupFiles.Add([pscustomobject]@{relative=$name;bytes=$file.Length;sha256=$hash})
                }
            }finally{$zip.Dispose()}
            $zip=[IO.Compression.ZipFile]::OpenRead($zipPath)
            try{
                foreach($file in $backupFiles){
                    $member=$zip.GetEntry($file.relative)
                    if($null -eq $member -or $member.Length -ne $file.bytes){throw 'Backup size mismatch'}
                    $stream=$member.Open();$hasher=[Security.Cryptography.SHA256]::Create()
                    try{$actual=[Convert]::ToHexString($hasher.ComputeHash($stream))}finally{$stream.Dispose();$hasher.Dispose()}
                    if($actual -ne $file.sha256){throw 'Backup hash mismatch'}
                }
            }finally{$zip.Dispose()}
        }
        $worktrees.Add([pscustomobject]@{path=$dir.FullName;head=$head;branch=$entry.branch;merged_in=$preflight.base;status=$status;ignored=$ignored;bytes=$entry.bytes;backup=if($names.Count){$zipPath}else{$null};backup_sha256=if($names.Count){(Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash}else{$null};preserved_files=@($backupFiles)})
    }
    $files=[Collections.Generic.List[object]]::new()
    $cacheRoots=@($inventory.caches.psobject.Properties.Name | Where-Object {$_ -notmatch '^tmp\\' -and $_ -notmatch '^worktrees\\' -and $_ -match '^(architecture_tlm|pbit_llm|pbit-llm-qwen-baselines|qwen|joint|llama|pbit_.*ffn|pbit_sc|pbit_streaming|pbit_shared)'})
    foreach($relative in $cacheRoots){
        $dir=Assert-WorkspacePath (Join-Path $workspaceRoot $relative)
        foreach($file in Get-ChildItem -LiteralPath $dir.FullName -File -Recurse -Force){
            if($file.Extension -ne '.pyc'){continue}
            $safe=Assert-WorkspacePath $file.FullName
            $files.Add([pscustomobject]@{path=$safe.FullName;bytes=$safe.Length;sha256=(Get-FileHash -LiteralPath $safe.FullName -Algorithm SHA256).Hash;kind='python_bytecode';keep=$null})
        }
    }
    $manifest=Get-Content -LiteralPath (Join-Path $workspaceRoot 'architecture_tlm\.deps\zigzag_dependency_manifest.json') -Raw | ConvertFrom-Json
    $manifestText=Get-Content -LiteralPath (Join-Path $workspaceRoot 'architecture_tlm\.deps\zigzag_dependency_manifest.json') -Raw
    foreach($file in Get-ChildItem -LiteralPath (Join-Path $workspaceRoot 'architecture_tlm\.deps\wheels') -File -Filter '*.whl'){
        $safe=Assert-WorkspacePath $file.FullName
        $hash=(Get-FileHash -LiteralPath $safe.FullName -Algorithm SHA256).Hash
        if(!$manifestText.Contains($hash.ToLowerInvariant()) -and !$manifestText.Contains($hash)){throw 'Wheel absent from dependency hash manifest'}
        $files.Add([pscustomobject]@{path=$safe.FullName;bytes=$safe.Length;sha256=$hash;kind='downloaded_wheel_cache';keep='architecture_tlm/.deps/zigzag385 + zigzag_dependency_manifest.json'})
    }
    $qa=Join-Path $workspaceRoot 'pbit_llm_master_report_20261012\word_qa'
    foreach($file in Get-ChildItem -LiteralPath $qa -File -Filter 'checked-page-*.png'){
        $keep=Join-Path $qa ($file.Name.Replace('checked-page-','final-page-'))
        if(!(Test-Path -LiteralPath $keep)){continue}
        $hash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        if((Get-FileHash -LiteralPath $keep -Algorithm SHA256).Hash -ne $hash){continue}
        $files.Add([pscustomobject]@{path=$file.FullName;bytes=$file.Length;sha256=$hash;kind='identical_word_QA_image';keep=$keep})
    }
    $model=Join-Path $workspaceRoot 'pbit_llm\models\Qwen2.5-0.5B-modelscope\model.safetensors'
    $modelHash=(Get-FileHash -LiteralPath $model -Algorithm SHA256).Hash
    $plan=[pscustomobject]@{created=(Get-Date).ToString('o');root=$workspaceRoot;issue=68;base=$preflight.base;model_path=$model;model_sha256=$modelHash;worktrees=@($worktrees);files=@($files);disk_free_before=(Get-PSDrive C).Free;no_other_member_worktrees=$true}
    Save-Json $plan (Join-Path $auditRoot 'delete_plan.json')
    [pscustomobject]@{worktrees=$worktrees.Count;worktree_GiB=[math]::Round(($worktrees | Measure-Object bytes -Sum).Sum/1GB,3);files=$files.Count;file_MiB=[math]::Round(($files | Measure-Object bytes -Sum).Sum/1MB,3);model_sha256=$modelHash} | ConvertTo-Json -Compress
    exit
}

$receiptPath=Join-Path $auditRoot 'execution_receipt.json'
if(Test-Path -LiteralPath $receiptPath){throw 'Existing execution receipt; do not repeat'}
$plan=Get-Content -LiteralPath (Join-Path $auditRoot 'delete_plan.json') -Raw | ConvertFrom-Json
$receipt=[Collections.Generic.List[object]]::new()
try{
    foreach($entry in $plan.worktrees){
        $dir=Assert-WorkspacePath $entry.path
        if($dir.Parent.FullName -ne (Join-Path $workspaceRoot 'tmp') -or $dir.Name -notmatch '^pr55-resolve-\d+-20261019$'){throw 'Unexpected worktree root at execution'}
        if((Git-Text $dir.FullName @('rev-parse','HEAD')) -ne $entry.head){throw 'HEAD changed after plan'}
        if((Git-Text $dir.FullName @('status','--porcelain=v1','--untracked-files=all')) -ne $entry.status){throw 'Worktree state changed after plan'}
        & git -C $repo merge-base --is-ancestor $entry.head $plan.base
        if($LASTEXITCODE -ne 0){throw 'Worktree not merged'}
        if($entry.backup){
            if((Get-FileHash -LiteralPath $entry.backup -Algorithm SHA256).Hash -ne $entry.backup_sha256){throw 'Recovery archive changed'}
            foreach($file in $entry.preserved_files){
                $p=Assert-WorkspacePath (Join-Path $dir.FullName $file.relative)
                if($p.Length -ne $file.bytes -or (Get-FileHash -LiteralPath $p.FullName -Algorithm SHA256).Hash -ne $file.sha256){throw 'Preserved file changed'}
            }
        }
        $branchSha=Git-Text $repo @('rev-parse',$entry.branch)
        if($branchSha -ne $entry.head){throw 'Recovery branch changed'}
        if($entry.status){& git -C $repo worktree remove --force $dir.FullName}else{& git -C $repo worktree remove $dir.FullName}
        if($LASTEXITCODE -ne 0){throw 'Git worktree remove failed'}
        if(Test-Path -LiteralPath $dir.FullName){throw 'Worktree path still exists'}
        if((Git-Text $repo @('rev-parse',$entry.branch)) -ne $entry.head){throw 'Recovery branch was not preserved'}
        $receipt.Add([pscustomobject]@{kind='completed_own_review_worktree';path=$entry.path;bytes=$entry.bytes;head=$entry.head;branch=$entry.branch;backup=$entry.backup;backup_sha256=$entry.backup_sha256;status='removed_branch_and_recovery_preserved'})
        Save-Json @($receipt) $receiptPath
    }
    foreach($entry in $plan.files){
        $file=Assert-WorkspacePath $entry.path
        if($file.PSIsContainer -or $file.Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256){throw "File changed: $($entry.path)"}
        if($entry.kind -eq 'identical_word_QA_image' -and (Get-FileHash -LiteralPath $entry.keep -Algorithm SHA256).Hash -ne $entry.sha256){throw 'Retained duplicate changed'}
        Remove-Item -LiteralPath $file.FullName -Force
        $receipt.Add([pscustomobject]@{kind=$entry.kind;path=$entry.path;bytes=$entry.bytes;sha256=$entry.sha256;keep=$entry.keep;status='removed'})
    }
}finally{
    Save-Json @($receipt) $receiptPath
}
if((Get-FileHash -LiteralPath $plan.model_path -Algorithm SHA256).Hash -ne $plan.model_sha256){throw 'Retained model changed'}
$summary=[pscustomobject]@{finished=(Get-Date).ToString('o');removed_entries=$receipt.Count;removed_bytes=($receipt | Measure-Object bytes -Sum).Sum;groups=@($receipt | Group-Object kind | ForEach-Object {[pscustomobject]@{kind=$_.Name;entries=$_.Count;bytes=($_.Group | Measure-Object bytes -Sum).Sum}});disk_free_before=$plan.disk_free_before;disk_free_after=(Get-PSDrive C).Free;retained_model_sha256=$plan.model_sha256;retained_model_verified=$true;git_main_repo_present=(Test-Path -LiteralPath (Join-Path $repo '.git'));recovery_root=(Join-Path $auditRoot 'recovery')}
Save-Json $summary (Join-Path $auditRoot 'summary.json')
$summary | ConvertTo-Json -Depth 5
