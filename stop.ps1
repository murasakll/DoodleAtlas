$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$controlFile=Join-Path $PSScriptRoot 'data\control.json'
if(Test-Path -LiteralPath $controlFile){
    $control=Get-Content -LiteralPath $controlFile -Raw | ConvertFrom-Json
    try{
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$($control.port)/api/shutdown" -Headers @{'X-Host-Token'=$control.token} | Out-Null
        Write-Host 'Encerramento solicitado. O cache temporário será apagado.'
        exit
    }catch{}
}
$pidFile = Join-Path $PSScriptRoot 'data\server.pid'
if (!(Test-Path -LiteralPath $pidFile)) { Write-Host 'Nenhum PID registrado.'; exit }
$serverId = [int](Get-Content -LiteralPath $pidFile)
$expectedExe = Join-Path $PSScriptRoot 'runtime\python\python.exe'
$server = Get-CimInstance Win32_Process -Filter "ProcessId=$serverId"
if (!$server -or $server.ExecutablePath -ne $expectedExe -or $server.CommandLine -notmatch 'server\.py') {
    Write-Host 'O PID não pertence a este servidor; nenhum processo foi encerrado.'
    exit
}
Get-CimInstance Win32_Process -Filter "ParentProcessId=$serverId" | Where-Object { $_.ExecutablePath -eq $expectedExe -and $_.CommandLine -match 'multiprocessing' } | ForEach-Object { Stop-Process -Id $_.ProcessId }
Stop-Process -Id $serverId
Write-Host 'Servidor parado. O vigia da sessão removerá o cache temporário.'
