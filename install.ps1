$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path runtime,logs,data | Out-Null
if (!(Test-Path -LiteralPath runtime\python\python.exe)) {
    Invoke-WebRequest https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip -OutFile runtime\python.zip
    Expand-Archive -LiteralPath runtime\python.zip -DestinationPath runtime\python -Force
    Set-Content runtime\python\python312._pth -Encoding ASCII "python312.zip`n.`n..\..`nimport site"
    Invoke-WebRequest https://bootstrap.pypa.io/get-pip.py -OutFile runtime\get-pip.py
    & .\runtime\python\python.exe runtime\get-pip.py --no-warn-script-location
    if ($LASTEXITCODE -ne 0) { throw 'Falha no bootstrap pip' }
}
& .\runtime\python\python.exe -m pip install --only-binary=:all: -r requirements.txt --no-warn-script-location --log logs\install.log
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências' }
Write-Host 'Instalado dentro do projeto. Execute iniciar.bat. Nenhuma regra de Firewall foi alterada.'
