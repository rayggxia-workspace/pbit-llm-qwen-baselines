$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$inputDoc=[IO.Path]::GetFullPath((Join-Path $taskRoot 'architecture_tlm/memory_savings_20261023/概率计算架构的SRAM与DRAM节省总结.docx'))
$renderDir=Join-Path $PSScriptRoot 'render'
New-Item -ItemType Directory -Path $renderDir -Force | Out-Null
$outputPdf=Join-Path $renderDir 'word_export.pdf'
$word=$null
$document=$null
try {
  $word=New-Object -ComObject Word.Application
  $word.Visible=$false
  $word.DisplayAlerts=0
  $document=$word.Documents.Open($inputDoc,$false,$true)
  $document.Repaginate()
  $pages=$document.ComputeStatistics(2)
  $document.ExportAsFixedFormat($outputPdf,17)
  Write-Output "Word export completed: $pages pages"
} finally {
  if($null -ne $document){$document.Close(0);[void][Runtime.InteropServices.Marshal]::ReleaseComObject($document)}
  if($null -ne $word){$word.Quit();[void][Runtime.InteropServices.Marshal]::ReleaseComObject($word)}
}
