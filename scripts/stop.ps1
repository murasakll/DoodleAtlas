$ErrorActionPreference = "Stop"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$env:PYTHONPATH=Join-Path (Get-Location) "src"
& .\runtime\python\python.exe -m chiko stop
